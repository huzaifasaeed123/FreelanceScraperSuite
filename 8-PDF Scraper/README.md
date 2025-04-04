# PDF Scraper for Monitorul Oficial Romania

**Automatically download official documents by date range.**

This powerful Python script automates the download of PDF documents from the Romanian official journal website, Monitorul Oficial (`https://monitoruloficial.ro/`). It provides a flexible way to scrape documents from a specific date range, saving them into organized folders based on their publication date.

## Features

* **Targeted Date Range:**  Download PDFs published between specified start and end dates.
* **Two PDF Formats:** Handles both simple and complex PDF layouts on the website.
* **Organized Storage:** Saves PDFs into folders named after their publication date.
* **Robust Scraping:**  Built-in error handling for a smooth experience.
* **Easy Customization:**  Quickly adjust the date range to your needs.

## How It Works

1. **Date Iteration:** The script iterates through each date within your chosen range.
2. **HTML Scraping:** It fetches the HTML for each date's page and extracts links to the PDFs.
3. **PDF Download:** Downloads both simple and complex PDFs, handling any potential layout differences.
4. **Organized Saving:** Creates folders based on date and saves each PDF in its respective folder.

## Usage

1. **Prerequisites:**
   * Python 3.x installed
   * `requests`, `beautifulsoup4`, `datetime`, `os`, and `re` libraries (Install using `pip install requests beautifulsoup4`)
2. **Configuration:**
   * Open the script file and modify the following variables:
     * `Start_Date1`:  Set your desired start date (YYYY-MM-DD format).
     * `End_Date1`: Set your desired end date (YYYY-MM-DD format).
3. **Run the Script:** Execute the Python script from your terminal.

**Example:**

```bash
python pdf_scraper.py
