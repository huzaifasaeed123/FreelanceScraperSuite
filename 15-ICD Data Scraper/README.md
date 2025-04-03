
# 🧑‍⚕️ ICD Data Scraper

This project is a Python-based web scraper built to recursively extract hierarchical heading data from the **ICD 11 MMS (International Classification of Diseases)** dataset. The scraper traverses through a series of **nested links**, maintaining their heading hierarchy and extracting valuable information such as **title**, **code**, **exclusion**, **index terms**, and more.

## 🧑‍💼 **Client's Goals**

The client required a solution to **extract hierarchical data** related to the **ICD (International Classification of Diseases)** using a **recursive approach**. The goal was to:
- **Scrape** structured data about **ICD codes**, **definitions**, **exclusion criteria**, and more.
- **Maintain hierarchical levels** of headings as the scraper recursively navigates through nested child links.
- **Store the data** in a structured format (Excel) for further analysis.

## 🛠️ **Project Structure**

### 1. **`Main Scraper`**

- **Target Website:** [ICD WHO](https://id.who.int/icd/release/11/2025-01/mms)
- **Purpose:** The primary script that recursively navigates through child links, maintaining the correct heading hierarchy.
- **Process:**
  - Extracts **title**, **code**, **block ID**, **exclusion terms**, **index terms**, and other data fields.
  - Uses a recursive function to **traverse child links**, preserving the structure of the data.
  - **Stores the data** in a CSV or Excel file.
  
  **Recursive Data Extraction Example:**
  - For each heading, the script checks for **child links** and processes them.
  - It ensures that the heading levels are maintained as the scraper moves deeper into the dataset.

### 2. **`Helper Functions`**

- **Functionality:** Handles the data formatting and saving of scraped data.
  - **`format_labels_as_bullets`** – Formats label data as bulleted lists.
  - **`create_csv`** – Creates a CSV or Excel file with the hierarchical heading data.
  - **`process_each_link`** – Processes each child link recursively and stores the data while maintaining the heading levels.

### 3. **`Data Processing`**

- **Purpose:** Collects all the extracted data from the main scraper and formats it for easy storage and analysis.
- **Process:**
  - Iterates through the extracted data and formats it into a list.
  - The data is then **stored in a CSV or Excel file** using pandas.

## 🎯 **Key Features**

- **Recursive Data Extraction:** Uses a recursive approach to handle nested headings while maintaining the correct hierarchy.
- **Structured Output:** Saves the output as **Excel** files to ensure easy readability and further use.
- **Scalable:** Can handle large datasets by making use of recursive calls to fetch child links dynamically.
- **Error Handling:** Includes robust error handling for failed requests, ensuring smooth data extraction.
## Final Result Excel File
![image](https://github.com/user-attachments/assets/cd3e7ad0-f698-4cad-9925-419007a25553)
![image](https://github.com/user-attachments/assets/aeaf5278-6c05-41ab-9b8f-8a282ef89149)

## ⚙️ **Setup Instructions**

### 1. **Install Dependencies:**
```bash
pip install requests pandas beautifulsoup4 alive-progress
```

### 2. **Run the Scraper Script:**
```bash
python script_name.py
```

### 3. **Output Files:**
- **ICD_dataFinal8.xlsx**: Contains the final structured dataset in Excel format.

## 📌 **Notes**

- Ensure that your **internet connection** is stable, as the scraper involves multiple HTTP requests to fetch data.
- Proxies may be required for **IP management** if scraping larger datasets over extended periods.
- The **recursive approach** is essential for handling nested child links and ensuring the data hierarchy is maintained.

## 📬 **Contact**

Feel free to reach out for **modifications** or if you have any **questions** regarding the scraper.

---
