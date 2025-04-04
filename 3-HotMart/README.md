
# HotMart Web Scraping Project

This project scrapes product details and emails from the HotMart ecommerce website. It retrieves data such as product names, categories, and email addresses, which are then stored in a database and exported to CSV or Excel files. The scraping process is optimized using multithreading for efficient handling of multiple product URLs simultaneously.

## Features

- **Multithreading**: Uses Python's `ThreadPoolExecutor` to scrape multiple pages concurrently for faster performance.
- **Proxy Support**: Easily configurable proxy to avoid rate limiting or IP blocks.
- **Data Export**: Exports scraped data to CSV and Excel files.
- **Error Handling**: Captures errors and maintains a list of URLs that could not be scraped.
- **Email Extraction**: Extracts emails from product pages using regex.

## Requirements

- Python 3.x
- Internet connection
- A HotMart account to access product URLs (if needed)

## Installation

1. Clone the repository:

   ```bash
   git clone https://github.com/your-username/HotMart-Web-Scraper.git
   cd HotMart-Web-Scraper
   ```

2. Install the required dependencies:

   ```bash
   pip install -r requirements.txt
   ```

   **Note**: Ensure you have installed the required libraries such as `requests`, `beautifulsoup4`, `dataset`, `alive-progress`, `pandas`, and `concurrent.futures`.

   Sample `requirements.txt`:

   ```bash
   requests
   beautifulsoup4
   dataset
   pandas
   alive-progress
   ```

3. (Optional) If you are scraping from behind a proxy, configure your proxy in the `proxy` variable within the script:

   ```python
   proxy = {
       "http": "http://your-proxy-address:port",
       "https": "http://your-proxy-address:port",
   }
   ```

## Usage

1. **Add URLs to Scrape**:

   You can either:
   - Extract URLs directly from the HotMart sitemap using the `download_and_parse_all_xml()` function, or
   - Load URLs from a text file using the `extract_urls_from_file()` function.

   Each line of the text file should contain a valid HotMart product URL. For example:

   ```
   https://hotmart.com/es/marketplace/productos/seminariosonline/G7457141A
   ```

2. **Run the Scraper**:

   The main script will perform the following actions:
   - Scrape the product details and emails from each URL.
   - Save the data into a SQLite database (`HotMartMissing.db`).
   - Export the final data to both CSV and Excel files.

   Run the script as follows:

   ```bash
   python hotmart.py
   ```

3. **Output**:

   - Data will be saved in the `FinalData` table of `HotMartMissing.db`.
   - Two files will be generated:
     - `HotMartMissing.csv`: A CSV file containing the scraped data.
     - `HotMartMissing.xlsx`: An Excel file containing the scraped data.
   - A text file `Missing2.txt` will be created containing URLs that could not be scraped.

## Functions

- **`differentiate_urls(url)`**: Identifies category levels in the URL structure.
- **`retrive_page(url, index, bar)`**: Scrapes the product details and emails from a single HotMart URL.
- **`Threading_Page_Urls(PageUrlsData)`**: Handles multithreaded scraping of multiple URLs.
- **`download_and_parse_all_xml()`**: Downloads and parses sitemap XML files to extract product URLs.
- **`export_table_to_csv_and_excel(db_table, common_filename)`**: Exports scraped data from the database to CSV and Excel files.
- **`extract_urls_from_file(filename)`**: Reads product URLs from a text file.
- **`final_updation_inDB(UpdatedTable, list)`**: Inserts scraped data into the SQLite database.
- **`create_Missing_txt(output_file, urls)`**: Saves URLs that failed to scrape into a text file.

## Example

After running the script, the following output is expected in the terminal:

```
Processing Sitemap Xml File ::https://hotmart.com/product-page/public/sitemap/ae6b0e92-a8c1-40d1-92ed-28d4bbc5b603/sitemap_page_1.xml
Page Threading Reached at 1
Page Threading Reached at 2
...
Data successfully exported to HotMartMissing.csv (UTF-8)
Data successfully exported to HotMartMissing.xlsx
```

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for more details.

## Contributing

Feel free to contribute by submitting a pull request. Please ensure your code adheres to Python’s PEP 8 standards by using formatters like `black`.

---

## Troubleshooting

- **Proxy Issues**: If you're using a proxy and facing issues, ensure the proxy is properly configured and reachable.
- **Connection Timeout**: If scraping is slow or intermittent, you might need to add time delays or handle potential connection issues.
- **Missing Data**: Check the `Missing2.txt` file to identify the URLs that could not be scraped. You can retry these URLs later.

