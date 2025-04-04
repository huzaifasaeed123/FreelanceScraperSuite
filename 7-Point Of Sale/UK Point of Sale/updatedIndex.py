import requests
from bs4 import BeautifulSoup
import time
import dataset

# Proxy settings
proxy = {
    'http': 'http://198.204.241.50:17047',
    'https': 'http://198.204.241.50:17047'
}
headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "max-age=0",
        "Cookie": ("OptanonAlertBoxClosed=2024-09-20T14:25:01.938Z; _ga=GA1.1.1549404099.1726842299; _gcl_au=1.1.432050905.1726842302; AMCV_04D07E1C5E4DDABB0A495ED1%40AdobeOrg=-637568504%7CMCIDTS%7C19987%7CMCMID%7C78705225053617251862749518570512246727%7CMCAAMLH-1727447103%7C3%7CMCAAMB-1727447103%7CRKhpRz8krg2tLO6pguXWp5olkAcUniQYPHaMWWgdJ3xzPWQmdj0y%7CMCOPTOUT-1726849503s%7CNONE%7CvVersion%7C5.1.1; _clck=1d149cq%7C2%7Cfpd%7C0%7C1724; _sylar_key=SFMyNTY.g3QAAAAEbQAAAAtfY3NyZl90b2tlbm0AAAAYTVhqdG1ua1NDUnZzRWxCdFJXdXhTbURFbQAAAAxsYW5kaW5nX3BhZ2VtAAAArWh0dHBzOi8vd3d3LmNhcHRlcnJhLmNvLnVrL3gvMTY5NjQvc3RyaXBlP2NsaWNrb3V0X3R5cGU9bGFuZGluZ19wYWdlJmNsaWNrb3V0X3BsYWNlbWVudD1yZXZpZXctaW5kZXgtbGFuZGluZ19wYWdlLW5hbWUmZWNvbW1lcmNlX2xpc3RfbmFtZT1SZXZpZXdzK1N3aXRjaGVkK0Zyb20maXRlbV9pbmRleD0xbQAAABBsYXN0X2NhdGVnb3J5X2lkYgAALzJtAAAAF2xhc3RfZ2xvYmFsX2NhdGVnb3J5X2lkYgAABr0.J27qkxCl0-Wi0POin0K4Rt6QfLbuOFXlXSYzrIqiMWo; cf_clearance=U8HLg6DCUPIUYYesCtQAvcupnQkhIpWwSSrAfmYXaZc-1726939452-1.2.1.1-PndSG14Wgkj7Fewzt1RwNVc4x0HSyzU.Xkof1lD4Lm1Dn9yJDTvDLTKdozG7ZXrYRo76v4bro3AwEfb4NSZtOe8rORtNaMkDR.3WehwTFO.Pv6sI2_Twcdg7ndDil97DSJ_N6KmUvzTE_pqYFiU6qRXW7inQ1b_Rdj5dOPkx1nUsxY1qpEEHxU8i9gut_oTtpcOflDkLVSxb3MyFHatQhhTl4pCm9eREOopfwzOzPRDuuFFlfl0z2XqIMxWUG5wOSYP_AzaXEC6lxUz.MkKXvDyQ8Hzn_Tp4MEhbfPp_SYX_3c5rRPXlcWjVa4Ku5JPxIYrjRFZ0Li5cawR9HQ6mqKTU67_7yAyddeAga1suSUV7EjBTUHvmXJQtzi9fY.71; OptanonConsent=isGpcEnabled=0&datestamp=Sat+Sep+21+2024+22%3A24%3A14+GMT%2B0500+(Pakistan+Standard+Time)&version=202403.2.0&browserGpcFlag=0&isIABGlobal=false&hosts=&consentId=8d876048-9167-4cea-bee6-b87bc66d6e82&interactionCount=1&isAnonUser=1&landingPath=NotLandingPage&groups=C0004%3A1%2CC0002%3A1%2CC0003%3A1%2CC0001%3A1&intType=1&geolocation=%3B&AwaitingReconsent=false; _uetsid=1fc8f340775c11ef97996f477a33e369; _uetvid=1fc917b0775c11ef89f1ff661e96ecbb; fs_lua=1.1726941721078; fs_uid=#o-19TW98-na1#efef0299-b7b2-4902-abc5-00b68a0039a4:d9dcdd3f-c7c6-489f-8412-dfdfa14f7c9f:1726941721078::1#/1758378418; _clsk=8dzhcb%7C1726941721238%7C1%7C1%7Cq.clarity.ms%2Fcollect; _dd_s=isExpired=1; _ga_0WNG69R0Z3=GS1.1.1726941723.6.0.1726941723.0.0.0"),
        "Priority": "u=0, i",
        "Sec-CH-UA": '"Google Chrome";v="129", "Not=A?Brand";v="8", "Chromium";v="129"',
        "Sec-CH-UA-Mobile": "?0",
        "Sec-CH-UA-Platform": '"Windows"',
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "cross-site",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
    }

