# Web Scraping and Data Management Project

## Overview

This project is a Python-based web scraping tool designed to extract and manage data from a specified website. The tool efficiently scrapes URLs, extracts detailed information from individual pages, stores the data in an SQLite database, and exports the data to a CSV file. The script uses multi-threading to enhance performance and handle large volumes of data efficiently.

## Features

- **Multi-threaded URL Scraping**: Quickly scrape large numbers of URLs based on specified parameters.
- **Detailed Page Scraping**: Extract detailed information from individual pages, including company details, revenue, management, etc.
- **SQLite Database Integration**: Store and manage scraped data in an SQLite database.
- **Data Export to CSV**: Convert the stored data into a CSV file for easy access and analysis.
- **Robust Error Handling**: Handles exceptions and errors gracefully to ensure continuous operation.

## Prerequisites

- **Python 3.7+**
- **Required Python Libraries**:
  - `requests`
  - `pandas`
  - `dataset`
  - `beautifulsoup4`
  - `concurrent.futures`
  - `re`
  - `json`
  - `os`
  - `time`
  - `traceback`

To install the required libraries, run the following command:

```bash
pip install requests pandas dataset beautifulsoup4

```
## Project Structure
-----------------

-   **`ScrapeUrl(headers, internal_params, legal_form, name_letter, i)`**:\
    Scrapes company URLs based on the provided parameters and stores them in a list of dictionaries.

-   **`store_data_in_db(Main_list, database, databaseTable)`**:\
    Inserts or updates the scraped data in an SQLite database.

-   **`threadingScrapeUrl(database, databaseTable)`**:\
    Manages multi-threaded scraping of URLs and stores the results in the database.

-   **`read_db_to_dict_list(table)`**:\
    Reads unscraped entries from the database and converts them into a list of dictionaries.

-   **`retriveIndividualPages(obj1, index)`**:\
    Scrapes detailed information from individual company pages and returns the data as a dictionary.

-   **`threadingIndividualPages(ScrapedData, Scrapedtable, UpdatedTable)`**:\
    Manages multi-threaded scraping of individual company pages and updates the database with detailed information.

-   **`sql_table_to_csv(UpdatedTable, csv_file_path)`**:\
    Exports the data from the SQLite database table to a CSV file.

-   **`main()`**:\
    The main entry point of the script that coordinates the entire scraping and data export process.

## How to Run
----------

### 1.  **Initial Setup**:

    -   Ensure all required Python libraries are installed.
    -   Place the script in your project directory.
### 2.  **Run the Script**:

    -   Simply execute the `main()` function by running the script.

    bash

    Copy code

    `python your_script_name.py`

### 3.  **Data Output**:

    -   The script will generate an SQLite database (`ScrapedData.db`) containing the scraped URLs and detailed company data.
    -   A final CSV file (`FinalDataDB.csv`) will be generated with all the detailed information extracted from the individual company pages.