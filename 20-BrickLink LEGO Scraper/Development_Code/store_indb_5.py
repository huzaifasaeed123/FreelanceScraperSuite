#This Code will update One things in database that we not do before
# 2)Save Content for consist_of Response
import os
import re
import json
import requests
import dataset
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from concurrent.futures import ThreadPoolExecutor, as_completed
from alive_progress import alive_bar
import time
import demjson3

# Setup dataset connection
DB = dataset.connect("sqlite:///bricklink_data.db")
TABLE = DB["minifigures"]
inputtext = "Minifigureitems.txt"
catType = "M"
proxy = ""
proxies = {
    "http": proxy,
    "https": proxy
}
HEADERS = {
    "User-Agent": "Mozilla/5.0",
    # "Connection": "close"
}

def fetch_html(url):
    response = requests.get(url, headers=HEADERS, proxies=proxies, timeout=50)
    response.raise_for_status()
    return response.text

def process_item(item_no):
    max_retries = 3
    attempt = 0
    while attempt < max_retries:
        attempt += 1
        try:
            row = TABLE.find_one(item_no=item_no)
            if not row:
                print(f"⚠️ Item not found in DB, skipping: {item_no}")
                return

            consist_url = f"https://www.bricklink.com/catalogItemInv.asp?{catType}={item_no}"
            consist_html = fetch_html(consist_url)

            if not consist_html:
                raise Exception("Failed to fetch consist_of_response.")

            # Only update consist_of_response field
            TABLE.update({
                "item_no": item_no,
                "consist_of_response": consist_html
            }, ["item_no"])

            print(f"✅ Updated consist_of_response for item: {item_no}")
            break

        except Exception as e:
            print(f"❌ Error processing {item_no} (attempt {attempt}): {e}")

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
