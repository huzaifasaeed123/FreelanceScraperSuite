import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, parse_qs
from concurrent.futures import ThreadPoolExecutor, as_completed
import traceback
from alive_progress import alive_bar
proxy = ""
proxies = {
    "http": proxy,
    "https": proxy
}

def get_item(url,cattype):
    headers = {
        "User-Agent": "Mozilla/5.0"
    }
    while True:
        try:
            response = requests.get(url, headers=headers,proxies=proxies)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')

                table = soup.find('table', class_='catalog-list__body-main')
                tem_list=[]
                if table:
                    tds = table.find_all('td', nowrap=True)
                    for td in tds:
                        a_tag = td.find('a', href=True)
                        if a_tag and "/v2/catalog/catalogitem.page?" in a_tag['href']:
                            parsed_url = urlparse(a_tag['href'])
                            query_params = parse_qs(parsed_url.query)
                            s_param = query_params.get(cattype)
                            if s_param:
                                # stored_list.append(s_param[0])
                                # print(f"Parsed Url :{url}")
                                tem_list.append(s_param[0])
                    print(f"Parsed Url :{url}")
                    return  tem_list     
                else:
                    print(f"Data(Table) has not been Found")
            else:
                    print(f"Error has been Occur during fetching item No with status code :{response.status_code} with error : {response.text}")
        except Exception as e:
            print(e)
def get_all_items(pageNo,cattype):
    print(f"Getting All CatType: {cattype}")
    processes = []
    stored_list=[]
    with alive_bar(pageNo) as bar:
        with ThreadPoolExecutor(max_workers=20) as executor:
            for page in range(1, pageNo+1):
                # print(obj['id'])
                # if index>=0 and index<=40000:
                    url=f"https://www.bricklink.com/catalogList.asp?pg={page}&catLike=W&sortBy=I&sortAsc=A&catType={cattype}&v=0"
                    processes.append(executor.submit(get_item,url,cattype))
                # else:
                #     break
            # Process the completed tasks
            for task in as_completed(processes):
                if isinstance(task.result(), list): 
                    stored_list.extend(task.result())
                bar()  # Update the progress bar after each task is completed
    
    return stored_list

set_list=get_all_items(409,"S")  # Sets
minifigure_list=get_all_items(352,"M")  #Minifigure
parts_list=get_all_items(1757,"P")  #Parts
with open('Setitems.txt', 'w') as file:
    for item in set_list:
        file.write(f"{item}\n")
with open('Minifigureitems.txt', 'w') as file:
    for item in minifigure_list:
        file.write(f"{item}\n")
with open('Partsitems.txt', 'w') as file:
    for item in parts_list:
        file.write(f"{item}\n")





        