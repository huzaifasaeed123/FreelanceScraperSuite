
# Web Scraper for UK Product Reviews

## Overview

This Python script is designed to scrape product review pages from specific websites, extract valuable data such as ratings, user reviews, and other metadata, and store the results in a local SQLite database. After processing the data, it exports the final information to an Excel file for further analysis.

## Features

1. **URL Scraping**: The script collects and stores product review URLs from a specified website.
2. **Review Extraction**: It scrapes various review metrics like "Ease of Use", "Customer Service", "Value for Money", etc.
3. **Database Storage**: All scraped data, including URLs, HTML content, and parsed review information, is stored in a local SQLite database.
4. **Data Export**: The final processed data is exported into an Excel file for further analysis.

## Components

- **`store_urls()`**: This function gathers and stores URLs of product pages.
- **`scrap_review_pages_url()`**: Scrapes the stored URLs and retrieves review page URLs, storing them in the database.
- **`store_html_content()`**: Scrapes and stores the HTML content of the review pages in the database.
- **`parse_all_pages(main_list, review_table)`**: Parses the HTML content, extracts relevant review information, and stores it in the database.
- **`table_to_excel(final_data, "Final_Data_UK.xlsx")`**: Converts the final dataset into an Excel file.

## Requirements

- Python 3.x
- The following Python libraries are required:
  - `requests`
  - `beautifulsoup4`
  - `dataset`
  - `pandas`
  - `openpyxl`

Install the required libraries using:
```
pip install requests beautifulsoup4 dataset pandas openpyxl
```

## Usage

1. **Initialize Database**: The SQLite database `webpages_uk.db` is used to store the scraped URLs, HTML content, and the final processed review data.
2. **Run the Script**: The script will:
   - Scrape product URLs.
   - Scrape review page URLs.
   - Scrape and store review data.
   - Parse the stored review data.
   - Export the final data to an Excel file named `Final_Data_UK.xlsx`.

3. **Final Output**: The processed review data, including metrics like ease of use, customer service ratings, etc., will be available in the Excel file.

## Steps to Execute

1. Ensure all the necessary libraries are installed.
2. Run the script:
```
python mainfile_uk.py
```
3. After execution, check the `Final_Data_UK.xlsx` file for the final data.

## License

This project is licensed under the MIT License.
