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

def retrivePages(url,id):
    # url="https://www.local.ch/de/d/basel/4051/restaurant/indisches-restaurant-bajwa-palace-RssWWtrY8Z_NP4QaCkVSsw"
    # url="https://www.local.ch/de/d/wetzikon-zh/8620/holzbau/freuler-holzbau-Itd-FbLS5PhgSkWz3o2zlQ"
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "max-age=0",
        "Cookie": ("OptanonAlertBoxClosed=2024-08-22T12:28:51.102Z; "
                "eupubconsent-v2=CQDvjvgQDvjvgAcABBDEBCFgAAAAAAAAAAQ4AAAUcgDgA4AM-A7YCfYFFAKLQUaBRwAA.YAAAAAAAAAAA; "
                "deviceid=qdmsztte96euxihhxyw8v0t5lkursfthocybfb6h; ea_uuid=202408232114279494208932; "
                "__gads=ID=84b203acce559956:T=1724329727:RT=1724444610:S=ALNI_MYsVV8l1iEbAHtQy85bBQN_3yXKeg; "
                "__gpi=UID=00000ed46675ea2c:T=1724329727:RT=1724444610:S=ALNI_MZdWrQ2MRJ2b7XIW9LuUsxJcilJkw; "
                "__eoi=ID=81a7b471cb74968d:T=1724329727:RT=1724444610:S=AA-AfjbP5oc70b5f0rKCTQjxzFOU; "
                "localch=Fe26.2*1*4979d3aeb93802d1cce445b3597a46055f69afa5a0c07563bc039df8db1d8743*7h9cgRc-uJRJdXKYs3pArQ*gDPk6xyOlK83fRSrSBQBppDePEbE3hanfND9aKZJvdZkvtv97Tdr8Z67E2Ei3sQwVtkFm1EvwnwlUvdIgCX9Bpdp1sbJrPRYe8k_BuakxI1LicAo0dTE1d0C-_Hzg5DTRSA2T3wN_YEZkmK_bzysCZNlz0Mx-XRj5Ch5W83p1g_6JPN1vyO_SINBERleZNy0wXr2InL-haHO8-YQDljxnzvADJELZcz9ce13jzLH5pIZJ_nrOVQ7s4mPpbC5iKZFrSZlyCBUa3PjSztCEmewYN0oQF3du9RKvDMz9dvBTaOrSX8m218Wb1-1yZaoxYbQrU5yq4Qn44pnPbSZD-Udj4DGSwXLTQAxaFTMwb_DsNF0DZxemvFP9lmtYJTqC1yFktkeJn4vnzKF0SnSFRB8nwD7rcm_u0wOOlQ81s4PzRASwFqgKp7504IhhNHM7k7ILgYjtX7ECngpYL2Gi-ucez1UgEqOJThSS9u9n0mH35LQwIvrgMv_ziqaXcb81huKU3Jdn5emp3YBM3cSrlv2tg*1725289754894*99ccf3a7f562b8eb60776c6dba924d054d2e8a9459dd38fc825a42de3f2549c6*0S0aAWoCnsIs3wngGgkCdtYV7yX-aBpjKCDb-vdxi1s~2; "
                "sessionid=k0oOYN70z87eOFo3WaDSk9uA9MBcX3XWhxmBSQlj; adblock-enabled=false; "
                "OptanonConsent=isGpcEnabled=0&datestamp=Mon+Aug+26+2024+20%3A09%3A21+GMT%2B0500+(Pakistan+Standard+Time)&"
                "version=202407.2.0&browserGpcFlag=0&isIABGlobal=false&hosts=&consentId=f1a6d405-9db8-4ad1-955b-f9cdaa877a23&"
                "interactionCount=1&isAnonUser=1&landingPath=NotLandingPage&groups=C0002%3A0%2CC0001%3A1%2CC0003%3A0%2C"
                "C0004%3A0%2CV2STACK42%3A0&intType=2&geolocation=PK%3BPB&AwaitingReconsent=false; "
                "ats_ri=fp_ms=1724684965473&ri=202408232114279494208932&model=202408232114279494208932&"
                "models=eyJhdHNfcmkiOiIyMDI0MDgyMzIxMTQyNzk0OTQyMDg5MzIifQ%3D%3D&ttl_ms=3600000&"
                "expires_ms=1724450407470&version=1724446807.524&fs="),
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
    response = requests.get(url,headers=headers)
    # print(response.status_code)
    if response.status_code==200:
        name=address="Not Found"
        soup=BeautifulSoup(response.content,"html.parser")
        name=soup.find("h1",class_="DetailHeaderRow_title__dIOK3").text
        main_div=soup.find("div",class_="ContactDetailsRow_contactInfoCol__dwQCZ")
        address=main_div.find("div",class_="DetailMapPreview_addressInfoContainer__qRsKX").text
        li_items=main_div.find_all("li",class_="ContactGroupsAccordion_contactGroup__dsb2_")
        email=website=""
        Telefon=[]
        Mobiltelefon=[]
        WhatsApp=[]
        for li in li_items:
            label=li.find("label",class_="ContactGroupsAccordion_contactType__8Y1ED",recursive=False)
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
        return {
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
