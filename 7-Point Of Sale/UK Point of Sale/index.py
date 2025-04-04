import requests
from bs4 import BeautifulSoup
import time
import dataset
# Define the URL
url_list=[]
proxy = {
    'http': 'http://198.204.241.50:17047',
    'https': 'http://198.204.241.50:17047'
}
for index in range(1,46):
    time.sleep(2)
    if index==1:
        url = "https://www.capterra.com/point-of-sale-software/"
    else:
        url = f"https://www.capterra.com/point-of-sale-software/?page={index}"
    print(f"Reached Original INdex is {index}")
    # Define the headers
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

    # Send the GET request
    response = requests.get(url)
    # jhj gh hg ghhj hgg yyu po rt wewqtds sdagh gkjkjklj';/nm,n bvbncvcvx xzxcsadew
    # Check if the request was successful
    if response.status_code == 200:        
        # Parse the response content
        soup = BeautifulSoup(response.content, 'html.parser')
        with open("output.html", "w", encoding="utf-8") as file:
            file.write(response.text)
        all_cards=soup.find_all("div",class_="product-card")
        print(len(all_cards))    
        for card in all_cards:
            a=card.find("a",class_="mos-star-rating")
            # print(a.get("href"))
            if a:
                url_list.append(a.get("href"))
            # break
        # print(len(url_list))
    else:
        print(f"Failed to retrieve the page. Status code: {response.status_code}")
db = dataset.connect('sqlite:///webpages.db')

# Table to store the URL and HTML content
table = db['pages']

# Function to make a GET request and return HTML content
def fetch_html_content(url):
    # headers = {
    #     "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
    # }
    
    response = requests.get(url,proxies=proxy)
    
    # If the request is successful, return the content
    if response.status_code == 200:
        return response.content
    else:
        return None

# Main function to iterate over the URLs
def scrape_and_store(url_list):
    for url in url_list:
        print(f"Processing URL: {url}")
        
        iteration_count = 0  # Track the number of iterations for each URL
        totaliteration=0
        while True:
            
            iteration_count += 1
            if iteration_count==1:
                # Simulate a new page URL or API endpoint
                page_url = f"https://www.capterra.co.uk{url}"
                html_content = fetch_html_content(page_url)
                soup=BeautifulSoup(html_content,"html.parser")
                all_li=soup.find_all("li",class_="page-item")
                lenght=len(all_li)
                totaliteration=int(all_li[lenght-2].text)
            else:
                page_url = f"https://www.capterra.co.uk{url}?page={iteration_count}"
                html_content = fetch_html_content(page_url)
            
            # if not html_content:
            #     print(f"No content found for {page_url}, stopping iteration.")
            #     break  # Stop iterating if no content is found
            
            # Save the HTML content into the database
            table.insert({
                'url': page_url,
                'html_content': html_content,
            })
            if iteration_count==totaliteration:
                break
            print(f"Saved content for: {page_url}")
            time.sleep(0.1)

# scrape_and_store(url_list)
