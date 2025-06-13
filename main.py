# mypy: disable-error-code="prop-decorator"

import argparse
import functools
import itertools
import json
import re
from collections.abc import Hashable
from http import HTTPStatus
from pathlib import Path
from typing import Annotated, Any

import httpx
import jsbeautifier
import pandas as pd
import pydantic
import selenium
import selenium.common.exceptions
import selenium.webdriver.common
import selenium.webdriver.common.by
import selenium.webdriver.firefox.options
import selenium.webdriver.firefox.service
import selenium.webdriver.remote.webdriver
import selenium.webdriver.support.expected_conditions
import selenium.webdriver.support.wait
from bs4 import BeautifulSoup, element
from loguru import logger

driver_get_timeout_duration: float = 10.0


def get_caf_objective_links(base: httpx.URL) -> list[httpx.URL]:
    logger.info(f"Getting CAF Objective links from {base}")

    response = httpx.get(base)
    if response.status_code == HTTPStatus.NOT_FOUND:
        logger.error(f"URL {base} returned a HTTPStatus.NOT_FOUND response code, so will not be parsed.")
        return []

    driver.get(str(base))

    try:
        selenium.webdriver.support.wait.WebDriverWait(driver, driver_get_timeout_duration).until(
            selenium.webdriver.support.expected_conditions.visibility_of_element_located(
                (selenium.webdriver.common.by.By.CSS_SELECTOR, "a[href*='objective']"),
            ),
        )
    except selenium.common.exceptions.TimeoutException:
        logger.error(f"Timeout on element based page source get for {base}. Page source may be incomplete.")

    page = driver.page_source
    soup = BeautifulSoup(page, "html.parser")
    a_tags = soup.find_all("a", href=True)
    objective_links = [base.join(link.attrs.get("href")) for link in a_tags if "objective" in link.get("href")]
    objective_links.sort(key=lambda x: str(x.raw_path))
    logger.info(f"Got CAF Objective links: {objective_links}")
    return objective_links


def get_caf_principle_links(objective: httpx.URL) -> list[httpx.URL]:
    logger.info(f"Getting CAF Objective Principle links from {objective}")

    response = httpx.get(objective)
    if response.status_code == HTTPStatus.NOT_FOUND:
        logger.error(f"URL {objective} returned a HTTPStatus.NOT_FOUND response code, so will not be parsed.")
        return []

    driver.get(str(objective))
    try:
        selenium.webdriver.support.wait.WebDriverWait(driver, driver_get_timeout_duration).until(
            selenium.webdriver.support.expected_conditions.visibility_of_element_located(
                (selenium.webdriver.common.by.By.CSS_SELECTOR, "a[href*='principle']"),
            ),
        )
    except selenium.common.exceptions.TimeoutException:
        logger.error(f"Timeout on element based page source get for {objective}. Page source may be incomplete.")

    page = driver.page_source
    soup = BeautifulSoup(page, "html.parser")
    a_tags = soup.find_all("a", href=True)
    principle_links = [objective.join(link.attrs.get("href")) for link in a_tags if "principle" in link.get("href")]
    principle_links.sort(key=lambda x: str(x.raw_path))
    logger.info(f"Got CAF Objective Principle links: {principle_links}")
    return principle_links