# Initialize the SQL database (SQLite as an example)
db = dataset.connect('sqlite:///webpages.db')

# Table to store the URLs and HTML content
table = db['pages']

# Step 1: Scrape URLs and store them in the database with a `scraped` column
def store_urls():
    url_list = []
    for index in range(1, 46):
        while True:
            try:
                time.sleep(2)
                if index == 1:
                    url = "https://www.capterra.co.uk/directory/20052/point-of-sale/software"
                else:
                    url = f"https://www.capterra.co.uk/directory/20052/point-of-sale/software?page={index}"
                # print(f"Reached Original Index {index}")

                # Send the GET request
                response = requests.get(url,proxies=proxy)
                # response.encoding = "utf-8"  # Manually set encoding if needed
                # html_content = response.text.encode('utf-8', 'ignore').decode('utf-8', 'ignore')
                # Check if the request was successful
                if response.status_code == 200:
                    # print(html_content)        
                    # Parse the response content
                    soup = BeautifulSoup(response.content, 'html.parser')
                    all_cards = soup.find_all("div", class_="product-card")
                    print(f"Found {len(all_cards)} product cards for index {index}")
                    
                    # Extract URLs and store them in the database with `scraped = False`
                    for card in all_cards:
                        a = card.find("a", class_="mos-star-rating")
                        if a:
                            page_url = a.get("href")
                            if page_url:
                                page_url=page_url.replace("#reviews","")
                                url_list.append(page_url)
                                table.insert({
                                    'url': page_url,
                                    # 'html_content': None,  # Content will be fetched later
                                    'scraped': False  # Initially mark as not scraped
                                })
                        else:
                            h2 = card.find("h2",class_="h5 fw-bold mb-2")
                            if h2:
                                a_h2=h2.find("a",recursive=False)
                                if a_h2:
                                    page_url = a_h2.get("href")
                                    if page_url:
                                        url_list.append(page_url)
                                        # print(page_url)
                                        table.insert({
                                            'url': page_url,
                                            # 'html_content': None,  # Content will be fetched later
                                            'scraped': False  # Initially mark as not scraped
                                        })
                                    else:
                                        print("Page Url of a not found")
                            else:
                                print(f"h2 not found")
                                    
                    # print(f"Stored {len(all_cards)} URLs for page {index}")
                    break
                else:
                    print(f"Failed to retrieve the page. Status code: {response.status_code}")
            except Exception as e:
                print(f"Exception occur {e}")
    print(len(url_list))
# Step 2: Fetch HTML content for URLs that are not yet scraped
def fetch_html_content(url):
    response = requests.get(url, proxies=proxy)
    if response.status_code == 200:
        return response.content
    else:
        return None

