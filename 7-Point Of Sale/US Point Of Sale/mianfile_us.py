'''This is the main file of this Project that start from step 1 and go to last step,
The difficult step is for selenium scraping whihh
is very difficult and need to do with proper time
Further ,the first function in which urls is scraped is using request library,
some time all request got successfull and sometime temporary block 
but i put while request to make sure each time urls must be scraped
Further this project is totally managed by database approach
'''
import requests
from bs4 import BeautifulSoup
import time
import dataset
import pandas as pd
import re
import traceback
import dataset
from seleniumbase import Driver
from time import sleep
import random
from parsel import Selector
# Step 1: Scrape URLs and store them in the database with a `scraped` column
def check_reg(star_span):
    pattern = r'\((\d+)\)'
    # Search for the first match
    match = re.search(pattern, star_span.text)

    # If a match is found, extract and convert it to an integer
    if match:
        integer = int(match.group(1))
        return integer
        # print(integer)
    else:
        integer=0
        print("No number found.")
        return integer
        
def store_urls(table):
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "max-age=0",
        "Cookie": 'return_user=1909391822.1726842400|Thu Sep 26 2024 09:13:12 GMT+0500 (Pakistan Standard Time); return_user_session=1909391822.1726842400|Tue Sep 24 2024 12:34:22 GMT+0500 (Pakistan Standard Time)|returning; LD_UserID=7ffeb86c-85e7-4e24-a224-3eba0fe17f30; _pxvid=574ba303-775c-11ef-bf92-656bb2666582; _gcl_au=1.1.464833817.1726842404; _fbp=fb.1.1726842406201.569274872866015393; seerid=5dbfe5d7-b332-491b-9cac-c8d96fbb8aca; ELOQUA=GUID=6D69BCDEA6824E28A84AD77B77567014; return_user=1909391822.1726842400|Fri Sep 20 2024 19:27:44 GMT+0500 (Pakistan Standard Time); g_state={"i_p":1727768080587,"i_l":3}; _pxhd=7/CgDWpRLfEX1qdgXZAO52pLKE8v5p95E6xL9r2Iq0iYAX-xWAIoVV2oMOYDPUL5zltNNjtRCpiHh9HYJySd/w==:zTqvgll1zDUwUdY7V-4nNIbAtwW1S1/nCOscx9Qde/ZoOZS2Rn02hlW7kCbQ4ni3MgHfVTV-FoQt4ohHQCoAaYne5wAFMaOEvlMTJQYR9Vg=; _gid=GA1.2.321583793.1727323992; device=Desktop; country_code=PK; _capterra2_session=cf21bec8fd1743fe96f52927b5509e32; pxcts=ac3eeb2a-7bbd-11ef-8300-72cbba806b5c; seerses=e; AMCVS_04D07E1C5E4DDABB0A495ED1%40AdobeOrg=1; AMCV_04D07E1C5E4DDABB0A495ED1%40AdobeOrg=-637568504%7CMCIDTS%7C19993%7CMCMID%7C78705225053617251862749518570512246727%7CMCAAMLH-1727928806%7C3%7CMCAAMB-1727928806%7CRKhpRz8krg2tLO6pguXWp5olkAcUniQYPHaMWWgdJ3xzPWQmdj0y%7CMCOPTOUT-1727331206s%7CNONE%7CvVersion%7C5.1.1; _clck=11rovde%7C2%7Cfpi%7C0%7C1724; x-saved-product-ids=251808%2C251808%2C251808%2C251808%2C251808%2C251808%2C251808%2C251808%2C251808%2C251808%2C251808%2C251808%2C251808%2C251808%2C251808%2C251808%2C251808%2C251808%2C222572%2C222572; cf_clearance=6kZfoyQyVDR8jS7U_YRiLgDkDdIam_R9r3XqXkNjG9g-1727324715-1.2.1.1-E01Ac.ciODLwh3XEvNkcPtAeJXekj_CTKANlY0hv6NaWoWNXS9SFL50ZXfqAtAb.FEHmelpBWMogJjcrlNrD7IjmYfNhq2UfY.3ou1uw6oCM68hL2DQNYHVHaaBDrmxWquKwUe2kj_ZBblPABqPSaCLl7uvo2qQp3VaciJZBkb4rgTc_22mKVqq50UwHpYYpRYkzVByJwHpqpcLksUxO48cK0RNsBD.kvmW0cJF80nhNVAaq5dZaU5aX_y1fHlJxRoozWTaMcQFOeGMMzVRS2laF4gU7enu.M5tnve8qaWsFvLf6Zl57XsajGEnZIXn6iC8OcVvFY297pvG_lszJF8ff583VZY7i_ejNSAmXot4mmW0Fsj05zDgCir6qPweE; OptanonConsent=isGpcEnabled=0&datestamp=Thu+Sep+26+2024+09%3A26%3A47+GMT%2B0500+(Pakistan+Standard+Time)&version=202403.2.0&browserGpcFlag=0&isIABGlobal=false&hosts=&consentId=57b23c63-e075-4c67-bd34-9763526ba66e&interactionCount=1&isAnonUser=1&landingPath=NotLandingPage&groups=C0001%3A1%2CC0002%3A1%2CC0003%3A1%2CC0004%3A1%2CC0007%3A1&AwaitingReconsent=false; _ga=GA1.1.1909391822.1726842400; fs_uid=#18VAT4#01ed11fd-4325-4abc-a909-150734fb042d:1ff5165b-5155-4770-9b74-f15bdbb82419:1727324006469::12#/1758378497; _uetsid=ad8faa807bbd11efb594058612e8e12b; _uetvid=5d997cf0775c11efbca085060bc28e37; _ga_M5DGBDHG2R=GS1.1.1727324004.8.1.1727324810.56.0.0; fs_lua=1.1727325609659; _px3=c1bf35a47a47a9ee1fc5be5845b6876581128f72a40f4e07469b02b415aa2b9f:EmyQZ8hc3eBUGrd3CIkA3aNooPEO6ugnPdiytCYx34OdyQqhMJN2AscwkBQ3bxYjUu2XyieJVtfEaBOxYR0tAg==:1000:YxvKaKJ6Zx7Ow/UFsoSScJeSINAS19iYQBOMQSiYWtN7MhVlqm1ssyWVdCFTHiJllMcnEUSXcJviHCbsus16wqU1p0DGOK+sx/t7P+aEIhE3i8ZAEEo/ONaJzl7PCjAlD2oX1UZydWLydYYx5Im5BOO2RPalm2taQ/0NSAir3ma7RaaCvDZ3POwcYFUoyfLIX60R/1fdDSLGrtnhvKJrq9ZToFiS7F0GvQf90d5KhTM=; _pxde=1f9be9371a738b4555164f425edb3e2140bbef4bbc7404429911edb0ebaf2240:eyJ0aW1lc3RhbXAiOjE3MjczMjU4NTc3NzksImZfa2IiOjAsImlwY19pZCI6W119; __cf_bm=..grlog7noRAzomUIdDG7coZ7P3zYOrp6nX_gQdCeb0-1727326098-1.0.1.1-ytls.UbZFJ4e1lih2Y5DXg01Zwx3GUnYDUGXCxr_ksIwj8qII8cdQtBrOxS1m2WVZy0zU48d5.GVGF2tXrqmzg; _cfuvid=_Bnnrh61lXxhWhwyFiy05ltDZ8l1VdBGXRHcG4Qjhi8-1727326098833-0.0.1.1-604800000; _dd_s=rum=0&expire=1727327029259&logs=1&id=1f5d943b-4168-45ea-aa6d-f73bd130f05e&created=1727323991908',
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
    proxy = {
    'http': 'http://198.204.241.50:17047',
    'https': 'http://198.204.241.50:17047'
}
    url_list = []
    for index in range(1, 45):
        while True:
            try:
                time.sleep(2)
                if index == 1:
                    url = "https://www.capterra.com/point-of-sale-software/"
                else:
                    url = f"https://www.capterra.com/point-of-sale-software/?page={index}"
                # print(f"Reached Original Index {index}")

                # Send the GET request
                response = requests.get(url,headers=headers)
                # response.encoding = "utf-8"  # Manually set encoding if needed
                # html_content = response.text.encode('utf-8', 'ignore').decode('utf-8', 'ignore')
                # Check if the request was successful
                if response.status_code == 200:
                    # print(html_content)        
                    # Parse the response content
                    soup = BeautifulSoup(response.content, 'html.parser')
                    main_div = soup.find("div", {"data-testid":"product-card-stack"})
                    all_cards=main_div.find_all("div",recursive=False)
                    print(f"Found {len(all_cards)} product cards for index {index}")
                    
                    # Extract URLs and store them in the database with `scraped = False`
                    for card in all_cards:
                        a = card.find("a", class_="star-rating-root")
                        company_name=card.find("h2").text.strip()
                        
                        if a:
                            star_span=a.find("span",class_="star-rating-label")
                            # print(star_span.text)
                            star_list=star_span.text.split("(")
                            company_rating=star_list[0]
                            integer=check_reg(star_span)
                            page_url = a.get("href")
                            if page_url:
                                # page_url=page_url.replace("#reviews","")
                                url_list.append(page_url)
                                table.insert({
                                    'Name':company_name,
                                    'url': page_url,
                                    "type": 1,
                                    "total_rating":integer,
                                    "Company Overall Rating": company_rating,
                                    # 'html_content': None,  # Content will be fetched later
                                    'scraped': False  # Initially mark as not scraped
                                })
                        else:
                            a=card.find('div',class_="star-rating-root")
                            star_span=a.find("span",class_="star-rating-label")
                            star_list=star_span.text.split("(")
                            company_rating=star_list[0]
                            integer=check_reg(star_span)
                            a=card.find("a",class_="link")
                            if a:
                                page_url = a.get("href")
                                if page_url:
                                    url_list.append(page_url)
                                    table.insert({
                                    'Name':company_name,
                                    'url': page_url,
                                    "type": 2,
                                    "total_rating":integer,
                                    "Company Overall Rating": company_rating,
                                    # 'html_content': None,  # Content will be fetched later
                                    'scraped': False  # Initially mark as not scraped
                                })

                           
                            else:
                                print("Page Url of a not found")         
                    # print(f"Stored {len(all_cards)} URLs for page {index}")
                    break
                else:
                    print(f"Failed to retrieve the page. Status code: {response.status_code}")
            except Exception as e:
                traceback.print_exc()
                print(f"Exception occur {e}")

