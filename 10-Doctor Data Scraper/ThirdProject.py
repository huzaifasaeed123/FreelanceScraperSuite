import requests
from bs4 import BeautifulSoup
import pandas as pd

proxy = {
     "http": "http://saeedhuzaifa678_gmail_com-dc:Saeed123@la.residential.rayobyte.com:8000",
    "https": "http://saeedhuzaifa678_gmail_com-dc:Saeed123@la.residential.rayobyte.com:8000"

   }
MainData=[]
for i in range(121, 4801, 15):
    try:
        print("Main Data Iteration::",i)
        url=f"https://www.psychologen.at/go.asp?ZS=&ss=ergebnis&sektion=personen&aktion=view&suchformular_id=9&bereich_id=9003&berufsgruppe=psy&geschlecht=A&order_by=crabc&order_by_marker=Q&DS={i}"
        response=requests.get(url)
        
        soup=BeautifulSoup(response.content,"html.parser")
        
        class1=soup.find("div",class_="box_simple")
        divs_with_style = class1.find_all('div', style=lambda value: value and 'border-style:solid' in value,recursive=False)
        print(len(divs_with_style))
        # Print the result
        for div in divs_with_style:
            try:
                name=profession=address=phone=EmailLink=anchor=""
                internalDivs=div.find("div",class_="column black1")
                anchor_elements=internalDivs.find_all('a')
                for anchors in anchor_elements:
                    href_value = anchors.get('href')
                    if href_value and href_value.startswith('tel:'):
                        phone=href_value
                        phone = href_value.replace("tel:", "")
                    if href_value and "emailcontactform" in href_value:
                        EmailLink=href_value
                addressDiv=internalDivs.find("div",class_="black1")
                spanIn=addressDiv.find_all("span")
                for span in spanIn:
                    span.decompose()
                address=addressDiv.text.strip()
                name=internalDivs.find("h2").text.split(",")[0]
                spans=internalDivs.find_all("span",class_="darkgrey1")
                for span in spans:
                    parent = span.find_parent('a')  # Get the direct parent 'a' tag
                    if parent and not parent.has_attr('target'):
                        profession = span.text.strip()
                # session=requests.Session()
                # session.proxies.update(proxy)
                # print(f"Name::{name}    Profession::{profession}   Address::{address}   Phone:: {phone}  EmailLink::{EmailLink} Email::{anchor}")
                if EmailLink != "":
                    response2=requests.get(EmailLink,proxies=proxy)
                    soup2=BeautifulSoup(response2.content,"html.parser")
                    anchor=soup2.find("a").text
                # soup2.text
                MainData.append({
                    "Name": name,
                    "Profession": profession,
                    "Address": address,
                    "Phone": phone,
                    "EmailLink":EmailLink,
                    "Email": anchor
                })
                print(f"Name::{name}    Profession::{profession}   Address::{address}   Phone:: {phone}  EmailLink::{EmailLink} Email::{anchor}")
                # for InDiv in internalDivs:
                # break    
                # print(div)
            except Exception as e:
                print("Internal Exception has been Occur",e)
    except Exception as e:
        print("External Exception has been Occur",e)
# print(class1)
# soup.text

df = pd.DataFrame(MainData)

# Write DataFrame to CSV
df.to_csv('output2.csv', index=False)