class Principle(pydantic.BaseModel):
    class Config:
        arbitrary_types_allowed = True

    link: Annotated[
        httpx.URL,
        pydantic.PlainSerializer(lambda x: str(x), return_type=str),
    ]

    @pydantic.computed_field(alias="soup", repr=False)
    @functools.cached_property
    def _content(self) -> BeautifulSoup:
        if httpx.get(self.link).status_code == HTTPStatus.NOT_FOUND:
            logger.error(f"URL {self.link} returned a HTTPStatus.NOT_FOUND response code, so will not be parsed.")
            return BeautifulSoup()

        driver.get(str(self.link))
        try:
            selenium.webdriver.support.wait.WebDriverWait(driver, driver_get_timeout_duration).until(
                selenium.webdriver.support.expected_conditions.presence_of_element_located(
                    (selenium.webdriver.common.by.By.TAG_NAME, "table"),
                ),
            )
        except selenium.common.exceptions.TimeoutException:
            logger.error(f"Timeout on element based page source get for {self.link}. Page source may be incomplete.")

        page = driver.page_source
        soup = BeautifulSoup(page, "html.parser")
        return soup

    @pydantic.field_serializer("_content")
    def serialize_content(self, _content: BeautifulSoup) -> str:
        return "You can't serialize soup!"

    @pydantic.computed_field()
    @functools.cached_property
    def heading(self) -> str:
        tag = self._content.find("h1", attrs={"class": "subHeading"})
        if tag is None:
            logger.warning(f"Unable to determine heading for {self.link}")
            return "error determining heading"
        return tag.get_text(strip=True)

    @pydantic.computed_field()
    @functools.cached_property
    def principle(self) -> list[str]:
        h2_tag = self._content.find("h2", string=re.compile(r"\s*Principle\s*"))
        if h2_tag is None:
            logger.warning(f"Unable to determine principle for {self.link}")
            return ["error determining principle"]

        h2_tag_parent = h2_tag.parent
        if h2_tag_parent is None:
            logger.warning(f"Unable to determine principle for {self.link}")
            return ["error determining principle"]

        p_tags = h2_tag_parent.find_all("p")
        if not p_tags:
            logger.warning(f"Unable to determine principle for {self.link}")
            return ["error determining principle"]

        return [p_tag.get_text(strip=True) for p_tag in p_tags]

    @pydantic.computed_field()
    @functools.cached_property
    def description(self) -> list[str]:
        h2_tag = self._content.find(
            "h2",
            string=re.compile(r"\s*Description\s*"),
        )
        if h2_tag is None:
            logger.warning(f"Unable to determine description for {self.link}")
            return ["error determining description"]

        h2_tag_parent = h2_tag.parent
        if h2_tag_parent is None:
            logger.warning(f"Unable to determine description for {self.link}")
            return ["error determining description"]

        p_tags = h2_tag_parent.find_all("p")
        if not p_tags:
            logger.warning(f"Unable to determine description for {self.link}")
            return ["error determining description"]

        return [p_tag.get_text(strip=True) for p_tag in p_tags]

    @pydantic.computed_field()
    @functools.cached_property
    def guidance(self) -> list[str]:
        h2_tag = self._content.find("h2", string=re.compile(r"\s*Guidance\s*"))
        if h2_tag is None:
            logger.warning(f"Unable to determine guidance for {self.link}")
            return ["error determining guidance"]

        h2_tag_parent = h2_tag.parent
        if h2_tag_parent is None:
            logger.warning(f"Unable to determine guidance for {self.link}")
            return ["error determining guidance"]

        p_tags = h2_tag_parent.find_all("p")
        if not p_tags:
            logger.warning(f"Unable to determine guidance for {self.link}")
            return ["error determining guidance"]

        return [p_tag.get_text(strip=True) for p_tag in p_tags]

    @pydantic.computed_field()
    @functools.cached_property
    def pcfs(self) -> list[tuple[str, list[str], pd.DataFrame]]:
        pcf_tags = self._content.find_all(
            "div",
            attrs={
                "class": "pcf-BodyText",
            },
        )
        filtered_pcf_tags = list(
            filter(
                lambda tag: tag.find(
                    "table",
                )
                is not None,
                pcf_tags[:],
            ),
        )

        if not filtered_pcf_tags:
            logger.warning(f"Unable to determine pcfs for {self.link}")
            return []

        pcfs = []
        for pcf_tag in filtered_pcf_tags:
            pcf_heading_tag = pcf_tag.find("h3")
            if pcf_heading_tag is None:
                logger.warning(f"Unable to determine guidance for {self.link}")
                pcf_heading = "error determining pcf heading"
            else:
                pcf_heading = pcf_heading_tag.get_text(strip=True)

            pcf_detail_tags = pcf_tag.find_all("em")
            if not pcf_detail_tags:
                logger.warning(f"Unable to determine pcf details for {self.link}")
                pcf_details = ["error determining guidance"]
            else:
                pcf_details = [pcf_detail_tag.get_text(strip=True) for pcf_detail_tag in pcf_detail_tags]

            pcf_table_df = self.extract_pcf_table(pcf_tag.find("table"))
            pcfs.append(
                (pcf_heading, pcf_details, pcf_table_df),
            )

        return pcfs

    def extract_pcf_table(self, table_tag: element.Tag) -> pd.DataFrame:
        tr_tags = table_tag.find_all("tr")

        # tables are currently presented with three rows
        # to somewhat future-proof, throw an exception if this changes
        expected_num_rows = 3
        if len(tr_tags) != expected_num_rows:
            msg = "Extraction only support three row pcf tables."
            raise NotImplementedError(msg)

        # column headers
        # this is expected to be:
        #   'achieved' &
        #   'not achieved'
        columns = [th_tag.get_text(strip=True) for th_tag in tr_tags[0].find_all("th")]

        # 2D list/table
        table: list[tuple[str, ...]] = []

        # column subheaders
        # this is expected to be:
        #   'At least one of the following statements is true' &
        #   'All the following statements are true'
        table.append(tuple(td_tag.get_text(strip=True) for td_tag in tr_tags[1].find_all("td")))

        # controls of a single column are grouped in a single td tag, separated individually by p tags
        td_tags = tr_tags[-1].find_all("td")
        p_texts = [[p_tag.get_text(strip=True) for p_tag in td_tag.find_all("p")] for td_tag in td_tags]
        table.extend(itertools.zip_longest(*p_texts))

        # convert to dataframe
        df = pd.DataFrame(
            table,
            columns=columns,
        )

        return df

    @pydantic.field_serializer("pcfs")
    def serialize_pcfs(
        self,
        pcfs: list[tuple[str, list[str], pd.DataFrame]],
    ) -> list[tuple[str, list[str], dict[Hashable, Any]]]:
        return [(pcf[0], pcf[1], pcf[2].to_dict()) for pcf in pcfs]


