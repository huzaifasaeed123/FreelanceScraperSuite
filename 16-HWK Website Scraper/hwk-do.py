import requests
from bs4 import BeautifulSoup
import pandas as pd
import vobject
import time
# Base URL to scrape
base_url = "https://www.hwk-do.de/ansprechpartner-2/"
main_url = "https://www.hwk-do.de/"
csv_name="hwk-do.xlsx"
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
    div_tags = soup.find_all("div", class_="contact-person-single")
    
    # If we found any matching <a> tags
    if div_tags:
        # Loop through and print the href and text of each <a> tag
        for div in div_tags:
            # try:
                name=div.find("span",class_="name",recursive=False).text.strip()
                email=div.find("span",class_="email",recursive=False).text.strip()
                phone=div.find("span",class_="phone",recursive=False).text.strip()
                userprofileLink=f"{main_url}./?p={email}"
                obj1={
                    "Website":main_url,
                    "User Profile Link": userprofileLink,
                    "Name": name,
                    "Position": "",
                    "Phone": phone,
                    "Email": email,
                }
                
                print(obj1)
                main_list.append(obj1)
                print("Done")
            # except Exception as e:
            #     print(e)
    else:
        print(f"No results found for \n")

else:
    print(f"Failed to retrieve page for  - Status Code: {response.status_code}")

# break  # Remove this break if you want to iterate over all letters


df=pd.DataFrame(main_list)

df.to_excel(csv_name,index=False)