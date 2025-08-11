import requests
import json
from bs4 import BeautifulSoup
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from alive_progress import alive_bar
import threading
import dataset
import time
import requests
import gzip
from lxml import etree  # lxml for better XPath and namespace handling
from io import BytesIO
lock = threading.Lock()
import traceback
def retrivePages(url,id):
    # url="https://www.local.ch/de/d/basel/4051/restaurant/indisches-restaurant-bajwa-palace-RssWWtrY8Z_NP4QaCkVSsw"
    url="https://www.local.ch/de/d/wetzikon-zh/8620/holzbau/freuler-holzbau-Itd-FbLS5PhgSkWz3o2zlQ"
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "max-age=0",
        "Cookie": 'NEXT_LOCALE=de; rid=5cbc19; sessionid=qFRm19GrwgyiIazm0ReWQyvE650YlyLtEvUANRRV; __Host-authjs.csrf-token=954f8af7ddd8fcd69d5899b9928a80c7ceb5e25a9e42965fefd89aacbf337955%7Cfc0854d94960e7e301f143ae298ae2de1705a2a6836eb0ff187a2fc57ef9ba0b; localch_debug=%7B%22mmkpi%22%3Afalse%2C%22search%22%3Afalse%7D; adblock-enabled=false; deviceid=alp4pvvdq61jpqjcigwp7ko3nnsgqsq4rhlyr97j; __Secure-authjs.callback-url=https%3A%2F%2Fwww.local.ch%2Fde%2Fd%2Fwetzikon-zh%2F8620%2Fholzbau%2Ffreuler-holzbau-gmbh-Itd-FbLS5PhgSkWz3o2zlQ; __Secure-authjs.session-token=eyJhbGciOiJkaXIiLCJlbmMiOiJBMjU2Q0JDLUhTNTEyIiwia2lkIjoiMU1nVnFvT0tEekwzUTJ6RHV4QVA5TGN3bTlOejNWbXlZX1dGblBjQVFQNFgtWGR5MnJsb3BKRnZsX3FraERoTVlJOXpJWjVyQ0lvc2ZPamd6RXVTalEifQ..GdWj7yFdT_ET44kfGmPcqA.P3ZHM8pt3OMkOzYbG7ROiC8wPM8nwEHBATNpxqNSEF6aZQUUIw9_OHbzeGsqpvP3YFAVOi2DVnZPE9i9kD1sDoi_12iBO3dOZ2WCl8jYKKUgh6XJGQKDexLzDSw_YFpdcz_Yyf7nchJeLTGgLFVjBXvhtr6GDbqxcMmE-DF-_1exTjaHjtaYjOEmH40A6cNDufkBKdKyiXYSE7otLd62gk_i-dV7DafMHE-MgDQMDgn84QhHqBImxg1VJ08rKVyq42gvPxuyfp9viEWgseGTYdjG5UI8wqVnyva-IkaFd-X4gMyagIMJKTSCMPbK3r_yPq9g8epr3GS61scD0yDEiMD2JMbnwBYIz2vn07uEbIV9iphZADgYH7aTI3Uxhy7UwgfasqxfVx9Ivk0tIMcNCYhTnLM67ycUhrcgIiHM-An05tHCDKrEXUmkhs5E7XV3ZduvKg7pG5BV2VVsdaCrr5DbsBB0YGZX3iGiny9aSvHhGF7R2RCHy2a3UkN4XwedEE4PW317qtO9GkBWpc_Co3NbaWwq5vdLu9pG0NQQ6TV4CVOMEgHM5A9iP_RAXfWZUcWzQyNipC-d2PQ1yQHsU5Ov8jXgvuRp0-TywBY8tJvvpJ-ZZZfvp87RatCzRjxy_jTeI8KbQCKpRIeKk13qqB-MsSEY_UmiU2bQOCl7kdtvPd9Ofu4eUTwYPVkfR3NP2br8z5sxZJNcSUh0ZVlUpksf5V3fAqaOpEuPSFdAJODRMRbzh4pH58QeuLWok6Ut0jQNZJj_ezkMTxcW3XRwLPtZVZFMONbu7PwD5TOBzMM.6EpnUJ4o1v-6qu0tCt-EN0Mxd0IVWZ2I21n08rlGxps; OptanonAlertBoxClosed=2025-07-25T10:53:31.029Z; eupubconsent-v2=CQVGRrgQVGRrgAcABBDEB0FgAAAAAAAAAAQ4AAAWrgGAA4AM-A7YCiwFHAKpAVZArABXMCvoFigLVgAA.YAAAAAAAAAAA; OptanonConsent=isGpcEnabled=0&datestamp=Fri+Jul+25+2025+15%3A53%3A31+GMT%2B0500+(Pakistan+Standard+Time)&version=202504.1.0&browserGpcFlag=0&isIABGlobal=false&hosts=&consentId=1f655b10-da98-4154-a07e-553f56f681f2&interactionCount=1&isAnonUser=1&landingPath=NotLandingPage&groups=C0002%3A0%2CC0001%3A1%2CC0003%3A0%2CC0004%3A0%2CV2STACK42%3A0&intType=2',
        "Priority": "u=0, i",
        "Sec-CH-UA": '"Chromium";v="128", "Not;A=Brand";v="24", "Google Chrome";v="128"',
        "Sec-CH-UA-Mobile": "?0",
        "Sec-CH-UA-Platform": '"Windows"',
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    }
    try:
        response = requests.get(url,headers=headers)
        # print(response.status_code)
        if response.status_code==200:
            try:
                name=address="Not Found"
                soup=BeautifulSoup(response.content,"html.parser")
                name=soup.find("h1",class_="kW").text
                main_div=soup.find("div",class_="nE")
                address=main_div.find("div",class_="pT").text
                li_items=main_div.find_all("li",class_="si")
                email=website=""
                Telefon=[]
                Mobiltelefon=[]
                WhatsApp=[]
                for li in li_items:
                    label=li.find("span",class_="sq",recursive=False)
                    if label:
                        if label.text=="Telefon":
                            all_a=li.find_all("a")
                            for a in all_a:
                                if "tel:" in a.get("href"):
                                    number=a.get("href").replace("tel:","")
                                    Telefon.append(f"'{number}")
                        elif label.text=="Mobiltelefon":
                            all_a=li.find_all("a")
                            for a in all_a:
                                if "tel:" in a.get("href"):
                                    number=a.get("href").replace("tel:","")
                                    Mobiltelefon.append(f"'{number}")
                            # Mobiltelefon=li.text.replace("Mobiltelefon","")
                        elif label.text=="WhatsApp":
                            # print("Not Coming")
                            all_a=li.find_all("a")
                            for a in all_a:
                                # if "tel:" in a.get("href"):
                                number=a.get("href").replace("https://wa.me/","")
                                WhatsApp.append(f"'{number}")
                        elif label.text=="Email":
                            email=li.text.replace("Email","")
                        elif label.text=="Website":
                            website=li.text.replace("Website","")
                # print("Name is ::",name)            
                # print("Addresss is ::",address)
                # print("Email is ::",email)
                # print("Webite Is ::",website)
                # print(name,email,website)
                print("Reached at Id No is::",id)
                obj={
                    "Url":url,
                    "Name":name,
                    "Address": address,
                    "Email":email,
                    "Website":website,
                    "Telefon 1":Telefon[0] if len(Telefon) > 0 else "",
                    "Telefon 2":Telefon[1] if len(Telefon) > 1 else "",
                    "Mobiltelefon 1":Mobiltelefon[0] if len(Mobiltelefon) > 0 else "",
                    "Mobiltelefon 2":Mobiltelefon[1] if len(Mobiltelefon) > 1 else "",
                    "WhatsApp 1": WhatsApp[0] if len(WhatsApp) > 0 else "",
                    "WhatsApp 2": WhatsApp[1] if len(WhatsApp) > 1 else "",
                }
                print(obj)
                return obj
            except Exception as e:
                print(f"Exception has been occur as : {e}")
                # traceback.print_exc()
                return url
            
        else:
            print(f"Request have been failed with code :{response.status_code}")
            return url
    except Exception as e:
        # traceback.print_exc()
        print(f"Exception has been occur as : {e}")
        return url
    
retrivePages("",2)