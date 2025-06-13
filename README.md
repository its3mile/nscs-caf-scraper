# NCSC CAF Scraper

## Introduction
The [National Cyber Security Centre (NCSC)](https://www.ncsc.gov.uk/) develops and publishes a resource called the [Cyber Assessment Framework (CAF)](https://www.ncsc.gov.uk/collection/cyber-assessment-framework). 


From NSCF CAF site: _It is aimed at helping an organisation achieve and demonstrate an appropriate level of cyber resilience in relation to certain specified vitally important functions performed by that organisation, functions that are at risk of disruption as a result of a serious cyber incident._

The CAF is provided as a PDF documents for download, however it is not simple to assess against, often requiring organisations to purchase additional resources to support their assessment, or produce their own assessment sheets, often with errors. 

This project scrapes the NCSC CAF site, and extracts the relevant information, presenting it as a structured JSON document. Bespoke, post-processing using this JSON document can then be applied to render the CAF as desired.

## Usage
This project makes use of both Dev containers and poetry for environment management. Simply building the Dev container using the [VS Code Dev container extension](vscode:extension/ms-vscode-remote.remote-containers) is sufficient to get started.

Running `python3 main.py` or using the VS Code launch configuration `Python Debugger: ncsc-caf-scraper` is all that is required to produce some output. The resultant output.json is created at the project root directory.

## Caveats
- HTML scraping is fragile. There is no guarantee that updates to the NCSC CAF site won't completely change the format of the page, resulting in this project being obsoleted.

- The HTML is scraped as opposed to the PDF, as a review of the PDF has shown poor repeatability in the formatting, making it difficult to automate the data extraction. This project relies on the structured nature of HTML to provide better consistency, and therefore reliability, in data extraction.

