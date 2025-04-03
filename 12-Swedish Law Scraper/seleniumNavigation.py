import time
import pandas as pd
from seleniumwire import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import pandas as pd
from selenium.webdriver.chrome.options import Options

# Setup Selenium WebDriver
chrome_options = Options()
chrome_options.add_argument("--headless")  # Run in headless mode
# chrome_driver_path = '/path/to/chromedriver'  # Update this path

# service = Service(chrome_driver_path)
driver = webdriver.Chrome(options=chrome_options)

all_links = []
driver.get("https://www.fedlex.admin.ch")
time.sleep(20)
# Loop from 1 to 9 to visit each page
for i in range(7, 10):
    # Navigate to the URL   
    url = f"https://www.fedlex.admin.ch/it/cc/internal-law/{i}"
    driver.get(url)
    
    # Wait for 5 seconds
    time.sleep(15)
    
    # Get the HTML content of the page
    html_content = driver.page_source
    
    # Parse the HTML content using BeautifulSoup
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Find all td elements
    td_elements = soup.find_all('td')
    
    # Extract the href attribute of each a tag within td elements
    for td in td_elements:
        a_tags = td.find_all('a')
        for a in a_tags:
            href = a.get('href')
            if href:
                if "#" not in href:
                    print(href)
                    all_links.append(href)

# Close the WebDriver
secondary_links = []

base_url="https://www.fedlex.admin.ch"

# Iterate over the extracted links
for link in all_links:
    # Make sure the link is absolute
    if not link.startswith('http'):
        link = "https://www.fedlex.admin.ch" + link
    print("Make Request",link)
    # Navigate to the extracted link
    driver.get(link)
    
    # Wait for 5 seconds
    time.sleep(15)
    
    # Get the HTML content of the page
    html_content = driver.page_source
    
    # Parse the HTML content using BeautifulSoup
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Find all td elements
    td_elements = soup.find_all('td')
    
    # Extract the href attribute of each a tag within td elements
    for td in td_elements:
        a_tags = td.find_all('a')
        for a in a_tags:
            href = a.get('href')
            if href:
                if "#" not in href:
                    #print(href)
                    secondary_links.append(href)
    # break
# driver.quit()
def extract_mainFile(links):
    print("MainFile Stated")
    # with open('link.txt', 'r') as file:
    #     
    #     links = [base_url + line.strip() for line in file if line.strip()]

    # Configure the Selenium WebDriver
    # options = webdriver.ChromeOptions()
    # #options.add_argument('--headless')
    # driver = webdriver.Chrome()

    # Prepare a list to store data
    data = []       
    raw_link=[]
    for Orilink in links:
        link=base_url+Orilink
        driver.get(link)
        # Wait explicitly for 10 seconds
        try:
            WebDriverWait(driver, 60).until(EC.presence_of_element_located((By.ID, 'maintext')))
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
                if strong and "Abbreviazione" in strong.get_text(strip=True):
                    paragraphs = child_div.find('p',recursive=False)
                    if paragraphs:
                        Abbreviation=paragraphs.get_text(strip=True)
                        paragraph_texts.append(paragraphs.get_text(strip=True))
                elif strong and "Decisione" in strong.get_text(strip=True):
                    paragraphs = child_div.find('p',recursive=False)
                    if paragraphs:
                        Decision=paragraphs.get_text(strip=True)
                        paragraph_texts.append(paragraphs.get_text(strip=True))
                elif strong and "Entrata in vigore" in strong.get_text(strip=True):
                    paragraphs = child_div.find('p',recursive=False)
                    if paragraphs:
                        InForce=paragraphs.get_text(strip=True)
                        paragraph_texts.append(paragraphs.get_text(strip=True))
                # Extract the text from each paragraph and add to the list
                # for paragraph in paragraphs:
                #     paragraph_texts.append(paragraph.get_text(strip=True))

            # Print the extracted paragraph texts
            print(paragraph_texts)
            
            # Print the extracted paragraph texts
            # print(paragraph_texts)
            # with open("ContentTesting.html",'w') as file:
            #     file.write(str(soup))
            # Extract special request URL
            special_request_url = None
            for request in driver.requests:
                if request.response and request.url.startswith("https://www.fedlex.admin.ch/filestore/fedlex.data.admin.ch/eli/cc") and not "png" in request.url:
                    special_request_url = request.url
                    
                    
            print(special_request_url)
            data.append({
                'URL': link,
                'Special Request URL': special_request_url,
                "Abbreviation":Abbreviation,
                "Decision":Decision,
                "InForce":InForce,
                # 'HTML Content': soup.prettify()
            })
            # break
            # Append data to the list
            # if len(paragraph_texts)==5:
            #     data.append({
            #         'URL': link,
            #         'Special Request URL': special_request_url,
            #         "Abbreviation":paragraph_texts[0],
            #         "Decision":paragraph_texts[1],
            #         "InForce":paragraph_texts[2],
            #         "Source":paragraph_texts[3],
            #         "Publication_Language": paragraph_texts[4]

            #         # 'HTML Content': soup.prettify()
            #     })
            # elif len(paragraph_texts)==4:
            #     data.append({
            #         'URL': link,
            #         'Special Request URL': special_request_url,
            #         "Abbreviation":"Not Present",
            #         "Decision":paragraph_texts[0],
            #         "InForce":paragraph_texts[1],
            #         "Source":paragraph_texts[2],
            #         "Publication_Language": paragraph_texts[3]

            #         # 'HTML Content': soup.prettify()
            #     })

            # print(f"Processed content for {link}")
        except Exception as e:
            print("Exception has been Occur",e)
            raw_link.append(link)


    driver.quit()

    # Create a DataFrame from the data list
    df = pd.DataFrame(data)

    # Save DataFrame to CSV
    csv_filename = 'extracted_datait4.csv'
    df.to_csv(csv_filename, index=False, encoding='utf-8')

    print(f"CSV file has been created at {csv_filename}")
    print("Printing Raw Data")
    with open("RawDatait4.txt", 'w') as file:
        for raw in raw_link:
            file.write(link + '\n')
            print(raw)

# Close the WebDriver
# for link in secondary_links:
#     print(link)
extract_mainFile(secondary_links)
# Output the extracted secondary links  
# for link in secondary_links:
#     print(link)
