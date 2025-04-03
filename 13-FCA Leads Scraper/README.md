
# 📊 Financial Conduct Authority (FCA) Lead Scraper Project

This project involves scraping company information from the **Financial Conduct Authority (FCA)** website, specifically focusing on extracting data related to financial companies registered in the UK. The scraper uses **Selenium WebDriver** and **SeleniumWire** to interact with the website, capture JSON data from **XHR requests**, and extract relevant company details like **company names**, **contact names**, and **addresses**.

## 🧑‍💼 **Client’s Goals**

The client required an automated solution to extract detailed company data from the **FCA Register**, which is publicly available on the **UK Financial Conduct Authority’s** website. The goal was to collect information such as:

- **🔗 Company Names** and associated **IDs**
- **👤 Contact Information** of company representatives
- **🏠 Company Address Details**
- **📊 Additional Company Information** relevant to regulatory purposes

## ⚠️ **Challenges & Solutions**

### 1. **🔍 Capturing Dynamic JSON Data**
- **Challenge:** The website loads data dynamically through **XHR requests**, which requires capturing the requests to retrieve the JSON data.
- **Solution:** Utilized **SeleniumWire**, a powerful library that enables capturing network requests directly from the browser, allowing access to the dynamic JSON data.

### 2. **🖥️ Automating Data Extraction**
- **Challenge:** Automating the extraction of data across multiple pages required efficient navigation and scraping logic.
- **Solution:** Used **Selenium WebDriver** for browsing, interacting with page elements, and ensuring smooth navigation across the website. Data was extracted from dynamically loaded tables using **BeautifulSoup**.

### 3. **📥 Storing Data Efficiently**
- **Challenge:** Storing the scraped data in a structured and accessible format for analysis.
- **Solution:** The extracted data was organized into **pandas DataFrames** and saved into **Excel files** for easy access and future use.

## 🛠️ **Code Overview**

### 1. **`indexselenium.py`** - Extracting and Storing Company Information
- **🔗 Purpose:** This script uses **Selenium WebDriver** along with **SeleniumWire** to navigate through the FCA website and capture the JSON data containing the company information.
- **🧩 Key Actions:**
  - Navigates through the FCA pages.
  - Captures XHR requests containing company information.
  - Extracts and organizes company details such as names, contact information, and addresses.
  - Saves the final data into an **Excel file** for easy access and analysis.
## Excel File Result
![image](https://github.com/user-attachments/assets/9aa78b4c-1678-4799-a46b-35e5c0afcd40)

![image](https://github.com/user-attachments/assets/310a0651-0074-4870-83b1-c3e7db3d1195)

## 📦 **How the Code Works**

1. **Selenium Automation:** The code uses **Selenium WebDriver** to automatically navigate through the FCA website, click on buttons, and interact with elements on the page.
   
2. **XHR Request Capture:** By using **SeleniumWire**, the code captures the **XHR requests** and extracts JSON data, which contains the detailed company information.

3. **Data Extraction & Storage:** The JSON data is parsed to extract relevant fields like company name, contact name, and address, which are then stored in a **pandas DataFrame**.

4. **Excel Export:** The processed data is saved in an **Excel file** for easy export, allowing the client to analyze and use the data efficiently.

## 📈 **Results & Deliverables**

- **Excel File**: The data is saved in a clean, structured **Excel file** containing the following columns:
  - Company Name
  - Contact Name
  - Address
  - Additional company details
- **Automated Scraping**: The project provides a fully automated solution for scraping dynamic data from the FCA website, reducing the manual effort needed to collect this information.

## 📬 **Contact & Customization**

If you require further modifications or additional features (e.g., exporting to different formats, scraping additional data), feel free to reach out! I can also customize the scraper to work with other financial registers or websites based on your needs.

## **Setup Instructions**

1. **Install Dependencies:**
   ```bash
   pip install selenium selenium-wire pandas openpyxl
   ```

2. **Run the Script:**
   - Run the main script to start scraping:
   ```bash
   python indexselenium.py
   ```

3. **Output:**
   - The scraped data will be saved into an **Excel file** (`outputfile.xlsx`).

---

