import time
import pandas as pd
from seleniumwire import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup

# Read links from file and build full URLs
with open('link.txt', 'r') as file:
    base_url = "https://www.fedlex.admin.ch"
    links = [base_url + line.strip() for line in file if line.strip()]

# Configure the Selenium WebDriver
options = webdriver.ChromeOptions()
#options.add_argument('--headless')
driver = webdriver.Chrome()

# Prepare a list to store data
data = []
raw_link=[]
for link in links:
    driver.get(link)
    
    # Wait explicitly for 10 seconds
    try:
        WebDriverWait(driver, 300).until(EC.presence_of_element_located((By.ID, 'maintext')))
    except Exception as e:
        print(f"Error loading {link}: {e}")
        raw_link.append(link)
        continue
    time.sleep(5)

    # Get HTML content
    html_content = driver.page_source
    
    # Parse HTML content with BeautifulSoup
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        # maintext=soup.find('main',id="maintext")
        # maintext.decompose()
        main_div = soup.find('div', id='annexeContent')

    # Initialize a list to store paragraph texts
        paragraph_texts = []
        Abbreviation="Not Found"
        Decision="Not Found"
        InForce="Not Found"
        # Iterate over each child div of the main div
        for child_div in main_div.find_all('div', recursive=False):
            # Find all paragraph tags within the child div
            strong=child_div.find("strong",recursive=False)
            if strong and "Abréviation" in strong.get_text(strip=True):
                paragraphs = child_div.find('p',recursive=False)
                if paragraphs:
                    Abbreviation=paragraphs.get_text(strip=True)
                    paragraph_texts.append(paragraphs.get_text(strip=True))
            elif strong and "Décision" in strong.get_text(strip=True):
                paragraphs = child_div.find('p',recursive=False)
                if paragraphs:
                    Decision=paragraphs.get_text(strip=True)
                    paragraph_texts.append(paragraphs.get_text(strip=True))
            elif strong and "Entrée en vigueur" in strong.get_text(strip=True):
                paragraphs = child_div.find('p',recursive=False)
                if paragraphs:
                    InForce=paragraphs.get_text(strip=True)
                    paragraph_texts.append(paragraphs.get_text(strip=True))
            # Extract the text from each paragraph and add to the list
            # for paragraph in paragraphs:
            #     paragraph_texts.append(paragraph.get_text(strip=True))

        # Print the extracted paragraph texts
        print(paragraph_texts)
        # with open("ContentTesting.html",'w') as file:
        #     file.write(str(soup))
        # Extract special request URL
        special_request_url = None
        for request in driver.requests:
            if request.response and request.url.startswith("https://www.fedlex.admin.ch/filestore/fedlex.data.admin.ch/eli/cc") and not "png" in request.url:
                special_request_url = request.url
                
                
        print(special_request_url)
        # Append data to the list
       
        data.append({
                'URL': link,
                'Special Request URL': special_request_url,
                "Abbreviation":Abbreviation,
                "Decision":Decision,
                "InForce":InForce,
                # 'HTML Content': soup.prettify()
            })

        # print(f"Processed content for {link}")
    except Exception as e:
        print("Exception has been Occur",e)
        raw_link.append(link)


driver.quit()

# Create a DataFrame from the data list
df = pd.DataFrame(data)

# Save DataFrame to CSV
csv_filename = 'extracted_data2.csv'
df.to_csv(csv_filename, index=False, encoding='utf-8')

print(f"CSV file has been created at {csv_filename}")

for raw in raw_link:
    print(raw)
