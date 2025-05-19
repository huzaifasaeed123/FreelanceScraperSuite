#This Code will update Two things in database that we not do before
# 1)Download and save Image
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
TABLE = DB["set"]
inputtext = "Setitems.txt"
catType = "S"
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
            row = TABLE.find_one(item_no=item_no)
            if not row:
                print(f"⚠️ Item not found in DB, skipping: {item_no}")
                return

            update_data = {"item_no": item_no}

            # Ensure both fields are updated before breaking
            need_image = not row.get("image_path")
            need_consist = not row.get("consist_of_response")

            # Get main HTML from DB
            html = row.get("main_response")
            if html and need_image:
                soup = BeautifulSoup(html, 'html.parser')
                for script in soup.find_all("script"):
                    if script.string and "_var_item" in script.string:
                        match = re.search(r"var\s+_var_item\s*=\s*(\{.+?\})\s*;", script.string, re.DOTALL)
                        if match:
                            var_item_str = match.group(1)
                            var_item_data = demjson3.decode(var_item_str)
                            image_url = var_item_data.get("strMainLImgUrl")
                            if image_url:
                                referer = f"https://www.bricklink.com/v2/catalog/catalogitem.page?{catType}={item_no}"
                                image_path = download_image(image_url, item_no, referer)
                                update_data["image_path"] = image_path
                        break

            if need_consist:
                consist_url = f"https://www.bricklink.com/catalogItemInv.asp?S={item_no}"
                consist_html = fetch_html(consist_url)
                update_data["consist_of_response"] = consist_html

            if (need_image and not update_data.get("image_path")) or (need_consist and not update_data.get("consist_of_response")):
                raise Exception("Retrying due to partial failure.")

            TABLE.update(update_data, ["item_no"])
            print(f"✅ Updated item: {item_no}")
            break

        except Exception as e:
            print(f"❌ Error processing {item_no} (attempt {attempt}): {e}")
            # time.sleep(5)

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
