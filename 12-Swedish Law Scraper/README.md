
# 📜 Swedish Law Scraper

This project is designed to scrape legal data from the **Fedlex** website, which provides official Swiss legal documents. The scraper is divided into three main parts: 

1. **Selenium Navigation**: Extracts links to various laws from the website.
2. **Extracting Law Details**: Collects additional details about the laws by navigating through individual pages.
3. **Parsing Law Files**: Extracts relevant sections, articles, and footnotes from the law files.

## 🧑‍💼 **Client’s Goals**

The client's objective was to collect detailed law-related data from the Fedlex website for research purposes. The project was structured to:
- **🔗 Extract links** to all laws listed on the Fedlex website.
- **📄 Extract full law files** along with their key details like law ID, abbreviation, decision dates, and version history.
- **📖 Parse the law files** to extract sections, articles, and related footnotes, storing them in an easily accessible format for analysis.

## ⚠️ **Challenges & Solutions**

### 1. **🖥️ Selenium Navigation for Link Extraction**  
- **Challenge:** Automating the navigation through dynamic pages and extracting all law links.  
- **Solution:** Used **Selenium WebDriver** with headless Chrome to automate browsing, iterate through pages, and extract law links effectively.

### 2. **📑 Extracting Detailed Information**  
- **Challenge:** Each law had a unique structure, requiring careful parsing for specific details.  
- **Solution:** Selenium navigates to each law page, and **BeautifulSoup** is used to parse the content, extracting essential information like abbreviations, decision dates, and law-specific text.

### 3. **📝 Parsing Law Files & Handling Nested Sections**  
- **Challenge:** Parsing nested sections, articles, and footnotes from law files in different formats.  
- **Solution:** Implemented robust HTML parsing logic using **BeautifulSoup**, which handles nested tags, and replaced `<br>` and `<sup>` tags for clean data extraction. Extracted articles were then stored systematically.

## 📂 **Code Structure**

### 1. **`seleniumNavigation.py`** - Extracting Law Links
- **🔗 Purpose:** This script automates the process of navigating through Fedlex’s website using **Selenium** and extracts all available law links from the pages.  
- **🧩 Code Breakdown:** 
    - Configures Selenium WebDriver with headless mode.
    - Loops through multiple pages to retrieve law links.
    - Collects secondary law links by iterating over each extracted law link and fetching related details.

### 2. **`seleniumpartTwo.py`** - Extracting Law Details
- **📄 Purpose:** Extracts detailed information from the links collected in the first part.  
- **🧩 Code Breakdown:** 
    - Uses Selenium to open each law link and waits for the page to load.
    - Uses **BeautifulSoup** to extract content like **Abbreviation**, **Decision Dates**, and **In-Force Dates**.
    - Collects secondary links and law-specific URLs.
    - Stores all collected data into a CSV file for further analysis.

### 3. **`index.py`** - Parsing Law Content
- **📖 Purpose:** Parses the law content page for specific sections, articles, and footnotes.  
- **🧩 Code Breakdown:** 
    - Retrieves detailed law information by parsing the page content.
    - Extracts headings, articles, subparagraphs, and other key data.
    - Replaces special tags like `<sup>` and `<br>` with spaces or appropriate tags.
    - Stores parsed data into structured CSV files for export.

### 4. **Supporting Functions and Helpers**
- The project also includes several helper functions to:
    - **Clean the extracted data**: Removing unnecessary tags and replacing them with structured content.
    - **Handle nested sections**: Ensures that any nested law sections are properly parsed and organized.
    - **Export parsed data**: Data is saved into CSV files (`FinalData.csv`, `Missing.csv`) for easy access and analysis.

## ⚙️ **How the Code Works**

1. **Part 1 - Extract Links**: The script `seleniumNavigation.py` collects the links to all laws from the **Fedlex** site by using Selenium for browser automation. The code fetches the link of each law from multiple pages by navigating through page numbers.

2. **Part 2 - Extract Law Data**: After collecting the links, `extract_mainFile.py` opens each law page and extracts detailed law data such as abbreviation, decision dates, and law ID. It navigates through each law's page and stores the required data in CSV files.

3. **Part 3 - Parsing Law Content**: Once the data is extracted, `parsing_law_file.py` parses each law file to extract articles, paragraphs, and footnotes. These elements are cleaned, structured, and saved in an organized manner.

4. **Output**: Finally, the extracted data is saved in CSV format for analysis. The `createCSVFile()` function ensures the data is saved with appropriate column headers, and missing data is logged separately.

## 🏁 **Result & Deliverables**

The scraper efficiently collects all necessary information from the **Fedlex** website, processes the data, and exports it into structured **CSV files**. The final deliverables include:

- **🔗 List of Law Links**: All relevant links to laws from the Fedlex website.
- **📄 Detailed Law Data**: Information about each law, including abbreviation, decision dates, and other important details.
- **📖 Parsed Law Content**: Articles, paragraphs, and footnotes parsed and organized from each law.
- **CSV Files**: Clean and structured CSV files for **easy analysis and future use**.

## 📬 **Contact & Customization**

Feel free to contact me if you need further customization or additional features for this scraper. I can modify the script to handle additional websites, new categories, or specific data points based on your needs.

---

## **Setup Instructions**

To set up the project on your machine, follow the instructions provided in the `README.md` file. Make sure you have Python installed along with the required libraries.

