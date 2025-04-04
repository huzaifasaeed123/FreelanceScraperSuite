import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
# Base URL to scrape
def classify_span_content(span_text):
    span_text = span_text.strip()

    # Check if it's an email (contains '@')
    if "@" in span_text:
        return 'email', span_text.replace("E-Mail:","")

    # Check if it's a phone number (contains 'Tel:' followed by numbers)
    if span_text.startswith('Tel:'):
        phone_number = span_text.replace('Tel:', '').strip()
        if re.match(r'^\+?\d+', phone_number):  # Basic validation for phone number
            return 'phone', phone_number

    if re.match(r'^[a-zA-ZÀ-ÿ\s/.,-]+$', span_text):
        return 'position', span_text

    return 'unknown', span_text  # Return unknown if it doesn't match any category
def scrape_single_span_from_div(url):
    response = requests.get(url)

    if response.status_code == 200:
        soup = BeautifulSoup(response.content, "html.parser")
        
        # Find all <div> elements (you can modify this to narrow down to specific divs)
        Main_div = soup.find("div",id="c2051")
        div=Main_div.find("div",class_="row")
        h1=div.find("h1").text.replace("Ihr Ansprechpartner","").strip()
        div.find("h1").decompose()
        # Variables to store the first found values
        position = ""
        phone = ""
        email = ""

        # Loop over each <div> and find <span> elements inside
        
        spans = div.find_all("span")

        # Process each span element
        for span in spans:
            span_text = span.get_text()

            # Classify the span content
            classification, content = classify_span_content(span_text)

            # Assign the first found value for each category
            if classification == 'position' and position=="":
                position = content
            elif classification == 'phone' and phone=="":
                phone = content
            elif classification == 'email' and email=="":
                email = content

            # If all values are found, stop searching
            # if position and phone and email:
            #     break

    
        return {
            'Name':h1,
            'Email': email,
            'Phone': phone,
            'Position 2': position,
            
            
        }

    else:
        print(f"Failed to retrieve page - Status Code: {response.status_code}")
        return None
    
base_url = "https://www.hwk-dresden.de/kontakt/ansprechpartner.html"
main_url = "https://www.hwk-dresden.de"
csv_name="hwk-dresden.xlsx"
main_list=[]
# Iterate over A to Z

# Construct the full URL for the current character
url = base_url

# Send a GET request to the server
response = requests.get(url)

# Check if the request was successful
if response.status_code == 200:
    # Parse the page content with BeautifulSoup
    soup = BeautifulSoup(response.content, "html.parser")
    
    # Find all <a> elements with the class 'list-group-item'
    a_tags = soup.find_all("a", class_="inline",target="_blank")
    
    # If we found any matching <a> tags
    if a_tags:
        # Loop through and print the href and text of each <a> tag
        for a_tag in a_tags:
            obj2={}
            href = a_tag.get('href')
            full_link = f"{main_url}{href}"
            obj2=scrape_single_span_from_div(full_link)
            # response2 = requests.get(full_link)
            
            # if response2.status_code == 200:
            #     soup2 = BeautifulSoup(response2.content, 'html.parser')
            #     # all_a=soup2.find_all("a")
            #     # for a in all_a:
            #     #     if a.get("href") and ".vcf" in a.get("href"):
            #     #         vcf_link=a.get("href")
            #     #         # obj2=download_and_parse_vcf(f"{main_url}{vcf_link}")
            # else:
            #     print(f"Failed to retrieve detail page for {full_link} - Status Code: {response2.status_code}")
            obj1={
                "Website":main_url,
                "User Profile Link": full_link,
                "Position 1": "",
            }
            merge_dict={**obj1,**obj2}
            print(merge_dict)
            main_list.append(merge_dict)
            print("Done")
    else:
        print(f"No results found for \n")

else:
    print(f"Failed to retrieve page for  - Status Code: {response.status_code}")

# break  # Remove this break if you want to iterate over all letters


df=pd.DataFrame(main_list)

df.to_excel(csv_name,index=False)