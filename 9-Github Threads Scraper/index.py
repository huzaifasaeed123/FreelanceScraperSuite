import requests
import json
from bs4 import BeautifulSoup
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from alive_progress import alive_bar
import threading
import dataset
import traceback

def retrivePageUrls(url,URL_List):
    response=requests.get(url)
    if response.status_code==200:
        soup=BeautifulSoup(response.content,"html.parser")
        li_items=soup.find("ol",class_="gutter").find_all("li",recursive=False)
        # print(len(li_items))
        for li in li_items:
            # print(li.text)
            a=li.find("a")
            URL_List.append(a.get("href"))
            # print(a.get("href"))

def getCount(url,Main_Url):
    response=requests.get(url)
    if response.status_code==200:
        soup=BeautifulSoup(response.content,"html.parser")
        all_a=soup.find_all("a")
        for a in all_a:
            if a.get("href")==Main_Url:
                count=int(a.find("span",class_="Counter").get("title").replace(",", ""))
                print(count)
        count=int(count/48) + 1
        return count
def retriveIndividualPages(url,index):
    try:
        headers = {
        "Cookie": "_device_id=3589cf40c4f160063732c00bb14c1721; user_session=iRslm4P_yKfnVFhMA05RMjTU0LGPA1ulhi5Xd-T0sAU62mpm; __Host-user_session_same_site=iRslm4P_yKfnVFhMA05RMjTU0LGPA1ulhi5Xd-T0sAU62mpm; logged_in=yes; dotcom_user=huzaifasaeed123; GHCC=Required:1-Analytics:1-SocialMedia:1-Advertising:1; MicrosoftApplicationsTelemetryDeviceId=2cb0b163-4a02-4e21-9018-41bd9af3908d; MSFPC=GUID=88692c671b9f4a58b7407800d9011686&HASH=8869&LV=202308&V=4&LU=1692817330445; _octo=GH1.1.582398321.1724854094; color_mode=%7B%22color_mode%22%3A%22auto%22%2C%22light_theme%22%3A%7B%22name%22%3A%22light%22%2C%22color_mode%22%3A%22light%22%7D%2C%22dark_theme%22%3A%7B%22name%22%3A%22dark%22%2C%22color_mode%22%3A%22dark%22%7D%7D; preferred_color_mode=dark; tz=Asia%2FKarachi; _gh_sess=jL%2Fd%2B%2FJYjrwH2l%2BG51oK%2BKSStlXmS7LZNsiFtLoc4UO%2FZfOQNvOyW%2Fwk%2BX1ioN94BuoT087Ng3TnbANKKF7%2FrD7MtnxZ1iIUE2ouudOR7d8yrFQn9WvrTN1U0pVQdQIOlZAv3%2BZuvJB%2FRu9JTWR%2FmCLQCZ9sY5Nv5bthJl4e1dX7AYCX4U2N0qj%2FFd4rXn4jLSs3wP%2Bx8ixg33Nd44XnetsPw%2FrZ9U2rzX6BC2S3b7F5EiL1E8duq9WvxOZWcilQ1Dwm7P1BlbIjYY5I31p9GYQuYm65ri4Oi8%2FZuRjhi18WhgxzmNXCVRakJJGpENe%2FtcQYFTF43q660IJK5Lbt5xtRdrb1ZX0tJUmUTA%3D%3D--OEMgDs7JAcQH6Alm--2tJpKT5VEkkbwbVuCZn%2Bhg%3D%3D",
        "If-None-Match": 'W/"e41dd47bc8deb21113ab32ec8ead91f2"',
        "Priority": "u=1, i",
        "Referer": "https://github.com/dustinmoris",
        "Sec-CH-UA": '"Chromium";v="128", "Not;A=Brand";v="24", "Google Chrome";v="128"',
        "Sec-CH-UA-Mobile": "?0",
        "Sec-CH-UA-Platform": '"Windows"',
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "X-Requested-With": "XMLHttpRequest"
    }
        response=requests.get(url)
        if response.status_code==200:
            Name=UserName=Bio=following=followers=""
            soup=BeautifulSoup(response.content,"html.parser")
            spanName=soup.find("span",class_="vcard-fullname")
            # print(spanName)
            if spanName:
                Name=spanName.text.strip()
                # print("Name",Name)
            spanUserName=soup.find("span",class_="vcard-username")
            if spanUserName:
                UserName=spanUserName.text.strip()
            DivBio=soup.find("div",class_="user-profile-bio")
            if DivBio:
                Bio=DivBio.text.strip()
            all_a=soup.find_all("a")
            for a in all_a:
                if "followers" in a.get("href"):
                    # print(a)
                    # print("huzaifa saeed")
                    followers_span=a.find("span")
                    if followers_span:
                        followers=followers_span.text.strip()
                    # print(followers)
                if "following" in a.get("href"):
                    # print(a)
                    following_span=a.find("span")
                    if following_span:
                        following=following_span.text.strip()
                    # print(following)
            ul=soup.find("ul",class_="vcard-details")
            facebook=twitter=linkin=Instagram=worksFor=homeLocation=""
            Personal_url=[]
            if ul:
                li_items=ul.find_all("li",recursive=False)
                for li in li_items:
                    # print(li.get("itemprop"))
                    if li.get("itemprop")=="homeLocation":
                        homeLocation=li.text.strip()
                    elif li.get("itemprop")=="worksFor":
                        worksFor=li.text.strip()
                    elif li.get("itemprop")=="url":
                        Personal_url.append(li.text.strip())
                    elif li.get("itemprop")=="social":
                        social_Link=li.find("a").get("href")
                        if "instagram.com" in social_Link:
                            Instagram=social_Link
                        elif "linkedin.com" in social_Link:
                            linkin=social_Link
                        elif "twitter.com" in social_Link:
                            twitter=social_Link
                        elif "facebook.com" in social_Link:
                            facebook=social_Link
            # print(Name,UserName,Bio)
            print(homeLocation)
            print("Reached Individual Pages Scraping::",index)
            return {
                "URL": url,
                "Name": Name,
                "UserName": UserName,
                # "Description": Bio,
                "Location": homeLocation,
                "Company": worksFor,
                "Facebook": facebook,
                "Twitter": twitter,
                "LinkdIn": linkin,
                "Instagram": Instagram,
                "Followers": followers,
                "Following": following,
                "Personal Website 1": Personal_url[0] if len(Personal_url) > 0 else "",
                "Personal Website 2": Personal_url[1] if len(Personal_url) > 1 else "",
                "Personal Website 3": Personal_url[2] if len(Personal_url) > 2 else "",
                "Personal Website 4": Personal_url[3] if len(Personal_url) > 3 else "",
            }                           
            # print(facebook,twitter,linkin,Instagram,Personal_url,worksFor,homeLocation)
        else:
            return url    
            # print("Email",email)
    except Exception as e:
        print(e)
        traceback.print_exc()
        return url

