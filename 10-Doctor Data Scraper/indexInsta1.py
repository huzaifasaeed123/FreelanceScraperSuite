from bs4 import BeautifulSoup
import requests
import re
import pandas as pd
import traceback
def makeIteration(url,mainList):
    for i in range(1,15):
        response=requests.get(f"{url}={i}")
        if response.status_code==200:
            soup=BeautifulSoup(response.content,'html.parser')
            divs=soup.find_all('div',class_="psy-verzeichnis-entry offline-psychologe")
            for div in divs:
                try:
                    h2=div.find('h2')
                    a=h2.find('a',recursive=False)
                    href=a.get('href')
                    print(f"Name::{h2.text} Link::{href}")
                    response2=requests.get(href)
                    if response2.status_code==200:
                        soup2=BeautifulSoup(response2.content,'html.parser')
                        profileDiv=soup2.find('div',class_="psy-profile-desc")
                        ContactDiv=soup2.find('div',class_="psy-profile-contact")
                        # print(ContactDiv)
                        if profileDiv:
                            table=ContactDiv.find("table")
                            Name=profileDiv.select_one("h1").text
                            profession=profileDiv.select_one("h2").text
                            print(Name,profession)
                            # print(table)
                            trs=table.find_all('tr',recursive=False)
                            email=website=address=phone=Languages=""
                            for tr in trs:
                                # print(tr)
                                td=tr.find('td').text
                                # print(td)
                                if td=="E-Mail:":
                                    a=tr.find_all("td")[1].find('a')
                                    email=a.get("data-contact")
                                    print("Email::",email)
                                if td=="Website:":
                                    website=tr.find_all("td")[1].text
                                    print("Website::",website)
                                if td=="Adresse:":
                                    address=tr.find_all("td")[1].get_text()
                                    address = re.sub(r'\s+', ' ', address)
                                    print("Address::",address)
                                if td=="Telefon:":
                                    a=tr.find_all("td")[1].find("a")
                                    if a:
                                        phone=a.get("data-tel")
                                        print("Phone::",phone)
                                if td=="Sprachen:":
                                    tr.find("br").decompose()
                                    Languages=tr.find_all("td")[1].get_text(strip=True)
                                    print("Languages::",Languages.strip())
                                # print(email,website,address,phone,Languages)
                            mainList.append({
                                "Name": Name,
                                "Profession": profession,
                                "Email": email,
                                "Website": website,
                                "Address": address,
                                "Phone Number": phone,
                                "Language": Languages
                            })

                    else:
                        print("Internal Request failed With Status Code: ",response2.status_code)
                        # break
                except Exception as e:
                    print("Exception has been Occur",e)
                    traceback.print_stack()
            len(divs)
            # break
        else:
            print("Main Request Failed With status Code::",response.status_code)
states_with_cities = [
"https://instahelp.me/de/psychologen/de/alle/bayern/",
"https://instahelp.me/de/psychologen/de/alle/baden-wuerttemberg/",
"https://instahelp.me/de/psychologen/de/alle/berlin/",
"https://instahelp.me/de/psychologen/de/alle/brandenburg/"
"https://instahelp.me/de/psychologen/de/alle/bremen/",
"https://instahelp.me/de/psychologen/de/alle/hamburg/",
"https://instahelp.me/de/psychologen/de/alle/hessen/",
"https://instahelp.me/de/psychologen/de/alle/mecklenburg-vorpommern/",
"https://instahelp.me/de/psychologen/de/alle/niedersachsen/",
"https://instahelp.me/de/psychologen/de/alle/nordrhein-westfalen/",
"https://instahelp.me/de/psychologen/de/alle/rheinland-pfalz/",
"https://tinstahelp.me/de/psychologen/de/alle/saarland/",
"https://instahelp.me/de/psychologen/de/alle/sachsen/",
"https://instahelp.me/de/psychologen/de/alle/sachsen-anhalt/",
"https://instahelp.me/de/psychologen/de/alle/schleswig-holstein/",
"https://instahelp.me/de/psychologen/de/alle/thueringen/",
]
#https://instahelp.me/de/psychologen/de/alle/?op=12
mainlist=[]
for url in states_with_cities:
    # print(f"State: {state}")
    # Url=f"https://instahelp.me/de/psychologen/at/alle/{state}/?op"
    Url=f"{url}?op"
    parts = Url.split("de")

# Join the parts back, replacing the second occurrence of "de" with "at"
    new_url = "de".join(parts[:2]) + "at" + "de".join(parts[2:])
    print(new_url)
    makeIteration(new_url,mainlist)
        # pass
    # else:
    #     for city in cities:
    #         print(f"  City: {city}")
    #         Url=f"https://instahelp.me/de/psychologen/at/alle/{state}/{city}/?op"
    #         makeIteration(Url,mainlist)
    #         # break
    # break
df=pd.DataFrame(mainlist)

df.to_csv("InstaData3.csv",index=False)