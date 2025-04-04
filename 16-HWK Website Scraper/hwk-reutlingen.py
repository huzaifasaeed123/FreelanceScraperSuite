import requests
from bs4 import BeautifulSoup
import pandas as pd
import vobject
import time
import re
# Base URL to scrape
base_url = "https://www.hwk-reutlingen.de/top-menue/kontakt/ansprechpartner.html"
main_url = "https://www.hwk-reutlingen.de/"
csv_name="hwk-reutlingen.xlsx"
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
    div_tags = soup.find_all("div", class_="list-group-item")
    
    # If we found any matching <a> tags
    if div_tags:
        # Loop through and print the href and text of each <a> tag
        for div in div_tags:
            name=email=phone=position=""
            all_p=div.find_all("p")
            name=all_p[0].text.strip()
            phone=all_p[1].text.strip()
            email=all_p[2].text.replace("[at]","@").strip()
            more_info=div.find("div",class_="more_info")
            main_div=more_info.find("div",recursive=False)
            # main_div.find("a").decompose()
            split_content = [str(text).strip() for text in main_div.stripped_strings]
            # Initialize an empty list to hold strings without numbers
            no_integer_list = []
            concatenated_string=""
            # Iterate over the split content
            for item in split_content:
                # Check if the string does not contain an integer
                if not re.search(r'\d', item) and "[at]" not in item:
                    no_integer_list.append(item)

            # Concatenate the items without integers using '&'
            concatenated_string = ' & '.join(no_integer_list)
            position=concatenated_string
            print(split_content)
            # break
            obj1={
                "Website":main_url,
                "User Profile Link": "",
                "Name": name,
                "Phone": phone,
                "Email": email,
                "Position": position
            }
            # merge_dict={**obj1,**obj2}
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