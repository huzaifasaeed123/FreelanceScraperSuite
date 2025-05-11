# 1st Code that scrap two things
# 1)Main Page Content
# 2)Table Page Content
import os
import re
import json
import requests
import dataset
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from concurrent.futures import ThreadPoolExecutor, as_completed
from alive_progress import alive_bar

# Setup dataset connection
DB = dataset.connect("sqlite:///bricklink_data.db")
TABLE = DB["minifigures"]
inputtext="Minifigureitems.txt"
catType="M"
proxy = ""
proxies = {
    "http": proxy,
    "https": proxy
}
# proxy = "5.79.73.131:13010"
# proxies = {
#     "http": "http://5.79.73.131:13010",
#     "https": "http://5.79.73.131:13010"
# }
HEADERS ={
    "User-Agent": "Mozilla/5.0",
    # "Connection": "close"  # Important for rotating IPs with StormProxies
}

def fetch_html(url):
    response = requests.get(url, headers=HEADERS, proxies=proxies, timeout=50)
    response.raise_for_status()
    return response.text

def process_item(item_no):
    max_retries = 10
    attempt = 0
    while attempt < max_retries:
        attempt += 1
        try:
            url = f"https://www.bricklink.com/v2/catalog/catalogitem.page?{catType}={item_no}"
            html = fetch_html(url)

            soup = BeautifulSoup(html, 'html.parser')
            id_item = None
            for script in soup.find_all("script"):
                if script.string and "_var_item" in script.string:
                    match = re.search(r'idItem\s*:\s*(\d+)', script.string)
                    if match:
                        id_item = match.group(1)
                    break

            table_html = None
            if id_item:
                table_url = f"https://www.bricklink.com/v2/catalog/catalogitem_pgtab.page?idItem={id_item}&st=2&gm=1&gc=0&ei=0&prec=2&showflag=0&showbulk=0&currency=1"
                table_html = fetch_html(table_url)

            TABLE.insert({
                "item_no": item_no,
                "main_response": html,
                "table_response": table_html
            })
            print(f"✅ Stored item: {item_no}")
            break
        except Exception as e:
            print(f"❌ Error processing {item_no}: {e}")

def main():
    with open(inputtext) as f:
        item_nos = [line.strip() for line in f if line.strip()]

    processes = []
    with alive_bar(len(item_nos)) as bar:
        with ThreadPoolExecutor(max_workers=20) as executor:
            for item_no in item_nos:
                processes.append(executor.submit(process_item, item_no))

            for task in as_completed(processes):
                bar()

if __name__ == "__main__":
    main()
