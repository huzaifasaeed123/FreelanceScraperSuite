import requests
import json
from bs4 import BeautifulSoup
import pandas as pd
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from time import time
from alive_progress import alive_bar
import pickle
from datetime import datetime

def retrieveAuthorInformation():
    url = "https://quote.org/Authors"
    
    headers = {
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "en-US,en;q=0.9",
        "Content-Length": "976",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Cookie": "_ga=GA1.1.2065737631.1722282952; .AspNetCore.Antiforgery.Z0BgdIcYxfQ=CfDJ8ObHffAmizBDk30Qlggqj4P3ZhZPfUAl2hK71ZyfhMzHTO0FDgsz0amLTEdG1i0D_a0ti8-SbE_oOVAnRC7DxeheeZkECn4YlNgbpzOCrEwV2lCSezyD4jMa0UIv9FgeFfoQyP0gGZ5LciwPqtvjpHk; _ga_32V6RHVRCY=GS1.1.1722782425.5.1.1722786367.0.0.0; AWSALB=O+Zcg00kS5D2hvZgsYtuXJSkeJRzuRlsbJqo/zcQPK+uQXg20cPzbAf1h0/3eLgHm/sCzfsiAI/EzKuZ1IToWV18/XRf2HQV7eys2ONB5pyw4t74nuTuk9ByNk3g; AWSALBCORS=O+Zcg00kS5D2hvZgsYtuXJSkeJRzuRlsbJqo/zcQPK+uQXg20cPzbAf1h0/3eLgHm/sCzfsiAI/EzKuZ1IToWV18/XRf2HQV7eys2ONB5pyw4t74nuTuk9ByNk3g",
        "Origin": "https://quote.org",
        "Priority": "u=1, i",
        "Referer": "https://quote.org/authors",
        "Sec-CH-UA": "\"Not)A;Brand\";v=\"99\", \"Google Chrome\";v=\"127\", \"Chromium\";v=\"127\"",
        "Sec-CH-UA-Mobile": "?0",
        "Sec-CH-UA-Platform": "\"Windows\"",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
        "X-Requested-With": "XMLHttpRequest",
        "XSRF-Token": "CfDJ8ObHffAmizBDk30Qlggqj4MSp-baj01L00K7B27MnV7SWwInJFxSgoo-MnZB_n-HKwQa8SMctINdaakpEl06fp9ZoxMVJZ18y4KifJT4cVeRuzramXYgBB4opzxz0mgv6C9K9bYQK-zECcfRJ2CLoyY"
    }
    
    payload = {
        "draw": "2",
        "columns[0][data]": "name",
        "columns[0][name]": "",
        "columns[0][searchable]": "true",
        "columns[0][orderable]": "true",
        "columns[0][search][value]": "",
        "columns[0][search][regex]": "false",
        "columns[1][data]": "alias",
        "columns[1][name]": "",
        "columns[1][searchable]": "true",
        "columns[1][orderable]": "true",
        "columns[1][search][value]": "",
        "columns[1][search][regex]": "false",
        "columns[2][data]": "profession",
        "columns[2][name]": "",
        "columns[2][searchable]": "true",
        "columns[2][orderable]": "true",
        "columns[2][search][value]": "",
        "columns[2][search][regex]": "false",
        "columns[3][data]": "nationality",
        "columns[3][name]": "",
        "columns[3][searchable]": "true",
        "columns[3][orderable]": "true",
        "columns[3][search][value]": "",
        "columns[3][search][regex]": "false",
        "columns[4][data]": "born",
        "columns[4][name]": "",
        "columns[4][searchable]": "true",
        "columns[4][orderable]": "true",
        "columns[4][search][value]": "",
        "columns[4][search][regex]": "false",
        "order[0][column]": "0",
        "order[0][dir]": "asc",
        "start": "0",
        "length": "41256",
        "search[value]": "",
        "search[regex]": "false"
    }
    response = requests.post(url, headers=headers, data=payload)
    if response.status_code == 200:
        print(f"Author Request Detail Has been Successful with status Code: {response.status_code}")
        json_data = response.json()
        with open("Data.json", 'w') as file:
            json.dump(json_data, file, indent=4)
        datas = json_data['data']
        Author_data = []
        AuthorName = profession = nationality = ""
        for data in datas:
            name = data.get("name")
            if name:
                name_soup = BeautifulSoup(name, "html.parser")
                # print(name_soup)
                AuthorName = name_soup.text
                AuthorLink = name_soup.find('a')['href'] if name_soup.find('a') else None
            profession = data.get('profession', '')
            nationality = data.get('nationality', '')
            Author_data.append({
                "AuthorName": AuthorName,
                "AuthorLink": AuthorLink,
                "profession": profession,
                "nationality": nationality
            })
        print("Data retrivel Done")
        return Author_data
    else:
        print("Failed")
