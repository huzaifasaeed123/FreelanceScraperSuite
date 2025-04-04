import requests
from bs4 import BeautifulSoup
import pandas as pd
import vobject
import time
import re
# Base URL to scrape
base_url = "https://www.hwkhalle.de/ansprechpartner/"
main_url = "https://www.hwkhalle.de/"
csv_name="hwkhalle.xlsx"
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
    a_tags = soup.find_all("a", class_="list-group-item")
    
    # If we found any matching <a> tags
    if a_tags:
        # Loop through and print the href and text of each <a> tag
        for a_tag in a_tags:
            href = a_tag.get('href')
            full_link = href
            # print(full_link)
            response2 = requests.get(full_link)
            position2=""
            obj2={}
            name=email=phone=""
            if response2.status_code == 200:
                soup2 = BeautifulSoup(response2.content, 'html.parser')
                name=soup2.find("h1").text
                all_a=soup2.find_all("a")
                p=soup2.find("p",class_="uni-kontakt")
                # p.find("label")
                # print(p.text)
                # label_tag = p.find('label',recursive=False)
                # label_tag.decompose()
                span_tag = p.find('span',style="font-size: 18px !important;",recursive=False)
                position2=span_tag.text.strip()
                email=p.find("a",recursive=False).text.strip()
                # Regular expression to capture phone numbers that follow the word "Telefon"
                pattern = r'Telefon\s+(\d[\d\s-]*)'

                # Find all matches in the text
                matches = re.findall(pattern, p.text)

                # Output the result
                phone=matches[0].strip()
                # br_tags=p.find_all("br",recursive=False)
                # for br in br_tags:
                #     br.decompose()
                # print(label_tag.text)
                # p_content_str = str(p)

                # # Split the content based on the <span> tag
                # split_content = p_content_str.split('<span')[0]

                # # Parse the split content back to HTML and extract the text
                # split_soup = BeautifulSoup(split_content, 'html.parser')

                # # Extract all the text
                # result_text = split_soup.get_text(separator=' ', strip=True)
                # position2=result_text.strip()
                # break
                # Output the result
                # break
                # for a in all_a:
                #     if a.get("href") and "vcf" in a.get("href"):
                        
                #         vcf_link=a.get("href")
                #         print(vcf_link)
                #         time.sleep(2)
                #         obj2=download_and_parse_vcf(vcf_link)
                #         print(obj2)
            else:
                print(f"Failed to retrieve detail page for {full_link} - Status Code: {response2.status_code}")
            obj1={
                "Website":main_url,
                "User Profile Link": full_link,
                "Position": position2,
                'Name': name,
                'Email': email,
                'Phone': phone,
            }
            
            print(obj1)
            main_list.append(obj1)
            print("Done")
    else:
        print(f"No results found for \n")

else:
    print(f"Failed to retrieve page for  - Status Code: {response.status_code}")

# break  # Remove this break if you want to iterate over all letters


df=pd.DataFrame(main_list)

df.to_excel(csv_name,index=False)