def check_for_blocks(driver):
    sleep(3)
    block_sel = Selector(text=driver.page_source)
    if 'www.capterra.com' in block_sel.xpath('//h1/text()').get(default='') != '':
        input('bypass any blocks')

    block_sel = Selector(text=driver.page_source)
    if block_sel.xpath('//div[@class="px-captcha-header"]/text()').get(default='') == 'Before we continue...':
        input('bypass any blocks')

    block_sel = Selector(text=driver.page_source)
    
    # Check for the h2 tag with the text "See how this software works with your current tools"
    if block_sel.xpath('//h2[contains(text(), "See how this software works with your current tools")]').get() is not None:
        input('bypass any blocks')
def scrap_by_selenium(table,review_table):
    driver = Driver(uc=True)
    db = dataset.connect('sqlite:///webpages2.db')
    # Table to store the URLs and HTML content
    table = db['pages']
    review_table = db['review']
    unscraped_rows = table.all(scraped=False,type=1)
    for product in unscraped_rows:
        url=f"https://www.capterra.com/{product['url']}"
        print(url)
        # if product['id']>7:
        print(f"Processing {product['url']}")
        url=f"https://www.capterra.com/{product['url']}"
        driver.get(url)
        check_for_blocks(driver)
        # print("Huzaifa Saeed")
        iteration=int(product['total_rating']/25)+2
        print(f"Total Iteration is:{iteration} and total Rating is {product['total_rating']}")
        for i in range(1,iteration):
            check_for_blocks(driver)
            print(f"Iteration No:  {i}")
            try:
                random_number = random.randint(7, 15)
                sleep(random_number)
                print(f"Random Sleep Number: {random_number}")
                button = driver.find_element("css selector", '[data-testid="show-more-reviews"]')
                button.click()
            except Exception as e:
                print(e)
                continue
        random_number = random.randint(1,3)
        sleep(random_number)
        # Store html in the database after the element has appeared
        db["review"].upsert({"url": product["url"], "html": driver.page_source}, ["url"])
        # Mark the product as scraped
        product.update({"scraped": True})
        table.update(product, ["id"])

