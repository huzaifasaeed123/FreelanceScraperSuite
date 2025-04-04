import requests
from bs4 import BeautifulSoup
import time
import dataset
import dateparser
def date_parser(date_str):
    parsed_date = dateparser.parse(date_str)
    
    # Extract only the date (if parsed_date is not None)
    if parsed_date:
        return parsed_date.date()
    else:
        return date_str

def parse_review(url):
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
    url="https://www.capterra.co.uk/reviews/154907/square-point-of-sale"
    url="https://www.capterra.co.uk/software/79892/cardwatch-pos"
    # Send the GET request
    response = requests.get(url,headers=headers)
    # jhj gh hg ghhj hgg yyu po rt wewqtds sdagh gkjkjklj';/nm,n bvbncvcvx xzxcsadew
    # Check if the request was successful
    if response.status_code == 200:        
        # Parse the response content
        soup = BeautifulSoup(response.content, 'html.parser')
        # with open("output.html", "w", encoding="utf-8") as file:
        #     file.write(response.text)
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
                    print(f"Role: {role_list[0]}  Country: {role_list[1]}")
                    review_role=role_list[0]
                    country=role_list[1]
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
                    print(f"Industry: {industry}  while Employess:{employess}")
                elif "Used the Software for:" in div.text:
                    used_software=div.text.strip().replace("Used the Software for:","")
                    print(used_software)
                elif "Source:" in div.text:
                    source=div.text.strip().replace("Source:","")
                    print(f"Source Given:{source}")
                elif "Reviewer Source" in div.text:
                    tool_item=div.find("sylar-tooltip")
                    review_source=tool_item.get("data-bs-title")
                    print(f"Review Source::{review_source}")
            # second_div=main_two_divs[1].find("div",recursive=False)
            h3_review_title=main_two_divs[1].find("h3",class_="h5",recursive=False)
            # second_div=h3_review_title.find_next_sibling()
            if h3_review_title:
                review_title=h3_review_title.text.strip()
                second_div=h3_review_title.find_next_sibling()
                print(f"Review Title: {review_title}")
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
            print(obj)
            # break
            # pass
        # all_cards=soup.find_all("div",class_="product-card")
        # print(len(all_cards))    
        # for card in all_cards:
        #     a=card.find("a",class_="mos-star-rating")
            # print(a.get("href"))
            
            # break
        # print(len(url_list))
    else:
        print(f"Failed to retrieve the page. Status code: {response.status_code}")


parse_review("")