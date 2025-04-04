
# Property Scraper

## Overview
The **Property Scraper** project is designed to extract property-related information from a specific online directory. It processes postal code data and associates property addresses with owners' names. The program then scrapes contact details, including phone numbers, from a publicly available source and matches them with the names from the input dataset. The main goal is to automate data retrieval and match names with contact details for further analysis or record-keeping.

## Functionality
This project uses Python's `requests`, `BeautifulSoup`, and `pandas` libraries to scrape property-related data. The scraping process is divided into several steps:

1. **Input Data Processing:** 
    - The script begins by reading a CSV file containing postal addresses and property owners' names.
    - It organizes the data by postal codes, grouping property names under corresponding postal codes.

2. **Scraping Data:**
    - For each postal code, the script sends a request to the **Canada411** website.
    - It extracts contact information for each property listed under the postal code, including the property owner's name and phone number.
    - The extracted data is matched with the names from the input dataset based on the first name.

3. **Output:**
    - The script outputs the property owner's name and phone number if a match is found.

## Key Features:
- **Address Parsing:** The addresses are processed to extract postal codes and organize data accordingly.
- **Web Scraping:** The project uses `BeautifulSoup` to scrape contact details from the **Canada411** website.
- **Data Matching:** The first names from the input dataset are matched with the last names from the scraped contact details.
- **Error Handling:** The script is designed to handle exceptions, ensuring smooth execution even if some records don't match.

## Libraries Required
- `requests`: To send HTTP requests and retrieve page content.
- `beautifulsoup4`: For parsing HTML and extracting relevant information.
- `pandas`: For handling and processing input data.
- `re`: For regular expressions, used to extract postal codes.
- `datetime`: For handling date-related functionality.
- `time`: For introducing delays in the scraping process.

To install the required libraries, run:
```bash
pip install requests beautifulsoup4 pandas
```

## Input Format
The input file must be a CSV file named `results.csv` with at least two columns:
1. **Adresse postale**: Property address, including the postal code.
2. **Nom**: Property owner's name.

Example of `results.csv`:
```csv
Adresse postale,Nom
"123 Main St, Toronto, ON M5H 2N2","John Doe"
"456 Elm St, Ottawa, ON K1A 0B1","Jane Smith"
```

## Script Flow
1. **Data Parsing:** The input addresses are split into their components to extract the postal code.
2. **Data Grouping:** The names are grouped under their corresponding postal codes.
3. **Web Scraping:** For each postal code, a request is sent to **Canada411**, and contact details are scraped for matching names.
4. **Match Verification:** The first names from the input data are compared with the last names in the scraped data, and matching contact details are printed.

## Output
For each property match, the following details will be displayed:
- **Owner Name**
- **Phone Number**

Example Output:
```bash
John Doe
(555) 123-4567

Jane Smith
(555) 987-6543
```

## Error Handling
If any errors occur during the scraping process (e.g., connection issues or missing data), the error message will be printed, and the script will continue processing other data.

## Running the Script
To run the script:
```bash
python property_scraper.py
```

## Notes
- The website being scraped might block automated requests if done excessively. To avoid this, consider implementing rate-limiting or rotating IP addresses.
- Ensure that you have permission to scrape data from websites and that your usage complies with legal and ethical standards.

## Conclusion
This scraper efficiently processes and matches property-related data with contact details. It's ideal for property management companies or individuals needing to verify contact information quickly.

---

For any questions or issues, feel free to contact me. I'm open to further modifications or enhancements based on your needs!