def parse_html_content(review_table):
    main_list=[]
    # db = dataset.connect('sqlite:///final_database.db')
    # review_table = db['merged_listings']  #review
    unscraped_rows = review_table.all()

    print(review_table.count())
    index=0
    for single_company in unscraped_rows:
        index=index+1
        # if index==5 or index==8:
        #     continue
        print(f"Index:{index}")
        print(single_company['url'])
        html_content=single_company["html"]
        # Parse the HTML content with BeautifulSoup
        soup = BeautifulSoup(html_content, 'html.parser')
        # print(soup.text)
        # Find all div elements with class 'review-card'
        review_cards = soup.find_all('div', {'data-test-id':'review-card'})
        print(len(review_cards))
        vendor=single_company["Name"]
        def check_existence(item):
            if item:
                return item.text.strip()
            else:
                return ""
        # Iterate through each div and print its content or process further
        for card in review_cards:
            ease_of_use=customer_services=value_for_money=features=likelihood=overall_rating=""
            date=review_source=source=review_name=review_role=country=used_software=employess=industry=""
            main_div=card.find("div",recursive=False)
            sub_div=main_div.find_all("div",recursive=False)
            user_info_div=sub_div[0]
            review_div=main_div.find('div',{"data-testid":"review-content"})

            review_name_div=user_info_div.find("div",{"data-testid":"reviewer-full-name"})
            # print(review_name_div)
            if review_name_div:
                dialog_div=review_name_div.find('div',{"role":"dialog"})
                # print(dialog_div)
                if dialog_div:
                    dialog_div.decompose()
                review_name=review_name_div.text.strip()
            # review_name=check_existence()
            # review_name=check_existence(user_info_div.find("div",{"data-testid":"reviewer-full-name"}))

            review_role=check_existence(user_info_div.find("div",{"data-testid":"reviewer-job-title"}))

            

            industry=check_existence(user_info_div.find("span",{"data-testid":"reviewer-industry"}))
            employess=check_existence(user_info_div.find("span",{"data-testid":"reviewer-company-size"}))

            used_software=check_existence(user_info_div.find("div",{"data-testid":"reviewer-time-used-product"})).replace("Used the software for:","").strip()
            
            ease_of_use=check_existence(user_info_div.find("div",{"data-testid":"Ease of Use-rating"}))
            overall_rating=check_existence(user_info_div.find("div",{"data-testid":"Overall Rating-rating"}))
            customer_services=check_existence(user_info_div.find("div",{"data-testid":"Customer Service-rating"}))
            features=check_existence(user_info_div.find("div",{"data-testid":"Features-rating"}))
            value_for_money=check_existence(user_info_div.find("div",{"data-testid":"Value for Money-rating"}))

            #Detail For likelihood
            likelihood_div=user_info_div.find("div",{"data-testid":"Likelihood to Recommend-rating"})
            if likelihood_div:
                progress=likelihood_div.find("progress")
                max=progress.get("max")
                value=progress.get("value")
                likelihood=f"{value}"

            #detail For Review Source
            review_source_div=user_info_div.find("div",{"data-testid":"reviewer-source"})
            if review_source_div:
                review_source=check_existence(review_source_div.find("div",{"role":"dialog"}))
            
            source=check_existence(user_info_div.find("div",{"data-testid":"source-site"})).replace("Source:","").strip()
            date=check_existence(user_info_div.find("div",{"data-testid":"review-written-on"}))

            # Now Scrape Review Content
            review_title=pros=cons=comments=alternative_considered=reason_for_choosing=reason_for_switiching=switch_from=""

            review_title=check_existence(review_div.find("div",class_="mt-2xl text-lg font-bold md:mt-0")).replace('"', '')
            # print(review_title)
            comments=check_existence(review_div.find("div",{"data-testid":"overall-content"})).replace("Overall:","").strip()
            pros=check_existence(review_div.find("div",{"data-testid":"pros-content"})).replace("Pros:","").strip()
            cons=check_existence(review_div.find("div",{"data-testid":"cons-content"})).replace("Cons:","").strip()
            switch_from=check_existence(review_div.find("div",{"data-testid":"switched-products"})).replace("Switched From:","").strip()
            alternative_considered=check_existence(review_div.find("div",{"data-testid":"alternatives-considered"})).replace("Alternatives Considered:","").strip()
            # alternative_considered=check_existence(review_div.find("div",{"data-testid":"alternatives-considered"})).replace("Alternatives Considered:","").strip()

            # Scraped Reason for switching
            reason_for_switiching_div=review_div.find("div",{"data-testid":"reasons-for-switching-content"})
            if reason_for_switiching_div:
                reason_for_switiching_div.find("strong").decompose()
                reason_for_switiching=reason_for_switiching_div.text.strip()
            

            reason_for_choosing_div=review_div.find("div",{"data-testid":"reasons-for-choosing-content"})
            if reason_for_choosing_div:
                reason_for_choosing_div.find("strong").decompose()
                reason_for_choosing=reason_for_choosing_div.text.strip()
            # reason_for_switiching=check_existence(review_div.find("div",{"data-testid":"reasons-for-switching-content"})).replace("Reasons for Switching to","").strip()

            obj={
                        "Vendor":vendor,
                        "Review Date": date,
                        "Review Source":review_source,
                        "Source":source,
                        "Reviewer Name":review_name,
                        "Review Role":review_role,
                        "Industry":industry,
                        "Number of Employees":employess,
                        "Used Software For":used_software,
                        "Reviewer Company":"",
                        "Country":country,
                        "Review Title":review_title,
                        "Overall Feedback":comments,
                        "Pros":pros,
                        "Cons":cons,
                        "Alternative Considered": alternative_considered,
                        "Reasons for Choosing Vendor": reason_for_choosing,
                        "Switched From (Previos Vendor)":switch_from,
                        "Reasons for Switching to Vendor":reason_for_switiching,
                        "Overall Rating (Out of 5)":overall_rating,
                        "Ease of Use Rating (Out of 5)":ease_of_use,
                        "Customer Support Rating (Out of 5)":customer_services,
                        "Value for Money Rating (Out of 5)":value_for_money,
                        "Features Rating (Out of 5)": features,
                        "Liklihood to Recommend (Out of 10)":likelihood,    
                    }
            main_list.append(obj)
    
    return main_list
            
def table_to_excel(table, file_name):
    # Fetch all rows from the table
    rows = list(table.all())

    # If there are no rows, return without creating a file
    if not rows:
        print("No data in the table to export.")
        return

    # Convert rows to a pandas DataFrame
    df = pd.DataFrame(rows)

    # Export DataFrame to Excel file
    df.to_excel(file_name, index=False)
    print(f"Data exported to {file_name}")
    # print(len(url_list))



def main():
    # Initialize the SQL database (SQLite as an example)
    db = dataset.connect('sqlite:///webpages_us.db')

    # Table to store the URLs and HTML content
    table = db['pages']
    review_table = db['review']
    final_data=db["finaldata"]
    # Step 1: Scrape all company URLs(Some additional Information) fromm main page and store them in the database
    store_urls(table)
    # Step 2: Scrape all stored urls by using selenium and store html content in Database
    scrap_by_selenium(table,review_table)
    # Step 3: Parse html content (get from review table) and convert into another table named as 
    data_list=parse_html_content(review_table)
    #step 4 Insert final data list into table before creating the excel file
    final_data.insert_many(data_list)
    # Step 5 : Now create Excel file from final_data table
    table_to_excel(final_data,"Final_Data_US.xlsx")
    

if __name__ == "__main__":
    main()
