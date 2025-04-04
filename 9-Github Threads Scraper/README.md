
# GitHub User Data Scraper

## Overview
This project is a Python-based web scraper designed to extract user profile data from GitHub. The scraper retrieves information such as names, usernames, bios, locations, social media links, and follower/following counts. It processes multiple pages of user data efficiently using threading, stores the results in a SQLite database, and exports the data to both CSV and Excel files.

## Features
- **Multi-page scraping**: Automatically navigates and scrapes multiple pages of GitHub user profiles.
- **Concurrent execution**: Utilizes threading to speed up the scraping process.
- **Data storage**: Stores the scraped data in a SQLite database.
- **Data export**: Exports the data to CSV and Excel formats.
- **Progress tracking**: Displays a progress bar during the scraping process.

## Requirements
- Python 3.6+
- Required Python libraries:
  - `requests`
  - `beautifulsoup4`
  - `pandas`
  - `concurrent.futures`
  - `alive-progress`
  - `threading`
  - `dataset`
  - `traceback`

You can install the required libraries using the following command:
```bash
pip install requests beautifulsoup4 pandas alive-progress dataset
```

## How to Use
1. **Clone the Repository**:
   ```bash
   git clone https://github.com/your-username/github-user-data-scraper.git
   cd github-user-data-scraper
   ```

2. **Run the Script**:
   Execute the Python script in your terminal or command prompt:
   ```bash
   python scraper.py
   ```

3. **Input a GitHub URL**:
   When prompted, enter a GitHub URL of the repository or user whose data you want to scrape.

4. **View Progress**:
   A progress bar will display as the scraper processes the pages.

5. **Output**:
   - The scraped data will be stored in a SQLite database (`GitHubdata0.db`).
   - Data will also be exported to `GitHubData0.xlsx` (Excel format) and `GithubdataMissing0.csv` (CSV format for any missing data).

## Code Structure
### 1. `retrievePageUrls(url, URL_List)`
   - Fetches user profile URLs from a GitHub page.

### 2. `getCount(url, Main_Url)`
   - Calculates the number of pages to scrape based on the number of items (e.g., stars, followers).

### 3. `retrieveIndividualPages(url, index)`
   - Scrapes detailed information from individual GitHub user profiles.

### 4. `ThreadingPages(PageUrlsData, base_link)`
   - Manages the concurrent scraping of multiple pages using threading.

### 5. `Final_updation_inDB(UpdatedTable, list)`
   - Inserts the scraped data into a SQLite database table.

### 6. `makeCSV(Data_List, path)`
   - Exports the scraped data to a CSV file.

### 7. `sql_table_to_csv(UpdatedTable, csv_file_path)`
   - Exports data from the SQLite database table to an Excel file.

### 8. `main()`
   - The main function that orchestrates the entire scraping process.

## Contributing
Contributions are welcome! Please submit a pull request or open an issue to discuss any changes.

## License
This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Contact
If you have any questions or issues, please feel free to reach out via GitHub issues.

---

Happy Scraping! 🚀
