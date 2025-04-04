
# 🕵️‍♂️ **HWK Website Scraper**

This project consists of 23 unique Python scripts designed to scrape data from **52 related websites**. Each website shares similar functionalities and layouts but has distinct variations, requiring custom scripts to handle the nuances of each site. The main purpose of these scripts is to extract contact information such as **Name**, **Phone**, **Email**, **Position**, and **Address** from various organizations listed on these websites.

## 🛠️ **Project Structure**

This project contains **23 Python scripts**, one for each website, with the base URL for scraping stored in each respective file. These scripts utilize **BeautifulSoup** for web scraping and **requests** to make HTTP requests. Each file targets a specific website from the **HWK** network, scraping similar information but customized based on the site's structure.

---

### 📝 **Code Flow (General Explanation for All Files)**

1. **Base URL Setup:**
   - Each script is structured to scrape data from a specific **HWK website**, with the `base_url` defined at the beginning of the script.

2. **Iterating Over A-Z:**
   - The scripts iterate through letters A-Z, modifying the URL for each letter (e.g., `A`, `B`, `C`, etc.), to gather data for different pages of contacts listed under these letters.

3. **GET Requests:**
   - A **GET request** is sent for each letter’s URL. If successful, the page is parsed using **BeautifulSoup** to extract links to individual profiles.

4. **Extracting Data:**
   - For each individual profile, the script sends another **GET request** to fetch the full profile page, from which it extracts:
     - **Name**
     - **Phone Number**
     - **Email**
     - **Position**
     - **Address** (if available)

5. **Saving Data:**
   - The collected data is stored in a **list of dictionaries**, and once all pages have been scraped, the list is converted into a **Pandas DataFrame**.
   - The final data is saved in an **Excel file** (e.g., `hwk-aachen2.xlsx`).

---

## Final Result Excel Files
![image](https://github.com/user-attachments/assets/d7792cdb-ed35-4761-8401-58b1df413942)

![image](https://github.com/user-attachments/assets/68a3813c-0715-4e61-9ce9-a58005cd3d87)

![image](https://github.com/user-attachments/assets/a01e0d7f-0503-4e1d-bd5b-132e8449719a)

## ⚙️ **Setup Instructions**

### 1. **Install Dependencies:**
Make sure you have the necessary dependencies installed:
```bash
pip install requests beautifulsoup4 pandas
```

### 2. **Run the Script:**
To run any script, simply execute it via:
```bash
python hwk-aachen.py
```
This will scrape data from the corresponding HWK website and save it into an Excel file.

---

## 📝 **Notes**
- **Proxies** are recommended for handling large-scale scraping to avoid IP bans.
- The project can be **scaled** to include more sites by following the same structure.
- Each website has its **unique HTML structure**, so the scraping logic is adjusted accordingly.

---

## 📬 **Contact**
For any further modifications or custom requirements, feel free to reach out to me. I’m available for building customized scrapers for different websites or expanding the functionality of this project.
