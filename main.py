# mypy: disable-error-code="prop-decorator"

import argparse
import functools
import operator
import re
from http import HTTPStatus
from pathlib import Path
from typing import Annotated, Any

import pydantic
from loguru import logger
from scrapling.fetchers import StealthyFetcher
from scrapling.parser import Selector


class ContributingOutcome(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(arbitrary_types_allowed=True)

    content: Selector = pydantic.Field(exclude=True)

    @pydantic.computed_field()
    @functools.cached_property
    def heading(self) -> str:
        tag = self.content.find("h3")
        if tag is None:
            logger.warning("Unable to determine contributing outcome heading")
            return "error determining contributing outcome heading"
        return tag.get_all_text(strip=True)

    @pydantic.computed_field()
    @functools.cached_property
    def details(self) -> list[str]:
        details_tags = self.content.below_elements.filter(lambda p: p.tag in ("p", "em"))
        if not details_tags:
            logger.warning("Unable to determine contributing outcome details")
            return ["error determining contributing outcome details"]

        return list(filter(None, [details_tag.get_all_text(strip=True) for details_tag in details_tags]))

    class IGPCol(pydantic.BaseModel):
        heading: str
        subheading: str
        controls: list[str]

        @pydantic.model_serializer(mode="wrap")
        def serialize_md(self, handler, info) -> Any:  # type: ignore[no-untyped-def] # noqa: ANN001, ANN401
            # Check if 'format' is set to 'md' in the context
            if info.context and info.context.get("format") == "md":
                controls_md = "\n".join([f"- {x}" for x in self.controls])
                return f"""
{self.heading} - _{self.subheading}_

{controls_md}

"""
            # Fallback to standard behavior (dict or JSON)
            return handler(self)

    @pydantic.computed_field()
    @functools.cached_property
    def igps(self) -> list[IGPCol]:
        table_tag = self.content.find("table")
        if table_tag is None:
            logger.warning("Unable to determine contributing outcome IGP table")
            return []

        # the table is really three lists, as rows of controls have no relation
        tr_tags = table_tag.find_all("tr")

        # tables are currently presented with three rows
        # to somewhat future-proof, throw an exception if this changes
        expected_num_rows = 3
        if len(tr_tags) != expected_num_rows:
            msg = "Extraction only support three row igp tables."
            raise NotImplementedError(msg)

        # column headers
        # this is expected to be:
        #   'achieved' &
        #   'not achieved'
        headings = [th_tag.get_all_text(strip=True) for th_tag in tr_tags[0].find_all("th")]

        # column subheaders
        # this is expected to be:
        #   'At least one of the following statements is true' &
        #   'All the following statements are true'
        subheadings = [td_tag.get_all_text(strip=True) for td_tag in tr_tags[1].find_all("td")]

        # controls of a single column are grouped in a single td tag, separated individually by p tags
        td_tags = tr_tags[-1].find_all("td")
        controls = [
            list(filter(None, [str(p_tag.get_all_text(strip=True)) for p_tag in td_tag.find_all("p")]))
            for td_tag in td_tags
        ]

        return [
            self.IGPCol(heading=heading, subheading=subheading, controls=controls)
            for heading, subheading, controls in zip(headings, subheadings, controls, strict=True)
        ]

    @pydantic.model_serializer(mode="wrap")
    def serialize_md(self, handler, info) -> Any:  # type: ignore[no-untyped-def] # noqa: ANN001, ANN401
        # Check if 'format' is set to 'md' in the context
        if info.context and info.context.get("format") == "md":
            igps_md = "\n".join([str(x.model_dump(context=info.context)) for x in self.igps])
            return f"""
__{self.heading}__
{"\n".join([f"- {detail}" for detail in self.details])}

{igps_md}

"""
        # Fallback to standard behavior (dict or JSON)
        return handler(self)


class Principle(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(arbitrary_types_allowed=True)

    link: Annotated[str, "URL"]

    @pydantic.computed_field(alias="html_content", repr=False)
    @functools.cached_property
    def content(self) -> Selector:
        page = StealthyFetcher.fetch(str(self.link), headless=True, network_idle=True)
        if page.status == HTTPStatus.NOT_FOUND:
            logger.error(f"URL {self.link} returned a HTTPStatus.NOT_FOUND response code, so will not be parsed.")
            return Selector("")
        return page

    @pydantic.field_serializer("content")
    def serialize_content(self, _: Selector) -> None:
        """The content field is not serializable, so this serializer returns None to exclude it from the JSON output."""

    @pydantic.computed_field()
    @functools.cached_property
    def heading(self) -> str:
        tag = self.content.find("h2", {"class": "h1 mb-0"})
        if tag is None:
            logger.warning(f"Unable to determine heading for {self.link}")
            return "error determining heading"
        return tag.get_all_text(strip=True)

    @pydantic.computed_field()
    @functools.cached_property
    def principle(self) -> list[str]:
        principle_section = self.content.find(
            "section",
            lambda s: s.attrib.get("data-js-jumplinks-section-label", "").strip() == "Principle",
        )
        if principle_section is None:
            logger.warning(f"Unable to determine principle for {self.link}")
            return ["error determining principle"]

        p_tags = principle_section.find_all("p")
        if not p_tags:
            logger.warning(f"Unable to find any paragraph tags in the Principle section for {self.link}")
            return ["error determining principle"]

        return list(filter(None, [p_tag.get_all_text(strip=True) for p_tag in p_tags]))

    @pydantic.computed_field()
    @functools.cached_property
    def description(self) -> list[str]:
        description_section = self.content.find(
            "section",
            lambda s: s.attrib.get("data-js-jumplinks-section-label", "").strip() == "Description",
        )
        if description_section is None:
            logger.warning(f"Unable to determine description for {self.link}")
            return ["error determining description"]

        p_tags = description_section.find_all("p")
        if not p_tags:
            logger.warning(f"Unable to find any paragraph tags in the Description section for {self.link}")
            return ["error determining description"]

        return list(filter(None, [p_tag.get_all_text(strip=True) for p_tag in p_tags]))

    @pydantic.computed_field()
    @functools.cached_property
    def guidance(self) -> list[str]:
        guidance_section = self.content.find(
            "section",
            lambda s: s.attrib.get("data-js-jumplinks-section-label", "").strip() == "Guidance",
        )
        if guidance_section is None:
            logger.warning(f"Unable to determine guidance for {self.link}")
            return ["error determining guidance"]

        guidance_articles = [guidance_section]

        next_guidance_article = guidance_section.below_elements.search(
            lambda p: p.tag == "li" and "flex" in p.attrib.get("class", "").split(),
        )

        while (next_guidance_article is not None) and (not next_guidance_article.find("table")):
            guidance_articles.append(next_guidance_article)
            next_guidance_article = next_guidance_article.below_elements.search(
                lambda p: p.tag == "li" and "flex" in p.attrib.get("class", "").split(),
            )

        p_tags: list[Selector] = functools.reduce(
            operator.iconcat,
            [
                guidance_article.find_all(
                    "p",
                )
                for guidance_article in guidance_articles
            ],
            list[Selector](),
        )
        if not p_tags:
            logger.warning(f"Unable to determine guidance for {self.link}")
            return ["error determining guidance"]

        return list(filter(None, [p_tag.get_all_text(strip=True) for p_tag in p_tags]))

    @pydantic.computed_field()
    @functools.cached_property
    def contributing_outcomes(self) -> list[ContributingOutcome]:
        # The contributing outcomes are presented in div tags with class "c-wysiwyg"
        # Contributing outcomes are always accompanied with a indicator of good practice (IGP) table
        # so this is used to for selection
        tags: list[Selector] = self.content.find_all(
            "div",
            {
                "class": "c-wysiwyg",
            },
        )
        tags = list(
            filter(
                lambda tag: (
                    tag.find(
                        "table",
                    )
                    is not None
                ),
                tags[:],
            ),
        )

        if not tags:
            logger.warning(f"Unable to determine contributing outcomes for {self.link}")
            return []

        return [ContributingOutcome(content=tag) for tag in tags]

    @pydantic.model_serializer(mode="wrap")
    def serialize_md(self, handler, info) -> Any:  # type: ignore[no-untyped-def] # noqa: ANN001, ANN401
        # Check if 'format' is set to 'md' in the context
        if info.context and info.context.get("format") == "md":
            base_indentation = 5
            contributing_outcomes_md = "\n\n".join(
                [str(x.model_dump(context=info.context)) for x in self.contributing_outcomes],
            )
            return f"""
{base_indentation * "#"} [{self.heading}]({self.link})

{"\n\n".join(self.principle)}

{(base_indentation + 1) * "#"} Description

{"\n\n".join(self.description)}

{(base_indentation + 1) * "#"} Guidance

{"\n\n".join(self.guidance)}

{(base_indentation + 1) * "#"} Contributing Outcomes

{contributing_outcomes_md}

"""
        # Fallback to standard behavior (dict or JSON)
        return handler(self)


class Objective(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(arbitrary_types_allowed=True)

    link: Annotated[str, "URL"]

    @pydantic.computed_field(alias="html_content", repr=False)
    @functools.cached_property
    def content(self) -> Selector:
        page = StealthyFetcher.fetch(str(self.link), headless=True, network_idle=True)
        if page.status == HTTPStatus.NOT_FOUND:
            logger.error(f"URL {self.link} returned a HTTPStatus.NOT_FOUND response code, so will not be parsed.")
            return Selector("")
        return page

    @pydantic.field_serializer("content")
    def serialize_content(self, _: Selector) -> None:
        """The content field is not serializable, so this serializer returns None to exclude it from the JSON output."""

    @pydantic.computed_field()
    @functools.cached_property
    def heading(self) -> str:
        tag = self.content.find("h2", {"class": "h1 mb-0"})
        if tag is None:
            logger.warning(f"Unable to determine heading for {self.link}")
            return "error determining heading"
        return tag.get_all_text(strip=True)

    @pydantic.computed_field()
    @functools.cached_property
    def principles(self) -> list[Principle]:
        logger.info(f"Getting CAF Objective Principle links from {self.link}")

        page = StealthyFetcher.fetch(self.link, headless=True, network_idle=True)
        if page.status == HTTPStatus.NOT_FOUND:
            logger.error(f"URL {self.link} returned a HTTPStatus.NOT_FOUND response code, so will not be parsed.")
            return []

        a_tags: list[Selector] = page.css("a[href]")
        principle_links: list[str] = [
            tag.urljoin(tag.attrib.get("href")) for tag in a_tags if "principle" in tag.attrib.get("href")
        ]
        principle_links.sort()
        logger.info(f"Got CAF Objective Principle links: {principle_links}")
        return [Principle(link=link) for link in principle_links]

    @pydantic.model_serializer(mode="wrap")
    def serialize_md(self, handler, info) -> Any:  # type: ignore[no-untyped-def] # noqa: ANN001, ANN401
        # Check if 'format' is set to 'md' in the context
        if info.context and info.context.get("format") == "md":
            base_indentation = 3
            principles_md = "\n\n".join([str(x.model_dump(context=info.context)) for x in self.principles])
            return f"""
{base_indentation * "#"} [{self.heading}]({self.link})

{(base_indentation + 1) * "#"} Principles

{principles_md}

"""

        # Fallback to standard behavior (dict or JSON)
        return handler(self)


class CAF(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(arbitrary_types_allowed=True)

    base: Annotated[str, "URL"] = pydantic.Field(
        default="https://www.ncsc.gov.uk/collection/cyber-assessment-framework",
    )

    @pydantic.computed_field(alias="html_content", repr=False)
    @functools.cached_property
    def content(self) -> Selector:
        page = StealthyFetcher.fetch(str(self.base), headless=True, network_idle=True)
        if page.status == HTTPStatus.NOT_FOUND:
            logger.error(f"URL {self.base} returned a HTTPStatus.NOT_FOUND response code, so will not be parsed.")
            return Selector("")
        return page

    @pydantic.field_serializer("content")
    def serialize_content(self, _: Selector) -> None:
        """The content field is not serializable, so this serializer returns None to exclude it from the JSON output."""

    @pydantic.computed_field()
    @functools.cached_property
    def version(self) -> str:
        sidebar_tag = self.content.css("div[class=c-layout-sidebar-bottom]")

        if sidebar_tag is None or sidebar_tag.first is None:
            logger.warning("Unable to determine CAF version")
            return "error determining CAF version"

        version_heading_tag = sidebar_tag.first.find("h4", lambda h: h.get_all_text(strip=True) == "Version")
        if version_heading_tag is None or version_heading_tag.parent is None:
            logger.warning("Unable to determine CAF version")
            return "error determining CAF version"

        # version number is the text of the parent div
        # as it doesn't have it's own tag, extract all test, and get the final one (expected to be the version number)
        return version_heading_tag.parent.css("::text").getall()[-1]

    @pydantic.computed_field()
    @functools.cached_property
    def published(self) -> str:
        sidebar_tag = self.content.css("div[class=c-layout-sidebar-bottom]")

        if sidebar_tag is None or sidebar_tag.first is None:
            logger.warning("Unable to determine CAF Published Date")
            return "error determining CAF published date"

        published_heading_tag = sidebar_tag.first.find("h4", lambda h: h.get_all_text(strip=True) == "Published")
        if published_heading_tag is None or published_heading_tag.parent is None:
            logger.warning("Unable to determine CAF published date")
            return "error determining CAF published date"

        published_time_tag = published_heading_tag.parent.find("time")
        if published_time_tag is None:
            logger.warning("Unable to determine CAF published date")
            return "error determining CAF published date"

        return published_time_tag.get_all_text(strip=True)

    @pydantic.computed_field()
    @functools.cached_property
    def reviewed(self) -> str:
        sidebar_tag = self.content.css("div[class=c-layout-sidebar-bottom]")

        if sidebar_tag is None or sidebar_tag.first is None:
            logger.warning("Unable to determine CAF Published Date")
            return "error determining CAF published date"

        reviewed_heading_tag = sidebar_tag.first.find("h4", lambda h: h.get_all_text(strip=True) == "Reviewed")
        if reviewed_heading_tag is None or reviewed_heading_tag.parent is None:
            logger.warning("Unable to determine CAF reviewed date")
            return "error determining CAF reviewed date"

        reviewed_time_tag = reviewed_heading_tag.parent.find("time")
        if reviewed_time_tag is None:
            logger.warning("Unable to determine CAF reviewed date")
            return "error determining CAF reviewed date"

        return reviewed_time_tag.get_all_text(strip=True)

    @pydantic.computed_field()
    @functools.cached_property
    def objectives(self) -> list[Objective]:
        logger.info(f"Getting CAF Objective links from {self.base}")
        a_tags: list[Selector] = self.content.css("a[href]")
        links: list[str] = [tag.urljoin(tag.attrib.get("href")) for tag in a_tags]
        objective_links: list[str] = list(
            filter(lambda link: (link is not None) and ("objective" in link) and ("principle" not in link), links),
        )
        objective_links.sort()
        logger.info(f"Got CAF Objective links: {objective_links}")
        return [Objective(link=link) for link in objective_links]

    @pydantic.model_serializer(mode="wrap")
    def serialize_md(self, handler, info) -> Any:  # type: ignore[no-untyped-def] # noqa: ANN001, ANN401
        # Check if 'format' is set to 'md' in the context
        if info.context and info.context.get("format") == "md":
            base_indentation = 1
            objectives_md = "\n\n".join(str(x.model_dump(context=info.context)) for x in self.objectives)
            return f"""
{base_indentation * "#"} [NCSC CAF]({self.base})

Version: {self.version}
Published: {self.published}
Reviewed: {self.reviewed}

{(base_indentation + 1) * "#"} Objectives

{objectives_md}

"""

        # Fallback to standard behavior (dict or JSON)
        return handler(self)


def main(output_filename_stem: Path) -> None:

    ncsc_caf_homepage_link: Annotated[str, "URL"] = "https://www.ncsc.gov.uk/collection/cyber-assessment-framework"
    logger.info(f"Reading: {ncsc_caf_homepage_link}")

    caf = CAF(base=ncsc_caf_homepage_link)

    character_replacements = {
        r"\u202f": " ",  # narror space -> regular space
        r"\u2019": "'",  # right single quotation mark -> apostrophe
        r"\n": " ",  # literal newlines -> regular space
    }
    character_replacements = {re.escape(k): v for k, v in character_replacements.items()}
    pattern = re.compile("|".join(character_replacements.keys()))

    with Path.open(output_filename_stem.with_suffix(".json"), "w", encoding="utf-8") as fd:
        json = caf.model_dump_json(indent=2)
        json = pattern.sub(lambda m: character_replacements[re.escape(m.group(0))], json)
        fd.write(json)

    with Path.open(output_filename_stem.with_suffix(".md"), "w", encoding="utf-8") as fd:
        md = str(caf.model_dump(context={"format": "md"}))
        fd.write(md)

    logger.info(
        f"Completed scraping: see {output_filename_stem.with_suffix('.json')}, {output_filename_stem.with_suffix('.md')}, and {output_filename_stem.with_suffix('.log')}",
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Scrape the NCSC CAF site, and extract the relevant information, presenting it as a structured JSON document.",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="""The output file name without an extension (stem).
                        This is used to produce an <output>.json, <output>.md, and an <output>.log.
                        Defaults to 'output'.""",
        default="output",
    )
    args = parser.parse_args()
    try:
        logger.add(Path(args.output + ".log"))
        main(Path(args.output))
    except Exception as exc:
        logger.error(exc)
        raise
