
# Web Scraper for Bradley Caldwell Products

This project is a **web scraper** designed to scrape product data from Bradley Caldwell's website. It uses various libraries such as `requests`, `BeautifulSoup`, `selenium`, and `pandas` to extract product details like prices, item descriptions, and quantities, and stores the data in both CSV and Excel formats.

## Features

- Scrapes product URLs from Bradley Caldwell's sitemap.
- Logs into the website using Selenium to bypass authentication.
- Extracts product details like ID, manufacturer number, prices, and availability.
- Saves scraped data into a SQLite database.
- Exports the final scraped data into CSV and Excel files.

## Technologies

- **Python 3.x**
- **Selenium** for web automation.
- **Requests** for fetching the sitemap.
- **BeautifulSoup** and **Parsel** for parsing HTML.
- **SQLite** via **dataset** library for storing intermediate data.
- **Pandas** for creating CSV and Excel reports.

## Prerequisites

Make sure you have the following installed on your system:

- Python 3.x
- Pip (Python package installer)
- Google Chrome or Chromium (for Selenium)
- [Chromedriver](https://sites.google.com/a/chromium.org/chromedriver/downloads) for Selenium, matching your Chrome version

You can install the required Python packages by running:

```bash
pip install -r requirements.txt
```

### `requirements.txt` file:
```
requests
parsel
beautifulsoup4
dataset
loguru
seleniumbase
pandas
```

## Setup

1. Clone this repository:

   ```bash
   git clone https://github.com/yourusername/bradley-caldwell-scraper.git
   cd bradley-caldwell-scraper
   ```

2. Install the necessary dependencies using:

   ```bash
   pip install -r requirements.txt
   ```

3. Ensure you have the correct version of **ChromeDriver** matching your browser version.

## Usage

1. **Login to the Website**

   The scraper requires logging into the Bradley Caldwell website to access product data. Ensure you have valid login credentials in the code. Modify these lines in the code to use your actual credentials:

   ```python
   driver.find_element(By.ID, "side-login-1").send_keys("your-email@example.com")
   driver.find_element(By.ID, "side-login-2").send_keys("your-password")
   ```

2. **Run the Scraper**

   Run the Python script:

   ```bash
   python scraper.py
   ```

   - The scraper will first check if the SQLite database exists, and if not, it will start scraping URLs from the sitemap.
   - Then, it will loop through each product URL, retrieve data, and save it into the database.
   - Finally, the product data is exported to `BradelyData.csv` and `BradelyData.xlsx`.

3. **Monitor the Logs**

   The script uses `loguru` for logging. Logs will be printed to the console and can be used to track progress or debug issues.

## Output

Once the scraper finishes running, it will output two files:

- **BradelyData.csv**: Contains all the scraped product data in CSV format.
- **BradelyData.xlsx**: Contains the same data in Excel format.

The data includes the following fields:

- `URL`: The product's URL.
- `BCI`: Product ID.
- `MFG`: Manufacturer Item Number.
- `UPC`: UPC Code.
- `Qty`: Quantity.
- `Description`: Full product description.
- `Retail`, `Dealer`, `Show`: Pricing details.
- `Total_Retail`, `Total_Dealer`, `Total_Show`: Total cost per order.
- Additional information like `Maximum Order Quantity`, `Type`, `Size`, `Case Pack`, `Pallet Quantity`, and `Quantity on Hand`.

## Potential Issues

- **IP Blocking**: Running this script too frequently or scraping too aggressively may result in IP blocking. To avoid this, add delays between requests or use proxies.
- **Dynamic Content**: This scraper uses Selenium to interact with the website since it requires login and deals with dynamic content.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for more details.
