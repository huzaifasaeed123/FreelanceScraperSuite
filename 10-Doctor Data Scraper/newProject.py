import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from time import time
from bs4 import BeautifulSoup
from alive_progress import alive_bar
import pandas as pd
# URL for the POST request

# proxydelai = "198.204.241.50:17047"
# proxy = {
#     "http": f"http://{proxydelai}",
#     "https": f"http://{proxydelai}"
# }
proxy = {
    "http": "http://saeedhuzaifa678_gmail_com:Saeed123@la.residential.rayobyte.com:8000",
    "https": "http://saeedhuzaifa678_gmail_com:Saeed123@la.residential.rayobyte.com:8000"
}

def makeRequest(payload):
    # try:
        url = "https://healthreg-public.admin.ch/api/medreg/public/person"

        # Payload with the ID
        payload = {  "id": 208607  # Replace 'your_id_here' with the actual ID you want to use
        }

        # Headers for the POST request
    
        headers = {
            "api-key": "AB929BB6-8FAC-4298-BC47-74509E45A10B",
            # "connection": "keep-alive",
            # "content-length": "13",
            "content-type": "application/json",
            "cookie": "cookiesession1=678B77A21CE57C126282ED8B6BCB82A3;",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
            "x-requested-with": "XMLHttpRequest",
            # "x-time-zone-iana": "Asia/Karachi"
        }
        session=requests.Session()
        session.proxies.update(proxy) 
        # Send the POST request
        # response1=session.get("https://healthreg-public.admin.ch/psyreg/",headers=headers)
        response = session.post(url, json=payload, headers=headers)

        # Check if the request was successful
        if response.status_code == 200:
            # Parse the response JSON data
            data = response.json()
            # print(data)
            firstname=name=language=nation=profession=cetTitleType=cetTitleKind=""
            name=data["name"]
            firstname=data["firstName"]
            nationalities=data['nationalities']
            if nationalities:
                for nationality in nationalities:
                    nation=nation+nationality['textEn']+"/"
                # print("Response JSON data:",nation)
            languageSkills=data['languageSkills']
            if languageSkills:
                for SingleLanguage in languageSkills:
                    language=language+SingleLanguage['textEn']+"/"
                # print("Response JSON data:",language)
            if data["cetTitles"][0]:
                if data["cetTitles"][0]["profession"]["textEn"]:
                    profession=data["cetTitles"][0]["profession"]["textEn"]
                if data["cetTitles"][0]["cetTitleType"]["textEn"]:
                    cetTitleType=data["cetTitles"][0]["cetTitleType"]["textEn"]
                if data["cetTitles"][0]["cetTitleKind"]["textEn"]:
                    cetTitleKind=data["cetTitles"][0]["cetTitleKind"]["textEn"]
                # print(profession,cetTitleKind,cetTitleType)

                permissions=data["cetTitles"][0]["permissions"]
                email=zipcity=phoneNumber=streetWithNumber=""
                if permissions:
                    for SinglePermission in permissions:
                        addresses=SinglePermission["addresses"]
                        if addresses:
                            for address in addresses:
                                if address["email"]:
                                    email=email+address["email"]+"/"
                                if address["zipCity"]:
                                    zipcity=zipcity+address["zipCity"]+"/"
                                if address["phoneNumber"]:
                                    phoneNumber=phoneNumber+address["phoneNumber"]+"/"
                                if address["streetWithNumber"]:
                                    streetWithNumber=streetWithNumber+address["streetWithNumber"]+"/"
            bar()
            row=[language,nation,profession,cetTitleType,cetTitleKind,email,zipcity,phoneNumber,streetWithNumber]
            obj1={"Name":name,"FirstName":firstname,"languageSkills":language,"Nationalities":nation,"Profession":profession,"TitleType":cetTitleType,"TitleKind":cetTitleKind,"Email":email,"PhoneNumber":phoneNumber,"Address(Zip & City)":zipcity,"StrretWithNumber":streetWithNumber}
            print(obj1)
            return obj1
            # print(email,zipcity,phoneNumber,streetWithNumber)               
        else:
            bar()
            print(f"Failed to get data. Status code: {response.status_code}")
            return None
            # print("Response content:", response.content)
    # except Exception as e:
    #     return None

start = time()

processes = []
result=[]
count = 0
with alive_bar(110000 - 100000) as bar:
    with ThreadPoolExecutor(max_workers=3) as executor:
        for i in range(208607, 208608):
            processes.append(executor.submit(makeRequest,i))
for task in as_completed(processes):
    print(type(task.result()))
    if type(task.result()) is dict:
        result.append(task.result())
        print(task.result())
        # with open('resultgrw2023.csv', 'a', newline='') as new:
        #     count += 1
        #     # print(count)
        #     res_writer = csv.writer(new, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
        #     try:
        #         res_writer.writerow(task.result())
        #     except Exception as e:
        #         with open('exc.txt', 'a') as ex:
        #             ex.write(f'{e}\n')
    else:
        pass
df = pd.DataFrame(result)

df.to_csv("Bhabhi3.csv", index=False,encoding='utf-8')
print(f'Time taken: {time() - start}')