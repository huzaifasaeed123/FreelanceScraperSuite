
# OLX Scraper

## Overview

This project focuses on automating the data extraction from OLX, a popular online marketplace, using the OAuth 2.0 authorization flow and Selenium. The scraper follows a systematic approach to handle the authentication and data fetching process from the website. The main goal is to access protected resources on OLX and fetch valuable data like listings, user details, and more using GraphQL API requests.

## Steps Involved

### 1. **OAuth 2.0 Authorization Flow**

The website uses OAuth 2.0 for user authentication. Here’s a breakdown of the flow:

- **Step 1:** Clicking the "Account" button redirects the user to the login page.
- **Step 2:** The login page request includes several parameters (`cc`, `client_id`, `redirect_uri`, etc.).
- **Step 3:** The login request includes authentication details and redirects to a URL upon successful login.
- **Step 4:** A successful login leads to the redirection URL containing an authorization code.
- **Step 5:** The authorization code is exchanged for an access token and a refresh token to interact with the OLX GraphQL endpoint.

### 2. **Using Selenium to Handle Authorization**

- **Automating Browser Interaction:** Selenium automates the login process, overcoming CloudFront's block by using real browser sessions.
- **Capture Tokens:** After login, the redirected URL containing the `code` and `state` parameters is captured, which are then used to request the access and refresh tokens.
- **GraphQL Requests:** The access token is included in the headers for subsequent GraphQL requests to fetch data from OLX.

### 3. **Working with GraphQL API**

Once the OAuth tokens are retrieved using Selenium, you can make GraphQL requests to fetch data like listings and user profiles. The data is returned in JSON format, and Selenium automates the browser interactions to access these protected endpoints.

---

## Project Structure

The project is divided into multiple scripts, each responsible for a specific part of the workflow:

### **1. `1-SeleniumAuthorization.py`**

- Automates the login process using Selenium.
- Handles OAuth 2.0 flow and captures the `code` and `state` parameters.
- Fetches the access and refresh tokens needed to interact with OLX APIs.

### **2. `2-GraphQLDataExtraction.py`**

- Makes authenticated GraphQL requests to retrieve data from OLX.
- Handles the fetching of protected data like user profiles, listings, and other marketplace details.

### **3. `3-DataProcessing.py`**

- Processes the data fetched from the GraphQL endpoint.
- Cleans, filters, and structures the data to be saved or further analyzed.

---

## Setup Instructions

### 1. **Install Dependencies**

```bash
pip install selenium requests beautifulsoup4 pandas
```

### 2. **Running the Scripts**

To run the entire workflow, follow these steps:

1. **Step 1:** Run the Selenium script to authenticate and fetch the access tokens.
   ```bash
   python 1-SeleniumAuthorization.py
   ```
2. **Step 2:** Execute the GraphQL data extraction script using the obtained tokens.
   ```bash
   python 2-GraphQLDataExtraction.py
   ```
3. **Step 3:** Process the data as needed by running:
   ```bash
   python 3-DataProcessing.py
   ```

### 3. **Handling Delays**

The initial delay for obtaining tokens using Selenium is around 30-40 seconds. After the tokens are retrieved, you can access the GraphQL API without significant delay.

---

## Notes

- **CloudFront Block:** The initial login process might be blocked by CloudFront if automated requests are detected. Using Selenium to mimic a real browser session helps bypass this restriction.
- **GraphQL Data Format:** Data returned from GraphQL endpoints is in JSON format, which can be easily parsed using Python's `requests` library.

---

## Future Improvements

- Improve the efficiency of token handling by automating token refresh logic.
- Add additional functionality to scrape more specific data from OLX.
- Implement error handling and retries for failed requests.

---

## 📬 Contact

For further inquiries, feel free to reach out or open an issue in the repository. I am open to collaboration and further improvements.
