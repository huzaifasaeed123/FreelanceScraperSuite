'''
This is the main File whihc combine each and every step from start to bottom and i have follow database approach in this project also

'''
import requests
from bs4 import BeautifulSoup
import time
import dataset
import dateparser
import pandas as pd
import re

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
    # print(len(url_list))
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
        while True:
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
                break
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
        while True:
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
                    break
                else:
                    print(f"Failed to fetch content for {url}.")
            except Exception as e:
                print(f"Exception has been Occur {e}")
        # break
def date_parser(date_str):
    parsed_date = dateparser.parse(date_str)
    
    # Extract only the date (if parsed_date is not None)
    if parsed_date:
        return parsed_date.date().strftime("%Y-%m-%d")
    else:
        return date_str

def parse_review_1st(html_content,url,main_list):
    soup = BeautifulSoup(html_content, 'html.parser')
    vendor=ease_of_use=customer_services=value_for_money=features=likelihood=overall_rating=""
    h1=soup.find("h1",class_="h3 mb-1")
    vendor=h1.text.strip()
    overall_rating_div=h1.find_next_sibling()
    main_span=overall_rating_div.find("span",class_="mos-star-rating",recusive=False)
    overall_rating=main_span.find("span").text.strip()
    rating_section=soup.find('section',class_="product-rating-section")
    if rating_section:
        all_divs=rating_section.find_all("div",class_="row")
        for div in all_divs:
            if "Ease of Use" in div.text:
                span=div.find("span",class_="mos-star-rating")
                if span:
                    ease_of_use=span.text.strip()
                    # print(ease_of_use)
            elif "Customer Service" in div.text:
                span=div.find("span",class_="mos-star-rating")
                if span:
                    customer_services=span.text.strip()
                    # print(customer_services)
            elif "Value for Money" in div.text:
                span=div.find("span",class_="mos-star-rating")
                if span:
                    value_for_money=span.text.strip()
                    # print(value_for_money)
            elif "Features" in div.text:
                span=div.find("span",class_="mos-star-rating")
                if span:
                    features=span.text.strip()
                    # print(features)
        likelihood_h3=soup.find("h3",id="likeliHoodMeterLbl")
        if likelihood_h3:
            div=likelihood_h3.find_next_sibling()
            likelihood=div.text.strip().replace("/10","")

    review_cards=soup.find_all("div",class_="review-card")
    for card in review_cards:
        pros=cons=comments=alternative_considered=reason_for_choosing=reason_for_switiching=switch_from=""
        date=review_source=source=review_name=review_role=country=review_title=used_software=employess=industry=""
        row=card.find("div",class_="row")
        main_two_divs=row.find_all("div",recursive=False)
        first_div=main_two_divs[0].find("div",class_="row").find_all("div",recursive=False)
        # print(first_div[1].text)
        # print(first_div[2].text)
        name=first_div[1].find("div",class_="h5").text.strip()
        divs=first_div[1].find_all("div",recursive=False)
        review_name_div=first_div[1].find("div",class_="h5",recursive=False)
        review_name=review_name_div.text.strip()
        for div in divs:
            # print(div.text)
            if "US" in div.text or "UK" in div.text or "Canada" in div.text or "Australia" in div.text or "Spain" in div.text:
                role_list=div.text.strip().split(" in ")    
                # print(f"Role: {role_list[0]}  Country: {role_list[1]}")
                if len(role_list)==2:
                    review_role=role_list[0]
                    country=role_list[1]
                else:
                    review_role=""
                    country=role_list[0]
        divs_bottoms=first_div[2].find_all("div",recursive=False)
        
        for div in divs_bottoms:
            if "Employe" in div.text:
                split_data=div.text.strip().split(", ")
                if len(split_data)==3:
                    industry=f"{split_data[0]},{split_data[1]}"
                    employess=split_data[2]
                elif len(split_data)==2:
                    industry,employess=split_data
                else:
                    industry=split_data[0]
                    employess=""
                # print(f"Industry: {industry}  while Employess:{employess}")
            elif "Used the Software for:" in div.text:
                used_software=div.text.strip().replace("Used the Software for:","")
                # print(used_software)
            elif "Source:" in div.text:
                source=div.text.strip().replace("Source:","")
                # print(f"Source Given:{source}")
            elif "Reviewer Source" in div.text:
                tool_item=div.find("sylar-tooltip")
                review_source=tool_item.get("data-bs-title")
                # print(f"Review Source::{review_source}")
        
        # second_div=main_two_divs[1].find("div",recursive=False)
        h3_review_title=main_two_divs[1].find("h3",class_="h5",recursive=False)
        # second_div=h3_review_title.find_next_sibling()
        if h3_review_title:
            review_title=h3_review_title.text.strip()
            second_div=h3_review_title.find_next_sibling()
            # print(f"Review Title: {review_title}")
        # print(second_div)
            span=second_div.find("span",class_="mos-star-rating")
            # print(f"Individual Rating is {span.text.strip()}")
            span.decompose()
            second_span=second_div.find("span")
            date=date_parser(second_span.text.strip())
        # print(f"Date is {second_span.text.strip()}")
        second_div_p=main_two_divs[1].find_all("p",recursive=False)
        for p in second_div_p:
            svg=p.find("svg")
            bold_span=p.find("span",class_="fw-bold")
            if svg:
                if "Pros:" in p.text:
                    pros_p=p.find_next_sibling()
                    pros=pros_p.text.strip()
                elif "Cons" in p.text:
                    cons_p=p.find_next_sibling()
                    cons=cons_p.text.strip()
            if bold_span:
                if "Comments:" in bold_span.text:
                    bold_span.decompose()
                    comments=p.text.strip()
                elif "Alternatives Considered:" in bold_span.text:
                    bold_span.decompose()
                    alternative_considered=p.text.strip()
                elif "Reasons for Switching to" in bold_span.text:
                    bold_span.decompose()
                    reason_for_switiching=p.text.strip()
                elif "Switched From:" in bold_span.text:
                    bold_span.decompose()
                    switch_from=p.text.strip()
                elif "Reasons for Choosing" in bold_span.text:
                    bold_span.decompose()
                    reason_for_choosing=p.text.strip()
        # print(f"Pros: {pros} \n  Cons:{cons}")
        obj={
            "URL":url,
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
def parse_review_2nd(html_content,url,main_list):
    soup = BeautifulSoup(html_content, 'html.parser')
    vendor=ease_of_use=customer_services=value_for_money=features=likelihood=overall_rating=""
    h1=soup.find("h1",class_="h3")
    vendor=h1.text.strip()
    rating_section=soup.find('div',class_="review-overview")
    if rating_section:
        heading_div=rating_section.find("h3",class_="h6")
        if heading_div:
            div_contain=heading_div.find_next_sibling()
            all_divs=div_contain.find_all("div",class_="row")
            for div in all_divs:
                if "Overall" in div.text:
                    overall_rating=div.text.replace("Overall","").strip()
                        # print(ease_of_use)
                if "Ease of Use" in div.text:
                    ease_of_use=div.text.replace("Ease of Use","").strip()
                        # print(ease_of_use)
                elif "Customer Service" in div.text:
                    customer_services=div.text.replace("Customer Service","").strip()
                    # print(customer_services)
                elif "Value for Money" in div.text:
                    value_for_money=div.text.replace("Value for Money","").strip()
                        # print(value_for_money)
                elif "Features" in div.text:
                    features=div.text.replace("Features","").strip()
                    # print(features)
        likelihood_h3=soup.find("h3",id="likeliHoodMeterLbl")
        if likelihood_h3:
            div=likelihood_h3.find_next_sibling()
            likelihood=div.text.strip().replace("/10","")

    review_cards=soup.find_all("div",class_="review-card")
    for card in review_cards:
        pros=cons=comments=alternative_considered=reason_for_choosing=reason_for_switiching=switch_from=""
        date=review_source=source=review_name=review_role=country=review_title=used_software=employess=industry=""
        row=card.find("div",class_="row")
        main_two_divs=row.find_all("div",recursive=False)
        first_div=main_two_divs[0].find("div",class_="row").find_all("div",recursive=False)
        # print(first_div[1].text)
        # print(first_div[2].text)
        name=first_div[1].find("div",class_="h5").text.strip()
        divs=first_div[1].find_all("div",recursive=False)
        review_name_div=first_div[1].find("div",class_="h5",recursive=False)
        review_name=review_name_div.text.strip()
        for div in divs:
            # print(div.text)
            if "US" in div.text or "UK" in div.text or "Canada" in div.text or "Australia" in div.text or "Spain" in div.text:
                role_list=div.text.strip().split(" in ")                 
                if len(role_list)==2:
                    review_role=role_list[0]
                    country=role_list[1]
                else:
                    review_role=""
                    country=role_list[0]
        divs_bottoms=first_div[2].find_all("div",recursive=False)
        
        for div in divs_bottoms:
            if "Employe" in div.text:
                split_data=div.text.strip().split(", ")
                if len(split_data)==3:
                    industry=f"{split_data[0]},{split_data[1]}"
                    employess=split_data[2]
                elif len(split_data)==2:
                    industry,employess=split_data
                else:
                    industry=split_data[0]
                    employess=""
                # print(f"Industry: {industry}  while Employess:{employess}")
            elif "Used the Software for:" in div.text:
                used_software=div.text.strip().replace("Used the Software for:","")
                # print(used_software)
            elif "Source:" in div.text:
                source=div.text.strip().replace("Source:","")
                # print(f"Source Given:{source}")
            elif "Reviewer Source" in div.text:
                tool_item=div.find("sylar-tooltip")
                review_source=tool_item.get("data-bs-title")
                # print(f"Review Source::{review_source}")
        # second_div=main_two_divs[1].find("div",recursive=False)
        h3_review_title=main_two_divs[1].find("h3",class_="h5",recursive=False)
        # second_div=h3_review_title.find_next_sibling()
        if h3_review_title:
            review_title=h3_review_title.text.strip()
            second_div=h3_review_title.find_next_sibling()
            # print(f"Review Title: {review_title}")
        # print(second_div)
            span=second_div.find("span",class_="mos-star-rating")
            # print(f"Individual Rating is {span.text.strip()}")
            span.decompose()
            second_span=second_div.find("span")
            date=date_parser(second_span.text.strip())
        # print(f"Date is {second_span.text.strip()}")
        second_div_p=main_two_divs[1].find_all("p",recursive=False)
        for p in second_div_p:
            svg=p.find("svg")
            bold_span=p.find("span",class_="fw-bold")
            if svg:
                if "Pros:" in p.text:
                    pros_p=p.find_next_sibling()
                    pros=pros_p.text.strip()
                elif "Cons" in p.text:
                    cons_p=p.find_next_sibling()
                    cons=cons_p.text.strip()
            if bold_span:
                if "Comments:" in bold_span.text:
                    bold_span.decompose()
                    comments=p.text.strip()
                elif "Alternatives Considered:" in bold_span.text:
                    bold_span.decompose()
                    alternative_considered=p.text.strip()
                elif "Reasons for Switching to" in bold_span.text:
                    bold_span.decompose()
                    reason_for_switiching=p.text.strip()
                elif "Switched From:" in bold_span.text:
                    bold_span.decompose()
                    switch_from=p.text.strip()
                elif "Reasons for Choosing" in bold_span.text:
                    bold_span.decompose()
                    reason_for_choosing=p.text.strip()
        # print(f"Pros: {pros} \n  Cons:{cons}")
        obj={
            "URL":url,
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
        # print(obj)
        main_list.append(obj)
def clean_string(value):
    if isinstance(value, str):
        # Remove characters that are not allowed in Excel cells
        return re.sub(r'[\x00-\x1F]+', '', value)  # Removing control characters
    return value

def parse_all_pages(main_list,review_table):
    main_list=[]
    urls_to_scrape = review_table.find()
    for record in urls_to_scrape:
        url=record["url"]
        index=record["id"]
        print(f"{index}-Processing Urls is {url} ")
        html_content=record["html_content"]
        if "https://www.capterra.co.uk/reviews" in url:
            # pass
            parse_review_1st(html_content,url,main_list)
        else:
            parse_review_2nd(html_content,url,main_list)
def table_to_excel(table, file_name):
    # Fetch all rows from the table
    rows = list(table.all())

    # If there are no rows, return without creating a file
    if not rows:
        print("No data in the table to export.")
        return

    # Convert rows to a pandas DataFrame
    df = pd.DataFrame(rows)
    df = df.applymap(clean_string)
    # Export DataFrame to Excel file
    df.to_excel(file_name, index=False)
    print(f"Data exported to {file_name}")
    # print(len(url_list))

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
db = dataset.connect('sqlite:///webpages_uk.db')

# Table to store the URLs and HTML content
table = db['pages']
review_table = db['review']
final_data=db["finaldata"]
# Step 1: Scrape the URLs and store them in the database
store_urls()
# Step 2: Scrape the stored URLs from the database and store all review pages URL in new Database
scrap_review_pages_url()
# Step 3: Scrap the review pages and store html content of review pages in database
store_html_content()

#Step # 4
#Get html content from database and Parse Html content for Review pages
main_list=[]
parse_all_pages(main_list,review_table)
final_data.insert_many(main_list)
    # Step 5 : Now create Excel file from final_data table
table_to_excel(final_data,"Final_Data_UK.xlsx")
