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
states_with_cities = {
    "Bayern": [
        "Augsburg", "Bamberg", "Bayreuth", "Erlangen", "Fürth", 
        "Ingolstadt", "München", "Nürnberg", "Regensburg", "Würzburg"
    ],
    "Baden-Württemberg": [
        "Freiburg-im-Breisgau", "Heidelberg", "Heilbronn", "Karlsruhe", 
        "Ludwigsburg", "Mannheim", "Pforzheim", "Reutlingen", 
        "Stuttgart", "Ulm"
    ],
    "Berlin": [],  # No cities listed for Berlin
    "Brandenburg": [
        "Brandenburg-an-der-Havel", "Cottbus", "Eberswalde", "Falkensee", 
        "Frankfurt-Oder", "Oranienburg", "Potsdam"
    ],
    "Bremen": [
        "Bremen", "Bremerhaven"
    ],
    "Hamburg": [],  # No additional cities listed for Hamburg
    "Hessen": [
        "Darmstadt", "Frankfurt-am-Main", "Pour", "Hanau", 
        "Kassel", "Marburg", "Offenbach-am-Main", "Wiesbaden"
    ],
    "Mecklenburg-Vorpommern": [
        "Greifswald", "Güstrow", "Neubrandenburg", "Rostock", 
        "Schwerin", "Stralsund", "Wismar"
    ],
    "Niedersachsen": [
        "Brunswick", "Delmenhorst", "Goettingen", "Hanover", 
        "Hildesheim", "Oldenburg", "Osnabruck", "Salzgitter", 
        "Wolfsburg"
    ],
    "Nordrhein-Westfalen": [
        "Aachen", "Bielefeld", "Bochum", "Bonn", "Dortmund", 
        "Duisburg", "Dusseldorf", "Essen", "Gelsenkirchen", 
        "Hagen", "Hamm", "Cologne", "Krefeld", "Leverkusen", 
        "Moenchengladbach", "Mülheim-an-der-Ruhr", "Muenster", 
        "Oberhausen", "Wuppertal"
    ],
    "Rheinland-Pfalz": [
        "Kaiserslautern", "Koblenz", "Ludwigshafen am Rhein", 
        "Mainz", "Neustadt-an-der-Weinstraße", "Neuwied", 
        "Trier", "Worms"
    ],
    "Saarland": [
        "Homburg", "Neunkirchen", "Saarbrucken", "St. Ingbert", 
        "Voelklingen"
    ],
    "Sachsen": [
        "Chemnitz", "Dresden", "Goerlitz", "Leipzig", 
        "Plauen", "Zwickau"
    ],
    "Sachsen-Anhalt": [
        "Bitterfeld-Wolfen", "Dessau-Roßlau", "Halberstadt", 
        "Halle-Saale", "Magdeburg", "Wittenberg, Lutherstadt"
    ],
    "Schleswig-Holstein": [
        "Elmshorn", "Flensburg", "Kiel", "Lübeck", 
        "Neumünster", "Norderstedt", "Pinneberg"
    ],
    "Thüringen": [     
        "Eisenach", "Erfurt", "Gera", "Gotha", 
        "Jena", "Nordhausen", "Weimar"
    ]
}
#https://instahelp.me/de/psychologen/de/alle/?op=12
mainlist=[]
for state, cities in states_with_cities.items():
    print(f"State: {state}")
    if len(cities)==0:
        Url=f"https://instahelp.me/de/psychologen/at/alle/{state}/?op"
        makeIteration(Url,mainlist)
        # pass
    else:
        for city in cities:
            print(f"  City: {city}")
            Url=f"https://instahelp.me/de/psychologen/at/alle/{state}/{city}/?op"
            makeIteration(Url,mainlist)
            # break
    # break
df=pd.DataFrame(mainlist)

df.to_csv("InstaData3.csv",index=False)