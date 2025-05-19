# item_scraper.py
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

def get_item(url, cattype):
    headers = {
        "User-Agent": "Mozilla/5.0"
    }
    while True:
        try:
            response = requests.get(url, headers=headers, proxies=proxies)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')

                table = soup.find('table', class_='catalog-list__body-main')
                tem_list = []
                if table:
                    tds = table.find_all('td', nowrap=True)
                    for td in tds:
                        a_tag = td.find('a', href=True)
                        if a_tag and "/v2/catalog/catalogitem.page?" in a_tag['href']:
                            parsed_url = urlparse(a_tag['href'])
                            query_params = parse_qs(parsed_url.query)
                            s_param = query_params.get(cattype)
                            if s_param:
                                tem_list.append(s_param[0])
                    print(f"Parsed Url: {url}")
                    return tem_list     
                else:
                    print(f"Data(Table) has not been Found")
            else:
                print(f"Error has been Occur during fetching item No with status code: {response.status_code} with error: {response.text}")
        except Exception as e:
            print(e)

def get_all_items(page_no, cattype):
    """
    Get all items for a given category type
    Returns a list of item numbers instead of writing to file
    """
    print(f"Getting All CatType: {cattype}")
    processes = []
    stored_list = []
    
    with alive_bar(page_no) as bar:
        with ThreadPoolExecutor(max_workers=20) as executor:
            for page in range(1, page_no + 1):
                url = f"https://www.bricklink.com/catalogList.asp?pg={page}&catLike=W&sortBy=I&sortAsc=A&catType={cattype}&v=0"
                processes.append(executor.submit(get_item, url, cattype))
            
            # Process the completed tasks
            for task in as_completed(processes):
                if isinstance(task.result(), list): 
                    stored_list.extend(task.result())
                bar()  # Update the progress bar after each task is completed
    
    return stored_list