class Objective(pydantic.BaseModel):
    class Config:
        arbitrary_types_allowed = True

    link: Annotated[
        httpx.URL,
        pydantic.PlainSerializer(lambda x: str(x), return_type=str),
    ]

    @pydantic.computed_field(alias="soup", repr=False)
    @functools.cached_property
    def _content(self) -> BeautifulSoup:
        if httpx.get(self.link).status_code == HTTPStatus.NOT_FOUND:
            logger.error(f"URL {self.link} returned a HTTPStatus.NOT_FOUND response code, so will not be parsed.")
            return BeautifulSoup()

        driver.get(str(self.link))
        try:
            selenium.webdriver.support.wait.WebDriverWait(driver, driver_get_timeout_duration).until(
                selenium.webdriver.support.expected_conditions.presence_of_element_located(
                    (selenium.webdriver.common.by.By.CLASS_NAME, "subHeading"),
                ),
            )
        except selenium.common.exceptions.TimeoutException:
            logger.error(f"Timeout on element based page source get for {self.link}. Page source may be incomplete.")

        page = driver.page_source
        soup = BeautifulSoup(page, "html.parser")
        return soup

    @pydantic.field_serializer("_content")
    def serialize_content(self, _content: BeautifulSoup) -> str:
        return "You can serialize soup!"

    @pydantic.computed_field()
    @functools.cached_property
    def heading(self) -> str:
        tag = self._content.find("h1", attrs={"class": "subHeading"})
        if tag is None:
            logger.warning(f"Unable to determine heading for {self.link}")
            return "error determining heading"
        return tag.text

    @pydantic.computed_field()
    @functools.cached_property
    def principles(self) -> list[Principle]:
        return [Principle(link=link) for link in get_caf_principle_links(self.link)]


def main(output_json_file: Path) -> None:
    ncsc_caf_homepage_link = httpx.URL(
        "https://www.ncsc.gov.uk/collection/cyber-assessment-framework",
    )
    logger.info(f"Reading: {ncsc_caf_homepage_link}")
    ncsc_caf_objectives_links: list[httpx.URL] = get_caf_objective_links(
        ncsc_caf_homepage_link,
    )

    objectives: list[Objective] = []
    for objective_link in ncsc_caf_objectives_links:
        objective = Objective(link=objective_link)
        objectives.append(objective)

    with Path.open(output_json_file, "w", encoding="utf-8") as fd:
        # This is preferred over model_dump_json() as it allows for the output str to be formatted for readability,
        # while still allowing pydantic to do the serialisation
        objective_models = [objective.model_dump() for objective in objectives]
        opts = jsbeautifier.default_options()
        opts.indent_size = 2
        opts.space_in_empty_paren = True
        objectives_json: str = jsbeautifier.beautify(
            json.dumps(objective_models),
            opts,
        )
        unicode_replacements = {
            r"\u202f": " ",  # narror space -> regular space
            r"\u2019": "'",  # right single quotation mark -> apostrophe
        }
        unicode_replacements = {re.escape(k): v for k, v in unicode_replacements.items()}
        pattern = re.compile("|".join(unicode_replacements.keys()))
        objectives_json = pattern.sub(lambda m: unicode_replacements[re.escape(m.group(0))], objectives_json)
        fd.write(objectives_json)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Scrape the NCSC CAF site, and extract the relevant information, presenting it as a structured JSON document.",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="""The output file name without an extension (stem).
                        This is used to produce an <output>.json and an <output>.log.
                        Defaults to 'output'.""",
        default="output",
    )
    args = parser.parse_args()
    try:
        logger.add(Path(args.output + ".log"))
        options = selenium.webdriver.firefox.options.Options()
        options.binary_location = r"/usr/bin/firefox-esr"
        options.add_argument("--headless")
        options.add_argument("--disable-gpu")  # required for M1 Macs
        service = selenium.webdriver.firefox.service.Service(
            executable_path="/usr/local/bin/geckodriver",
        )
        logger.info("Opening Webdriver session")
        driver = selenium.webdriver.Firefox(options=options, service=service)
        driver.implicitly_wait(10.0)
        main(Path(args.output + ".json"))
    except Exception as exc:
        logger.error(exc)
        raise
    finally:
        logger.info("Closing Webdriver session")
        driver.close()
