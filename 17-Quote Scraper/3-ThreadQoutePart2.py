import requests
import json
from bs4 import BeautifulSoup
import pandas as pd
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from time import time
from alive_progress import alive_bar
import pickle

def retriveQoute(data,index):
    try:
        url1=data["QouteLink"]
        url=f"https://quote.org{url1}"
        url="https://quote.org/quote/fifteen-negroes-in-whose-hands-we-had-643578"
        # print(url)
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
            soup=BeautifulSoup(response.content,'html.parser',from_encoding="iso-8859-1")
            Context=ciation=relatedQoutes=ConceptBox=QouteText=""
            QouteText=soup.find('div',class_="quote-text").text.strip()
            # print(QouteText)
            ConceptLinks=soup.find_all("a",class_="linkbox-text")
            for box in ConceptLinks:
                ConceptBox=ConceptBox + box.text.strip() +","
                
            # print("Concept Box",ConceptBox)
            Context=ciation=relatedQoutes=""
            main_divs=soup.find_all('div',class_="section")
            for div in main_divs:
                headerTitle=div.find('div',class_="section-header-title",recursive=False)
                headerIcon=div.find('div',class_="section-header-icon",recursive=False)
                if headerTitle and headerIcon:
                    HeaderText=headerTitle.get_text().strip()
                    # print(HeaderText)
                    if HeaderText=="Context":
                        headerTitle.decompose()
                        headerIcon.decompose()
                        Context=div.get_text().strip()
                        # print(Context)
                    elif HeaderText=="Citations":
                        headerTitle.decompose()
                        headerIcon.decompose()
                        ciation=div.get_text().strip()
                        # print(ciation)
                        # paragraphs=div.find_all('p',recursive=False)
                        # for para in paragraphs:
                        #     ciation=ciation + para.get_text()+" "
                        # print(ciation)
                    elif HeaderText=="Related Quotes":
                        headerTitle.decompose()
                        headerIcon.decompose()
                        relatedQoutes=div.get_text().strip()
                        # print(relatedQoutes)
            obj1={
                "QouteText":QouteText,
                "ConceptBox":ConceptBox,
                "relatedQoutes":relatedQoutes,
                "ciation":ciation,
                "Context":Context
            }
            merged_obj = {**obj1, **data}
            print("Index No is",index)
            return merged_obj
        else:
            return None
    except Exception as e:
        return None
  
with open('AuthorThreading.pkl', 'rb') as file:
    objects = pickle.load(file)

start = time()
processes = []
result=[]
count = 0
print(len(objects))
with alive_bar(len(objects) - 0) as bar:
    with ThreadPoolExecutor(max_workers=1) as executor:
        for index, data in enumerate(objects):
            # print(index)
            if index==0000:
                #print(index)
                processes.append(executor.submit(retriveQoute,data,index))
for task in as_completed(processes):
    # print(type(task.result()))
    if type(task.result()) is dict:
        result.append(task.result())
        # result+=task.result()
        # print(task.result())
    else:
        pass
df = pd.DataFrame(result)

df.to_csv("testing.csv", index=False,encoding='utf-8')


print(f'Time taken: {time() - start}')
