import requests
from bs4 import BeautifulSoup
import string
import pandas as pd
# Base URL to scrape
base_url = "https://www.hwk-muenster.de/de/service-center/ansprechpartnerinnen"
main_url = "https://www.hwk-muenster.de"
csv_name="hwk-muenster.xlsx"
main_list=[]
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
        print(f"Results for :")
        # Loop through and print the href and text of each <a> tag
        for a_tag in a_tags:
            href = a_tag.get('href')
            full_link = f"{main_url}{href}"
            all_p=a_tag.find_all("p")
            name=all_p[0].text
            phone=all_p[1].text
            email=all_p[2].text
            position=""
            
            # Request the individual page for each contact
            # response2 = requests.get(full_link)
            # position2=""
            # if response2.status_code == 200:
            #     soup2 = BeautifulSoup(response2.content, 'html.parser')

            #     # Find all the <address> elements
            #     address_elements = soup2.find('address')
            
            #     # Iterate through all <address> elements
            
            #     previous_sibling = address_elements.find_previous_sibling('p')
                
            #     # Check if a <p> tag exists before <address>
            #     if previous_sibling and previous_sibling.name == 'p':
            #         position2=previous_sibling.text       
            #     else:
            #         print("No <p> element found before <address>.")
            # else:
            #     print(f"Failed to retrieve detail page for {full_link} - Status Code: {response2.status_code}")
            main_list.append({
                "Website":main_url,
                "User Profile Link": full_link,
                "Name": name,
                "Phone": phone,
                "Email": email,
                "Position": position,
            })
    else:
        print(f"No results found for '\n")

else:
    print(f"Failed to retrieve page for  - Status Code: {response.status_code}")

# break  # Remove this break if you want to iterate over all letters


df=pd.DataFrame(main_list)

df.to_excel(csv_name,index=False)