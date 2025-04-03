
# 📦 1mg Medicine Scraper

This project is a Python-based scraper designed to extract detailed information about medicines from **1mg**. It scrapes product details like **medicine name**, **price**, **manufacturer**, **composition**, and **usage** information using **requests**, **BeautifulSoup**, **multi-threading**, and **multiprocessing**.

## 🧑‍💼 **Client’s Goals**
The client wanted to extract comprehensive data from **1mg**, including:
- **Medicine Name**
- **Price**
- **Manufacturer**
- **Composition**
- **Uses** and **Benefits**
- **Side Effects**, **FAQs**, and **Safety Advice**

The goal was to retrieve and save this data in **Excel** and **CSV** formats for analysis or further use.

## 🛠️ **Project Structure**
This project consists of multiple Python scripts, each with a different role:

### 1. **`1.scrap_urls.py`** - Extracts Medicine URLs
- **Purpose:** Scrapes all medicine links from 1mg for further data extraction.
- **Process:**
  - Iterates over alphabets and pages to gather a list of medicine URLs.
  - Uses **ThreadPoolExecutor** for parallel scraping of data.
  - Saves the list of URLs and additional information into a CSV and Excel file.

### 2. **`2a.scrap_html.py`** - Scrapes HTML Content of Medicine Pages
- **Purpose:** Visits the scraped URLs and extracts detailed **HTML content** of each medicine's page.
- **Process:**
  - Uses multi-threading and proxies to handle multiple URLs concurrently.
  - Saves the HTML content to a database for further processing.

### 3. **`3a.parsedatabasefast.py`** - Parses Stored HTML Content
- **Purpose:** Processes the stored HTML content and extracts the required information for each medicine.
- **Process:**
  - Uses **multiprocessing** to parse large batches of data efficiently.
  - Extracts fields like **Uses**, **Side Effects**, **Storage**, **Manufacturer**, and **Safety Advice**.
  - Saves the parsed data in an Excel file for easy access and analysis.

## ⚙️ **Setup Instructions**

### 1. **Install Dependencies:**
```bash
pip install requests beautifulsoup4 pandas alive-progress dataset
```

### 2. **Run the Scripts:**
To scrape the URLs:
```bash
python 1.scrap_urls.py
```
To extract HTML content:
```bash
python 2a.scrap_html.py
```
To parse the HTML data:
```bash
python 3a.parsedatabasefast.py
```

### 3. **Output Files:**
- Scraped URLs: **`Data3.xlsx`**
- Extracted HTML content is stored in a database.
- Final parsed data is saved in **`Data3.xlsx`**.

---

## 📌 **Key Features**
- **Multithreading:** Fast data extraction using **ThreadPoolExecutor**.
- **Multiprocessing:** Efficient processing of large datasets using **multiprocessing**.
- **Proxies:** Implemented proxies to avoid IP blocks and increase scraping speed.
- **Scalable:** The scraper can handle large volumes of data and scale up as needed.

---

## 📬 **Contact**
If you need further modifications or have questions, feel free to open an issue or reach out to the project maintainer.

---

