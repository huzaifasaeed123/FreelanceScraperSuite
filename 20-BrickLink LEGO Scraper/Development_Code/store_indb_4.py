#Complete code which store Main Page Content,Table Content,Appear in Content And Download Image
# This Code is For Parts
# The main changing is just AppearIn Page instead of consist page,Just change API EndPOint
import os
import re
import json
import requests
import dataset
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from concurrent.futures import ThreadPoolExecutor, as_completed
from alive_progress import alive_bar
import demjson3
# Setup dataset connection

DB = dataset.connect("sqlite:///bricklink_data2.db")
TABLE = DB["part"]
inputtext = "Partsitems.txt"
catType = "P"
proxy = ""
proxies = {
    "http": proxy,
    "https": proxy
}
HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Connection": "close"
}

def fetch_html(url):
    response = requests.get(url, headers=HEADERS, proxies=proxies, timeout=50)
    response.raise_for_status()
    return response.text

def download_image(img_url, item_no, referer):
    if img_url.startswith("//"):
        img_url = "https:" + img_url
    ext = os.path.splitext(img_url)[1] or ".png"
    filename = f"{item_no}{ext}"
    img_path = os.path.join("Images", filename)
    os.makedirs("Images", exist_ok=True)

    if not os.path.exists(img_path):
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Referer": referer
        }
        img_data = requests.get(img_url, stream=True, headers=headers, proxies=proxies, timeout=30)
        img_data.raise_for_status()
        with open(img_path, "wb") as f:
            for chunk in img_data.iter_content(1024):
                f.write(chunk)
    return img_path

def process_item(item_no):
    max_retries = 3
    attempt = 0
    while attempt < max_retries:
        attempt += 1
        try:
            url = f"https://www.bricklink.com/v2/catalog/catalogitem.page?{catType}={item_no}"
            html = fetch_html(url)

            soup = BeautifulSoup(html, 'html.parser')
            id_item = None
            image_url = None
            image_path = None
            for script in soup.find_all("script"):
                if script.string and "_var_item" in script.string:
                    match = re.search(r"var\s+_var_item\s*=\s*(\{.+?\})\s*;", script.string, re.DOTALL)
                    if match:
                        var_item_str = match.group(1)
                        var_item_data = demjson3.decode(var_item_str)
                        id_item = var_item_data.get("idItem")
                        image_url = var_item_data.get("strMainLImgUrl")
                        if image_url:
                            image_path = download_image(image_url, item_no, url)
                    break

            table_html = None
            if id_item:
                table_url = f"https://www.bricklink.com/v2/catalog/catalogitem_pgtab.page?idItem={id_item}&st=2&gm=1&gc=0&ei=0&prec=2&showflag=0&showbulk=0&currency=1"
                table_html = fetch_html(table_url)

            consist_of_url = f"https://www.bricklink.com/catalogItemIn.asp?{catType}={item_no}"
            consist_of_html = fetch_html(consist_of_url)

            TABLE.insert({
                "item_no": item_no,
                "main_response": html,
                "table_response": table_html,
                "consist_of_response": consist_of_html,
                "image_path": image_path
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
