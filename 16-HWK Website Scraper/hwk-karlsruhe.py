import requests
from bs4 import BeautifulSoup
import string
import vobject
import pandas as pd
# Base URL to scrape
base_url = "https://www.hwk-karlsruhe.de/kontakte/liste-63,88,dalist.html?curChar="
main_url = "https://www.hwk-karlsruhe.de"
csv_name="hwk-karlsruhe.xlsx"
main_list=[]

# Base URL to scrape
def download_and_parse_vcf(vcf_url):
    # Step 1: Make a request to the VCF link
    response = requests.get(vcf_url)

    # Check if the request was successful
    if response.status_code == 200:
        # Step 2: Parse the vCard content using vobject
        vcard_content = response.text
        
        try:
            vcard = vobject.readOne(vcard_content)
            
            # Extract Name
            name = vcard.fn.value if hasattr(vcard, 'fn') else ''
            
            # Extract Email
            email = vcard.email.value if hasattr(vcard, 'email') else ''
            
            # Extract Phone Number
            phone_list = []

            # If the vCard contains phone numbers
            if hasattr(vcard, 'tel_list'):
                for tel in vcard.tel_list:
                    phone_list.append(tel.value.strip())  # Collect each phone number

            # Join phone numbers with " & " if there are multiple
            phone = " & ".join(phone_list) if phone_list else ''
                        
            # Extract Position (usually in Title or Role)
            position = vcard.title.value if hasattr(vcard, 'title') else ''
            
            return {
                'Name': name,
                'Email': email,
                'Phone': phone,
                'Position': position
            }
        except Exception as e:
            return f"Error parsing vCard: {e}"

    else:
        return f"Failed to download vCard. Status Code: {response.status_code}"

# Iterate over A to Z
for char in string.ascii_uppercase:
    # Construct the full URL for the current character
    url = base_url + char
    
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
                full_link = f"{main_url}{href}"
                response2 = requests.get(full_link)
                position2=""
                obj2={}
                if response2.status_code == 200:
                    soup2 = BeautifulSoup(response2.content, 'html.parser')
                    all_a=soup2.find_all("a")
                    for a in all_a:
                        if a.get("href") and ".vcf" in a.get("href"):
                            vcf_link=a.get("href")
                            obj2=download_and_parse_vcf(f"{main_url}{vcf_link}")
                else:
                    print(f"Failed to retrieve detail page for {full_link} - Status Code: {response2.status_code}")
                obj1={
                    "Website":main_url,
                    "User Profile Link": full_link,
                }
                merge_dict={**obj1,**obj2}
                print(merge_dict)
                main_list.append(merge_dict)
                print("Done")
        else:
            print(f"No results found for \n")
    
    else:
        print(f"Failed to retrieve page for '{char}' - Status Code: {response.status_code}")



df=pd.DataFrame(main_list)

df.to_excel(csv_name,index=False)