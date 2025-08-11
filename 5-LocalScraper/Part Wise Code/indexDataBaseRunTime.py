import requests
import json
from bs4 import BeautifulSoup
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from alive_progress import alive_bar
import threading
import dataset
import time
lock = threading.Lock()
import traceback
def retrivePages(url,id):
    # url="https://www.local.ch/de/d/basel/4051/restaurant/indisches-restaurant-bajwa-palace-RssWWtrY8Z_NP4QaCkVSsw"
    # url="https://www.local.ch/de/d/wetzikon-zh/8620/holzbau/freuler-holzbau-Itd-FbLS5PhgSkWz3o2zlQ"
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "max-age=0",
        "Cookie": 'NEXT_LOCALE=de; deviceid=alp4pvvdq61jpqjcigwp7ko3nnsgqsq4rhlyr97j; OptanonAlertBoxClosed=2025-07-25T10:53:31.029Z; eupubconsent-v2=CQVGRrgQVGRrgAcABBDEB0FgAAAAAAAAAAQ4AAAWrgGAA4AM-A7YCiwFHAKpAVZArABXMCvoFigLVgAA.YAAAAAAAAAAA; lang=de; ea_uuid=202507251314362028201910; OptanonConsent=isGpcEnabled=0&datestamp=Sun+Jul+27+2025+20%3A29%3A48+GMT%2B0500+(Pakistan+Standard+Time)&version=202504.1.0&browserGpcFlag=0&isIABGlobal=false&hosts=&consentId=1f655b10-da98-4154-a07e-553f56f681f2&interactionCount=1&isAnonUser=1&landingPath=NotLandingPage&groups=C0002%3A0%2CC0001%3A1%2CC0003%3A0%2CC0004%3A0%2CV2STACK42%3A0&intType=2&geolocation=PK%3BPB&AwaitingReconsent=false; rid=71ca63; sessionid=QOQIwgNnZz5sLolO25VLuUsQYN5v8WdrnnbExoeD; __Host-authjs.csrf-token=5160965b133460577c3a4cd039eddd96f3d3e33d9621f755d81c6a548379fa81%7Cf7b590cebfe03e3bf042f0f9dc174256ff9c03bf69c1c8ca99a641daf1c2a7bc; __Secure-authjs.callback-url=https%3A%2F%2Fwww.local.ch; localch_debug=%7B%22mmkpi%22%3Afalse%2C%22search%22%3Afalse%7D; __Secure-authjs.session-token=eyJhbGciOiJkaXIiLCJlbmMiOiJBMjU2Q0JDLUhTNTEyIiwia2lkIjoiMU1nVnFvT0tEekwzUTJ6RHV4QVA5TGN3bTlOejNWbXlZX1dGblBjQVFQNFgtWGR5MnJsb3BKRnZsX3FraERoTVlJOXpJWjVyQ0lvc2ZPamd6RXVTalEifQ..Dwh3uDC9zhS8UEMYKL8b5g.v462CyvSZGrA8RdqEemnCMeAANLmQWoU_m00UXW9QaVwAUjiMaJ6uxiqjW8nGq0ag9Xg7u6QnF_7LyW2L3L7QcBUT6NLUf2IXGdnloA19C5CT3koYgTpHcEVD5iZ4oFKeP5_9qkBSgbfM04dYRP682As7FYxJvsFhO400TIp070qiMArV4uWSJOWauTWyCTjQQWNT35UUxAI_0xGg-1Ypc5jv0YZ3R0vE-7lRAe-kLTzkfzJq1O4I_6EAQefeZtSP2NLYMG2ULea1wOhgRQMcOXCa4goW7lpSLN0KxW4AJ64W71IQybyETQF_96sIyJxnZIYaujYbhj07z-NzwSICIiDpYMYl0geYwXAQZOO1_HcbOV0TDQWDoGsfHNk7IH40jKej2RRM01TDaA0huqvE-vFLeGlo4n3zBMNSgVbyBxA6oAc-qAZ8It4_MgKkqnEkLCstUEOprSpgJRovLNwnY3KXb1dGGX1_CgodX-jNdpVObo7dMJDhZ77AHv8d3wfPtVJxIjkdUPPHXloCxj8VyDONTJ9dRHMhOUMCqbFwIxNq9MAfAMS4AIQCGLGH1sh2vFl8UNV9X5yaM6XjVKQxOSlDm6iKoz82wjALFhO9EZzR4cVKNFs4sjzsp5gsFEQ8hKDmlldc0JkuXTlRfUlZLDhwtleBycxWDT4vo7Z0Z2Urd56oCtRVnX4VEY77o8c27MTopKX3R0jjrF82jdhvsEbk8EJ6UcjLLeAelPS42uWspc1ElkC9BL8lCGsOgY6qshat3ApanRULhcNdpw2aPsvovwIGYBUasPHvKFesww.-JNL-_kCSeevuubhhjod2xekmvj0XB3OLBMkBexnqBA; ats_ri=ri=202507251314362028201910&model=202507251314362028201910&models=eyJzcmMiOiJndSIsImF0c19yaSI6IjIwMjUwNzI1MTMxNDM2MjAyODIwMTkxMCJ9&ttl_ms=3600000&expires_ms=1753690459169&version=1753686857.806&fs=519c; adblock-enabled=true',
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
                name=address=""
                soup=BeautifulSoup(response.content,"html.parser")
                name=soup.find("h1",class_="kW").text
                main_div=soup.find("div",class_="nE")
                address_div=main_div.find("div",class_="pT")
                if address_div:
                    address=address.text.replace("Adresse","")
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
                # print(obj)
                return obj
            except Exception as e:
                print(f"Exception has been occur as : {e}")
                traceback.print_exc()
                return url
            
        else:
            print(f"Request have been failed with code :{response.status_code}")
            return url
    except Exception as e:
        traceback.print_exc()
        print(f"Exception has been occur as : {e}")
        return url