def retriveAllAuthorQoutes(author,index):
    Main_data=[]
    # index=0
    # print(index)
    # print(author)
    # index=index+1
    base_url="https://quote.org"
    link=author.get('AuthorLink')
    # print(link)
    url=f"{base_url}{link}"
    # url="https://quote.org/author/a-a-milne-40054" #Testing Purpose
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "en-US,en;q=0.9",
        "Cookie": "_ga=GA1.1.2065737631.1722282952; .AspNetCore.Antiforgery.Z0BgdIcYxfQ=CfDJ8ObHffAmizBDk30Qlggqj4P3ZhZPfUAl2hK71ZyfhMzHTO0FDgsz0amLTEdG1i0D_a0ti8-SbE_oOVAnRC7DxeheeZkECn4YlNgbpzOCrEwV2lCSezyD4jMa0UIv9FgeFfoQyP0gGZ5LciwPqtvjpHk; _ga_32V6RHVRCY=GS1.1.1722789075.6.1.1722791375.0.0.0; AWSALB=HAi3y4qOu9W7yt6eP17bsX1tzkZZhsiOoh2Q917ZcSjIuTj1m3JbsA+11Wcel/FRUOpfZMEHSIIjunP8ugQHeShQJ8KhLKfOb1yOoD1tZlTODrmiDjhLLnfhyQuF; AWSALBCORS=HAi3y4qOu9W7yt6eP17bsX1tzkZZhsiOoh2Q917ZcSjIuTj1m3JbsA+11Wcel/FRUOpfZMEHSIIjunP8ugQHeShQJ8KhLKfOb1yOoD1tZlTODrmiDjhLLnfhyQuF",
        "Priority": "u=0, i",
        "Referer": "https://quote.org/authors",
        "Sec-CH-UA": "\"Not)A;Brand\";v=\"99\", \"Google Chrome\";v=\"127\", \"Chromium\";v=\"127\"",
        "Sec-CH-UA-Mobile": "?0",
        "Sec-CH-UA-Platform": "\"Windows\"",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"
    }
    response=requests.get(url,headers=headers)
    if response.status_code==200:
        soup=BeautifulSoup(response.content,'html.parser')
        QouteList=[]
        born=died=biograph=""
        main_divs=soup.find_all('div',class_="titled-section")
        for div in main_divs:
            headerTitle=div.find('div',class_="section-header-title",recursive=False)
            HeaderText=headerTitle.get_text().strip()
            # print(HeaderText)
            if HeaderText=="About the Author":
                # print("sfd")
                uls=div.find_all('li')
                for item in uls:
                    heading = item.find('strong').text.strip()
                    text = item.text.split(': ')[1].strip()
                    if heading=="Born":
                        if len(text) >3:
                            text=parse_and_format_date(text)
                        born=text
                    elif heading=="Died":
                        if len(text) >3:
                            text=parse_and_format_date(text) 
                        died=text
                    # print(heading,text)
            elif HeaderText=="Biography":
                paragraph=div.find('p',recursive=False)
                biograph=paragraph.get_text()
                # print(biograph)
            elif HeaderText=="Quotes":
                qouteslinks=div.find_all("a",class_="trlink spinner",recusive=False)
                for link in qouteslinks:
                    # print(link["href"])
                    QouteList.append(link["href"])
        for qoutelink in QouteList:
            # obj1=retriveQoute(qoutelink)
            obj3={"born":born,"died":died,"biograph":biograph}
            obj4={"QouteLink":qoutelink}
            merged_obj = {**author,**obj3,**obj4}
            Main_data.append(merged_obj)
    # if index==1000:
    #     break
    # print(Main_data)
    print("Index No is",index)
    return Main_data
def parse_and_format_date(date_str):
    # Define possible date formats
    formats = ["%B %d, %Y", "%m/%d/%Y"]
    
    for fmt in formats:
        try:
            # Try to parse the date string with the current format
            date_obj = datetime.strptime(date_str, fmt)
            # If successful, return the date in the desired format
            return date_obj.strftime("%Y-%m-%d")
        except ValueError:
            continue
    
    # If no formats matched, raise an error
    return ""
    # raise ValueError(f"Date format not recognized for: {date_str}")
def objects_to_excel(objects, filename):
    """
    Convert a list of objects into an Excel file.

    Parameters:
    objects (list): List of dictionaries representing the objects.
    filename (str): The name of the Excel file to save.

    Returns:
    None
    """
    # Convert the list of objects into a DataFrame
    df = pd.DataFrame(objects)
    
    # Save the DataFrame to an Excel file
    df.to_excel(filename, index=False)
data=retrieveAuthorInformation()
start = time()

processes = []
result=[]
count = 0
with alive_bar(len(data) - 0) as bar:
    with ThreadPoolExecutor(max_workers=3) as executor:
        for index, author in enumerate(data):
            if index<=100:
                processes.append(executor.submit(retriveAllAuthorQoutes,author,index))
for task in as_completed(processes):
    # print(type(task.result()))
    if type(task.result()) is list:
        # result.append(task.result())
        result+=task.result()
        # print(task.result())
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

df.to_csv("AuthorThreading.csv", index=False,encoding='utf-8')

# listdata=retriveAllAuthorQoutes(data)
# objects_to_excel(result)
with open('AuthorThreading.pkl', 'wb') as file:
    pickle.dump(result, file)
# print(listdata)
print(f'Time taken: {time() - start}')