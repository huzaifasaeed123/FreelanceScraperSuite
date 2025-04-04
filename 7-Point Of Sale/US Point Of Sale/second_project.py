from seleniumbase import Driver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import time

# Initialize the Chrome WebDriver using webdriver_manager
driver = Driver(uc = True)

# Navigate to the given URL
url = "https://www.capterra.com/p/135040/Revel-iPad-POS/reviews/"
driver.get(url)

# Initialize a wait object

# Perform the click action on the "Show more reviews" button up to 10 times
for _ in range(5):
    try:
        # Wait until the button appears and becomes clickable
        
        # Click the button
        # show_more_button.click()
        # Wait for new content to load
        time.sleep(100)  # Adjust this based on network speed
    except Exception as e:
        print("Button not found or no more clicks are possible:", str(e))
        # break

# Extract the entire page content after clicking the button
page_content = driver.page_source

# Close the driver
driver.quit()

# Parse the content using BeautifulSoup
soup = BeautifulSoup(page_content, 'html.parser')

# Extract reviews or any relevant data from the parsed HTML
# This is an example: extracting all review containers
reviews = soup.find_all("div", class_="review-container")  # Adjust the class name based on the actual HTML structure

# Print the extracted reviews or save them to a file
for i, review in enumerate(reviews, start=1):
    print(f"Review {i}:")
    print(review.text.strip())
    print("-" * 80)

# Optional: Save the full HTML to a file for later analysis
with open("extracted_reviews.html", "w", encoding="utf-8") as f:
    f.write(page_content)

print("Data extraction complete!")
