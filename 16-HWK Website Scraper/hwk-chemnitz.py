import requests
from bs4 import BeautifulSoup
import pandas as pd
import vobject
import time
# Base URL to scrape
base_url = "https://www.hwk-chemnitz.de/kontakt/ansprechpartner/?mode=ansprechpartner"
main_url = "https://www.hwk-chemnitz.de/"
csv_name="hwk-chemnitz.xlsx"
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
    li_tags = soup.find_all("li", class_="row search-results-toggle")
    
    # If we found any matching <a> tags
    if li_tags:
        # Loop through and print the href and text of each <a> tag
        for li in li_tags:
            try:
                all_divs=li.find_all("div",recursive=False)
                phone=all_divs[1].text.strip()
                email=all_divs[2].text.strip()
                print(phone,email)
                main_div=str(all_divs[0])
                split_content=main_div.split("<br/>")
                print(split_content)
                soup3=BeautifulSoup(split_content[0],"html.parser")
                name=soup3.text
                soup4=BeautifulSoup(split_content[1],"html.parser")
                position2=soup4.text
                
                obj1={
                    "Website":main_url,
                    "User Profile Link": "",
                    "Name": name,
                    "Position": position2,
                    "Phone": phone,
                    "Email": email,
                }
                
                print(obj1)
                main_list.append(obj1)
                print("Done")
            except Exception as e:
                print(e)
    else:
        print(f"No results found for \n")

else:
    print(f"Failed to retrieve page for  - Status Code: {response.status_code}")

# break  # Remove this break if you want to iterate over all letters


df=pd.DataFrame(main_list)

df.to_excel(csv_name,index=False)