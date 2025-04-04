from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import dataset

# Path to the WebDriver (update this to the location where your chromedriver or geckodriver is located)
driver_path = "/path/to/chromedriver"  # Update this to your driver path

# Initialize the WebDriver (Chrome in this case)
driver = webdriver.Chrome()
wait = WebDriverWait(driver, 10)  # Wait time for the elements

# Initialize the SQL database (SQLite as an example)
db = dataset.connect('sqlite:///webpages.db')

# Table to store the URL and HTML content
table = db['pages']

# List to store URLs
url_list = []

# Define the base URL
base_url = "https://www.capterra.co.uk/directory/20052/point-of-sale/software"

# Scraping URLs from the pagination pages
for index in range(1, 46):
    time.sleep(2)  # Optional delay
    if index == 1:
        page_url = base_url
    else:
        page_url = f"{base_url}?page={index}"

    print(f"Reached Original Index {index}")
    
    # Open the page with Selenium
    driver.get(page_url)

    # Wait for the "li.page-item" to be present before proceeding
    wait.until(EC.presence_of_element_located((By.CLASS_NAME, "page-item")))

    # Find all product cards
    all_cards = driver.find_elements(By.CLASS_NAME, "product-card")
    print(f"Found {len(all_cards)} product cards on page {index}")
    
    # Extract URLs from the product cards
    for card in all_cards:
        try:
            a = card.find_element(By.CLASS_NAME, "mos-star-rating")
            if a:
                url_list.append(a.get_attribute("href"))
        except:
            continue

# Function to save HTML content into the SQL database
def save_to_db(url, html_content):
    table.insert({
        'url': url,
        'html_content': html_content,
    })

# Main scraping function for individual product URLs
def scrape_and_store(url_list):
    for url in url_list:
        print(f"Processing URL: {url}")

        # Open the product page
        driver.get(url)

        # Wait for page content to load (optional)
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, "product-card")))

        # Get the page source (HTML)
        html_content = driver.page_source

        # Save the HTML content into the database
        save_to_db(url, html_content)

        # Optional sleep to avoid hitting the server too quickly
        time.sleep(0.1)

# Start the scraping process for individual product pages
scrape_and_store(url_list)

# Close the browser session
driver.quit()
