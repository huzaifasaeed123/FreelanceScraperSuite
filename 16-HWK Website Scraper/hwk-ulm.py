import requests
from bs4 import BeautifulSoup
import pandas as pd
import vobject
import time
# Base URL to scrape
base_url = "https://www.hwk-ulm.de/ansprechpartner/"
main_url = "https://www.hwk-ulm.de/"
csv_name="hwk-ulm.xlsx"
main_list=[]
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
            # Extract Phone Number
            phone_list = []

            # If the vCard contains phone numbers
            if hasattr(vcard, 'tel_list'):
                for tel in vcard.tel_list:
                    phone_list.append(tel.value.strip())  # Collect each phone number
            # print(phone_list)
            # # Join phone numbers with " & " only if there are multiple phone numbers
            # if len(phone_list) > 1:
            #     phone = " & ".join(phone_list)
            if phone_list:
                phone = phone_list[0]  # If there's only one number, just use that
            else:
                phone = ''  # If no phone numbers, return an empty string
            # print(phone)            
            # Extract Position (usually in Title or Role)
            position = vcard.title.value if hasattr(vcard, 'title') else ''
            
            # Extract Position (usually in Title or Role)
            position = vcard.title.value if hasattr(vcard, 'title') else ''
            
            return {
                'Name': name,
                'Email': email,
                'Phone': phone,
                # 'Position': position
            }
        except Exception as e:
            return f"Error parsing vCard: {e}"

    else:
        return f"Failed to download vCard. Status Code: {response.status_code}"



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
            all_p=a_tag.find_all("p")
            name=all_p[0].text
            phone=all_p[1].text
            email=all_p[2].text.replace("--at--","@")
            # print(full_link)
            response2 = requests.get(full_link)
            position=""
            obj2={}
            if response2.status_code == 200:
                soup2 = BeautifulSoup(response2.content, 'html.parser')
                all_a=soup2.find_all("a")
                p=soup2.find("p",class_="uni-kontakt")
                # p.find("label")
                # print(p.text)
                label_tag = p.find('label',recursive=False)
                if label_tag:
                    position=label_tag.text
                # label_tag.decompose()
                # span_tag = p.find('span',recursive=False)
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
                # Output the result
                # break
                # for a in all_a:
                #     if a.get("href") and "vcf" in a.get("href"):
                        
                #         vcf_link=a.get("href")
                #         # print(vcf_link)
                #         time.sleep(2)
                #         obj2=download_and_parse_vcf(f"{vcf_link}")
                #         # print(obj2)
            else:
                print(f"Failed to retrieve detail page for {full_link} - Status Code: {response2.status_code}")
            obj1={
                "Website":main_url,
                "User Profile Link": full_link,
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