def ThreadingPages(PageUrlsData,base_link):
    processes = []
    results = []
    Missing=[]
    with alive_bar(len(PageUrlsData)) as bar:
        # Use ThreadPoolExecutor for threading
        with ThreadPoolExecutor(max_workers=1) as executor:
            # Submit all tasks
            for index, PageUrl in enumerate(PageUrlsData):
                url=f"{base_link}{PageUrl}"
                # print(obj['id'])
                # if index>=0 and index<=40000:
                processes.append(executor.submit(retriveIndividualPages, url,index))
                # else:
                #     break
            # Process the completed tasks
            for task in as_completed(processes):
                if isinstance(task.result(), dict): 
                    # with lock:
                    #         Scrapedtable.update({'Url': result['Url'], 'Scraped': True}, ['Url'])
                    #         UpdatedTable.insert(result)
                    results.append(task.result())
                else:
                    Missing.append(task.result())
                    # print(result)
                bar()
    return [results,Missing]
def Final_updation_inDB(UpdatedTable,list):
    UpdatedTable.insert_many(list)
    print("Done Insertionion of Updated Database")
def makeCSV(Data_List,path):
    df=pd.DataFrame(Data_List)
    df.to_csv(path,index=False,encoding='utf-8')
def sql_table_to_csv(UpdatedTable ,csv_file_path):
    # Connect to the database
    # db = dataset.connect(f'sqlite:///{db_name}')
    
    # # Retrieve all data from the specified table
    # table = db[table_name]
    rows = list(UpdatedTable.all())  # Convert the iterator to a list of dictionaries
    
    # Convert the list of dictionaries to a pandas DataFrame
    df = pd.DataFrame(rows)
    
    # Save the DataFrame to a CSV file
    df.to_excel(csv_file_path, index=False)
    
    print(f"Data from table '{UpdatedTable}' has been successfully written to '{csv_file_path}'.")

def main():
    # https://github.com/kube-hetzner/terraform-hcloud-kube-hetzner/stargazers
    url = input("Enter a URL: ")
    if "github.com" not in url:
        return
    Main_Url=url.replace("https://github.com","")
    base_link="https://github.com"
    # Main_Url="/kube-hetzner/terraform-hcloud-kube-hetzner/stargazers"
    URL=f"{base_link}{Main_Url}"
    count=getCount(URL,Main_Url)
    PageUrlsData=[]
    for i in range(1,count+1):
        url=f"{URL}?page={i}"
        print(url)
        retrivePageUrls(url,PageUrlsData)
        # break
    CombineList=ThreadingPages(PageUrlsData,base_link)
    db = dataset.connect(f'sqlite:///GitHubdata1.db')
    UpdatedTable=db['FinalData']
    Final_updation_inDB(UpdatedTable,CombineList[0])
    sql_table_to_csv(UpdatedTable,"GitHubData1.xlsx")
    # makeCSV(CombineList[0],"Githubdata1.csv")
    makeCSV(CombineList[1],"GithubdataMissing1.csv")

if __name__ == "__main__":
    main()