# Step 3: Scrape the stored URLs whose `scraped` column is set to False
def scrape_and_store():
    # Fetch all URLs that are not yet scraped
    urls_to_scrape = table.find(scraped=False)
    
    for record in urls_to_scrape:
        url = record['url']
        print(f"Processing URL: {url}")

        try:
            html_content = fetch_html_content(f"https://www.capterra.co.uk{url}")

            if html_content:
                # Update the record with the HTML content and mark as scraped
                table.update({
                    'id': record['id'],  
                    'scraped': True
                }, ['id'])
                print(f"Successfully scraped and updated: {url}")
            else:
                print(f"Failed to scrape: {url}")
            iteration_count = 0  # Track the number of iterations for each URL
            totaliteration=0
            while True:
                
                iteration_count += 1
                if iteration_count==1:
                    # Simulate a new page URL or API endpoint
                    page_url = f"https://www.capterra.co.uk{url}"
                    html_content = fetch_html_content(page_url)
                    # print(page_url)
                    soup=BeautifulSoup(html_content,"html.parser")
                    all_li=soup.find_all("li",class_="page-item")
                    lenght=len(all_li)
                    # print(f"Lenght is {lenght}")
                    totaliteration=int(all_li[lenght-2].text)
                else:
                    page_url = f"https://www.capterra.co.uk{url}?page={iteration_count}"
                    html_content = fetch_html_content(page_url)
                table.insert({
                    'url': page_url,
                    'html_content': html_content,
                })
                if iteration_count==totaliteration:
                    break
                print(f"Saved content for: {page_url}")
                time.sleep(0.1)

        except Exception as e:
            print(f"Exception occurred while scraping {url}: {e}")
            continue
def scrap_review_pages_url():
    review_table=db["review"]
    urls_to_scrape = table.find(scraped=False)
    # lst=list(urls_to_scrape)
    # print(len(lst))
    for record in urls_to_scrape:
        try:
            url=record["url"]
            print(record['id'])
            page_url = f"https://www.capterra.co.uk{url}"
            print(page_url)
            html_content = fetch_html_content(page_url)
            soup=BeautifulSoup(html_content,"html.parser")
            all_li=soup.find_all("li",class_="page-item")
            lenght=len(all_li)
            totaliteration=1
            if lenght>1:
                totaliteration=int(all_li[lenght-2].text)
            print(f"Total Iteration found {totaliteration}")
            review_table.insert({
                    'url': f"https://www.capterra.co.uk{url}"
                })
            for index in range(2,totaliteration+1):
                review_table.insert({
                    'url': f"https://www.capterra.co.uk{url}?page={index}"
                })
            table.update({
                'id': record['id'],  
                'scraped': True
            }, ['id'])
        except Exception as e:
            print(e)
def store_html_content():
    review_table=db["review"]
    # columns = review_table.columns
    # # Print the columns
    # print("Existing columns in the 'products' table:")
    # for column in columns:
    #     print(column)
    review_table.create_column_by_example("scraped", True)
    review_table.create_column_by_example("html_content", "")
    records=review_table.find(scraped=None)
    index=0
    for record in records:
        try:
            # index=index+1
            url=record["url"]
            index=record["id"]
            html_content=fetch_html_content(url)
            if html_content:
                # Step 4: Update the record with the fetched HTML content and mark 'scraped' as True
                record["html_content"] = html_content
                record["scraped"] = True    
                # Step 5: Update the record in the database based on 'url'
                review_table.update(record, ['url'])
                print(f"{index}-Successfully stored HTML content for {url} and marked as scraped.")
            else:
                print(f"Failed to fetch content for {url}.")
        except Exception as e:
            print(f"Exception has been Occur {e}")
        # break
if __name__ == "__main__":
    # Step 1: Scrape the URLs and store them in the database
    # store_urls()
    # scrap_review_pages_url()
    store_html_content()
    # Step 2: Scrape the stored URLs from the database and store HTML content
    # scrape_and_store()
