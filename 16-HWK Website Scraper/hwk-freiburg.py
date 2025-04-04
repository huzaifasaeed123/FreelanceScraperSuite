import requests
from bs4 import BeautifulSoup
import pandas as pd
import vobject
import time
# Base URL to scrape
base_url = "https://www.hwk-freiburg.de/de/uber-uns/ansprechpartner/ansprechpartner-nach-name?"
main_url = "https://www.hwk-freiburg.de"
csv_name="hwk-freiburg.xlsx"
main_list=[]
for i in range(1,4):

    # Construct the full URL for the current character
    # url = base_url
    url=f"{base_url}page={i}"
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
                # print(full_link)
                response2 = requests.get(full_link)
                name=email=phone=position=""
                obj2={}
                if response2.status_code == 200:
                    soup2 = BeautifulSoup(response2.content, 'html.parser')
                    name_span=soup2.find('span',itemprop="name")
                    name=name_span.text.strip()
                    tel_td=soup2.find("td",itemprop="telephone")
                    if tel_td:
                        phone=tel_td.text.strip()
                    email_td=soup2.find("a",itemprop="email")
                    # print(email_td)
                    if email_td:
                        email=email_td.text.strip()
                    all_td=soup2.find_all("td")
                    for index,td in enumerate(all_td):
                        if "Funktion" in td.text:
                            position_td=td.find_next_sibling()
                            position=position_td.text.strip()
                            # print(f"{index}-{td.text}")
                    # print(name,phone,email,position)
                    # break
                    # all_a=soup2.find_all("a")
                    # p=soup2.find("p",class_="uni-kontakt")
                    # # p.find("label")
                    # # print(p.text)
                    # label_tag = p.find('label',recursive=False)
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
                    # # Output the result
                    # # break
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
                    'Name': name,
                    'Email': email,
                    'Phone': phone,
                    "Position": position
                }
                # merge_dict={**obj1,**obj2}
                # print(merge_dict)
                main_list.append(obj1)
                print("Done")
        else:
            print(f"No results found for \n")

    else:
        print(f"Failed to retrieve page for  - Status Code: {response.status_code}")

# break  # Remove this break if you want to iterate over all letters


df=pd.DataFrame(main_list)

df.to_excel(csv_name,index=False)