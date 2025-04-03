# 🧠 Doctor Data Scraper

This project is a collection of Python scripts built to scrape publicly available data about psychologists and psychotherapists from various European platforms. It extracts contact information, addresses, professions, languages spoken, and more.

---

## 📁 Project Structure

This project consists of **three Python scripts**, each targeting a different platform:

### 1. `indexInsta1.py` – Scraper for Instahelp.me

- **Target Website:** [Instahelp.me](https://instahelp.me/)
- **Purpose:** Extracts psychologist data from different cities and states in Germany and Austria.
- **Process:**
  - Iterates over a list of German states and their cities.
  - Sends GET requests for each city to gather profiles of therapists.
  - Visits each profile page to extract:
    - Name
    - Profession
    - Email
    - Website
    - Address
    - Phone number
    - Languages spoken
  - All data is saved into a CSV file: `InstaData3.csv`

---

### 2. `newProject.py` – Scraper for healthreg-public.admin.ch (Swiss Therapist Database)

- **Target Website:** [healthreg-public.admin.ch](https://healthreg-public.admin.ch/)
- **Purpose:** Uses POST requests to access structured JSON data for Swiss therapists using their ID.
- **Process:**
  - Uses an API key and proxies to send authenticated POST requests with a range of therapist IDs.
  - Extracts structured data such as:
    - First Name, Name
    - Languages
    - Nationalities
    - Profession, Title Type & Kind
    - Email, Address, Phone
  - Uses multithreading to speed up the scraping.
  - Outputs the final data to a CSV file: `Bhabhi3.csv`

---

### 3. `thirdproject.py` – Scraper for Psychologen.at

- **Target Website:** [Psychologen.at](https://www.psychologen.at/)
- **Purpose:** Extracts therapist listings from an Austrian directory.
- **Process:**
  - Iterates through paginated listings.
  - For each profile, it scrapes:
    - Name
    - Profession
    - Address
    - Phone number
    - Email (via a separate email contact page)
  - Extracted emails are fetched by visiting a secondary link.
  - The final data is saved into `output2.csv`

---

## ⚙️ Setup Instructions

### 1. Install Dependencies

```bash
pip install requests beautifulsoup4 pandas alive-progress
```

### 2. Run a Script

Run each Python script individually depending on the source you want to scrape:

```bash
python indexInsta1.py       # For Instahelp data
python newProject.py        # For Swiss HealthReg data
python thirdproject.py      # For Psychologen.at data
```

### 3. Output Files

Each script will generate a CSV file containing scraped data:

- `InstaData3.csv` → Instahelp profiles
- `Bhabhi3.csv` → Swiss HealthReg database
- `output2.csv` → Psychologen.at listings

---
## Result Excel Files Screenshot
![Screenshot 2025-04-01 101236](https://github.com/user-attachments/assets/6cffc777-5c06-48d4-997d-0a9a5a1c8ec1)
![Screenshot 2025-04-01 101236](https://github.com/user-attachments/assets/9b8863ac-980c-4961-b03b-00509c7540e4)

## 📌 Notes

- **Proxies** are used in `newProject.py` and `thirdproject.py` to avoid IP blocking.
- **Multithreading** is implemented in `newProject.py` for efficient scraping of a large ID range.
- Email scraping is handled carefully to avoid violating site restrictions.
- Make sure your internet connection is stable and proxies are active before running.

---

## 🔒 Disclaimer

This project is intended for **educational and research purposes only**. Please ensure that your use of this data complies with the [terms of service](https://instahelp.me/de/datenschutz/) of the websites being scraped and applicable data protection regulations such as the **GDPR**.

---

## 📬 Contact

If you have any suggestions, improvements, or questions, feel free to open an issue or contact the project maintainer.