def read_db_to_dict_list(table):
    # Connect to the SQLite database using the provided database name
    # db = dataset.connect(f'sqlite:///{database}')
    
    # # Assume the table name is 'scraped_data' (same as used in previous examples)
    # table = db[databaseTable]
    
    # Fetch all rows from the table
    rows = table.find(Scraped=False)
    
    # Convert the result to a list of dictionaries
    rows_list = [dict(row) for row in rows]
    
    return rows_list
def Threading_Page_Urls(PageUrlsData,Scrapedtable,UpdatedTable):
    processes = []
    results = []

    # Set the progress bar to match the number of URLs
    with alive_bar(len(PageUrlsData)) as bar:
        # Use ThreadPoolExecutor for threading
        with ThreadPoolExecutor(max_workers=50) as executor:
            # Submit all tasks
            for index, obj in enumerate(PageUrlsData):
                # print(obj['id'])
                # if obj['id']>=0 and obj['id']<=200000:
                processes.append(executor.submit(retrivePages, obj['Url'],obj['id']))
                # else:
                #     break
            
            # Process the completed tasks
            for task in as_completed(processes):
                result = task.result()
                if isinstance(result, dict):
                    with lock:
                            Scrapedtable.update({'Url': result['Url'], 'Scraped': True}, ['Url'])
                            UpdatedTable.insert(result)
                            results.append(result)
                    # print(result)
                bar()  # Update the progress bar after each task is completed
    
    return results  

def sql_table_to_csv(UpdatedTable ,csv_file_path):
    # Connect to the database
    # db = dataset.connect(f'sqlite:///{db_name}')
    
    # # Retrieve all data from the specified table
    # table = db[table_name]
    rows = list(UpdatedTable.all())  # Convert the iterator to a list of dictionaries
    
    # Convert the list of dictionaries to a pandas DataFrame
    df = pd.DataFrame(rows)
    
    # Save the DataFrame to a CSV file
    df.to_csv(csv_file_path, index=False)
    
    print(f"Data from table '{UpdatedTable}' has been successfully written to '{csv_file_path}'.")
def main():
    db = dataset.connect(f'sqlite:///ScrapedData.db')
    Scrapedtable = db["LocalUrls"]
    UpdatedTable=db['LocalFinalData']
    # time.sleep(5) 
    ScrapedData=read_db_to_dict_list(Scrapedtable)
    Threading_Page_Urls(ScrapedData,Scrapedtable,UpdatedTable)
    FinalDataCSVName="FinalDataLocalSample1.csv"
    sql_table_to_csv(UpdatedTable,FinalDataCSVName)

if __name__ == "__main__":
    main()
# def process_urls_from_txt(file_path):
#     # Step 1: Read URLs from the txt file and store them in a list
#     urls = []
#     try:
#         with open(file_path, 'r') as file:
#             # Read each line (each line should be a URL)
#             urls = [line.strip() for line in file.readlines()]
#     except FileNotFoundError:
#         print(f"File '{file_path}' not found.")
#         return
#     except Exception as e:
#         print(f"An error occurred: {e}")
#         return
#     Main_list=[]
#     # Step 2: Iterate over the list of URLs
#     index=0
#     for url in urls:
#         index=index+1
#         if index<200:
#         # Process each URL here, e.g., make a request, print the URL, etc.
#             Main_list.append(retrivePages(url))
#             print(f"Processing URL: {url}")
#         else:
#             break
#         # You can add logic to handle each URL as per your requirement
#     df=pd.DataFrame(Main_list)
#     df.to_csv("OutPutResultForLocal2.csv")
# # Example usage
# file_path = "extracted_urls.txt"  # Path to your txt file
# process_urls_from_txt(file_path)
