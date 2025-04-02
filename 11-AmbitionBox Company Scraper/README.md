
# 📊 AmbitionBox Company Scraper

This project consists of Python scripts designed to scrape data from AmbitionBox, a platform providing detailed insights about companies, their culture, salaries, employee reviews, and more. The scraper collects data across multiple categories and ratings, with options for filtering by employee size and location.

## 🛠️ Project Structure

The project contains several Python scripts:

### 1. **`IndexMain.py`** - Main Scraper Script

- **Functionality:** This is the primary script that sends POST requests to the AmbitionBox API to retrieve detailed company data.
- **Process:**
  - Sends requests for multiple categories like company culture, salary benefits, work-life balance, and more.
  - Loops through different ratings and employee sizes to gather data.
  - Extracts relevant data like company name, review count, job postings, ratings, employee count, etc.
  - Saves the extracted data into a CSV file (`IndianProjectSample4.csv`).

### 2. **`indexTesting.py`** - Test Version of Main Scraper

- **Functionality:** A simplified version of the main scraper for testing purposes.
- **Process:** 
  - This script performs similar operations to `IndexMain.py` but with limited categories and a `break` statement for testing.
  - It helps ensure that the primary script works as expected before scaling to the full set of features.

### 3. **`sitemapcheck.py`** - Sitemap Scraper

- **Functionality:** Scrapes URLs containing company overviews from the AmbitionBox sitemap.
- **Process:**
  - Requests the sitemap XML files and extracts all URLs with the word "overview."
  - Saves the URLs into a text file (`urls_with_overviews.txt`).
  - Provides a list of company overviews for further processing or scraping.

### 4. **`upload.py`** - File Upload Script

- **Functionality:** Uploads the CSV file containing scraped data to an external server.
- **Process:**
  - Uses the `file.io` API to upload the scraped CSV file.
  - Provides a link to the uploaded file for easy download.

## 🎯 Client’s Goals

- **Scrape company data** from AmbitionBox, focusing on specific categories such as company culture, salary, work-life balance, and employee ratings.
- **Export the data** into structured CSV files for analysis or further use.
- **Ensure scalability** to handle large datasets by implementing pagination and efficient data extraction.
- **Upload the final data** to a remote server for easy sharing.

## ⚠️ Challenges & Solutions

### Challenge 1: Handling Large Volumes of Data
- **Solution:** 
  - Used pagination to handle large numbers of companies across multiple categories.
  - Broke the scraping into manageable parts, ensuring each request is processed efficiently.

### Challenge 2: Filtering Data Based on Multiple Criteria
- **Solution:** 
  - Implemented category filters such as company culture, work-life balance, and employee size.
  - Added rating filters (e.g., 4.0, 4.5) to refine the data extraction process.

### Challenge 3: File Uploads and Data Storage
- **Solution:** 
  - Implemented a file upload feature (`upload.py`) to upload CSV data to an external server, providing easy access for the client.

## ⚙️ Setup Instructions

1. **Install Dependencies:**
   ```bash
   pip install requests pandas beautifulsoup4
   ```

2. **Run the Scripts:**
   - To run the main scraper:
     ```bash
     python IndexMain.py
     ```
   - To test the functionality with limited data:
     ```bash
     python indexTesting.py
     ```
   - To scrape URLs from the sitemap:
     ```bash
     python sitemapcheck.py
     ```

3. **Upload Data:**
   - Once the data is scraped and saved into a CSV file, run the following to upload the file:
     ```bash
     python upload.py
     ```

4. **Output Files:**
   - The main output file will be `IndianProjectSample4.csv`.
   - A list of overviews is saved in `urls_with_overviews.txt`.

## 📌 Notes

- The project is designed for **scalability** and can handle a large number of companies and data points.
- **Proxies** or **IP management** might be necessary for scraping larger datasets to avoid blocks.
- You can modify the categories, ratings, or employee counts to adjust the scraping scope.

---

## 📬 Contact

For further modifications, issues, or inquiries, feel free to reach out. I’m available for customizing the scraper for different websites or expanding its functionality based on your needs.
