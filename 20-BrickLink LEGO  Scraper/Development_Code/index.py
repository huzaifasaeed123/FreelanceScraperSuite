import os
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import pandas as pd
import json
import demjson3
from urllib.parse import urlparse, parse_qs
from multiprocessing import Pool, cpu_count

def fetch_html(url):
    headers = {
        "User-Agent": "Mozilla/5.0"
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.text

def sets_parser(html, base_url=None):
    soup = BeautifulSoup(html, 'html.parser')
    data = {
        "item_number": None,
        "item_name": None,
        "category": None,
        "year_released": None,
        "weight": None,
        "dimensions": None,
        "instructions": None,
        "parts_count": None,
        "parts_url": None,
        "minifigs_count": None,
        "minifigs_url": None,
        "appears_in": None,
        "image_url": None,
        "image_path": None,
    }

    h1 = soup.find("h1", id="item-name-title")
    if h1:
        data["item_name"] = h1.text.strip()

    for td in soup.find_all("td"):
        text = td.get_text(" ", strip=True)

        if "Catalog" in text:
            parts = text.split(":")
            parts = [p.strip() for p in parts if p.strip() and p.strip() != "Catalog"]
            if parts:
                data["item_number"] = parts[-1]
                data["category"] = " > ".join(parts[:-1])

        if "Item Info" in text:
            if "Year Released:" in text:
                data["year_released"] = int(re.search(r"Year Released:\s*(\d+)", text).group(1))
            if "Weight:" in text:
                data["weight"] = re.search(r"Weight:\s*([\d.]+\s*g)", text).group(1)
            if "Item Dim.:" in text:
                pass
                data["dimensions"] = re.search(r"Item Dim.:\s*([\d.]+\s*x\s*[\d.]+\s*x\s*[\d.]+\s*cm)", text).group(1)
            if "Instructions:" in text:
                instr = re.search(r"Instructions:\s*(Yes|No)", text).group(1)
                data["instructions"] = instr

        if "Item Consists Of" in text:
            links = td.find_all("a", href=True)
            for a in links:
                if "Parts" in a.text:
                    data["parts_url"] = urljoin(base_url, a['href'])
                    data["parts_count"] = int(re.search(r"(\d+)", a.text).group(1))
                if "Minifigure" in a.text:
                    data["minifigs_url"] = urljoin(base_url, a['href'])
                    data["minifigs_count"] = int(re.search(r"(\d+)", a.text).group(1))

        if "Item Appears In" in text:
            a = td.find("a", href=True)
            if a:
                data["appears_in"] = urljoin(base_url, a['href'])
            else:
                data["appears_in"] = text.split(":")[-1].strip().replace("Item Appears In","")

    # Extract var_item object from JavaScript
    scripts = soup.find_all("script")
    for script in scripts:
        if script.string and '_var_item' in script.string:
            # print("Matched")
            # Find the var_item object
            var_item_match = re.search(r"var\s+_var_item\s*=\s*(\{.+?\})\s*;", script.string, re.DOTALL)
            # print(var_item_match)
            if var_item_match:
                var_item_str = var_item_match.group(1)
                
                # Convert JavaScript object to valid JSON
                var_item_str = re.sub(r'(\w+):', r'"\1":', var_item_str)
                var_item_str = var_item_str.replace("'", '"')
                
                try:
                    var_item_data = json.loads(var_item_str)
                    # print("hi")
                    # Add all var_item properties to data dictionary
                    data["id_item"] = var_item_data.get("idItem")
                    data["item_type"] = var_item_data.get("type")
                    data["item_type_name"] = var_item_data.get("typeName")
                    data["item_status"] = var_item_data.get("itemStatus")
                    
                    # Store all image URLs
                    # for key, value in var_item_data.items():
                    #     if key.startswith("str") and "Img" in key:
                    #         img_url = value
                    #         if img_url.startswith("//"):
                    #             img_url = "https:" + img_url
                    #         data[key] = img_url
                    
                    # Use main large image for download
                    if "strMainLImgUrl" in var_item_data:
                        img_url = var_item_data["strMainLImgUrl"]
                        if img_url.startswith("//"):
                            img_url = "https:" + img_url
                        data["image_url"] = img_url
                        
                        # Download image
                        item_no = data["item_number"] or "image"
                        ext = os.path.splitext(img_url)[1] or ".png"
                        filename = f"{item_no}{ext}"
                        img_path = os.path.join("Images", filename)
                        os.makedirs("Images", exist_ok=True)
                        
                        if not os.path.exists(img_path):
                            headers = {
                                "User-Agent": "Mozilla/5.0",
                                "Referer": base_url
                            }
                            img_data = requests.get(img_url, stream=True, headers=headers)
                            with open(img_path, "wb") as f:
                                for chunk in img_data.iter_content(1024):
                                    f.write(chunk)
                        data["image_path"] = img_path
                    
                    # Store complete var_item object
                    # data["var_item"] = var_item_data
                    break
                except json.JSONDecodeError as e:
                    print(f"Error parsing var_item JSON: {e}")
                    print(f"var_item string: {var_item_str}")

    table_url=f"https://www.bricklink.com/v2/catalog/catalogitem_pgtab.page?idItem={data['id_item']}&st=2&gm=1&gc=0&ei=0&prec=2&showflag=0&showbulk=0&currency=1"
    html = fetch_html(table_url)
    table_soup=BeautifulSoup(html, 'html.parser')
    tables = table_soup.find_all("table", class_="pcipgSummaryTable")
    labels = ["sales_6mo_new", "sales_6mo_used", "sales_now_new", "sales_now_used"]
    print(f"Found {len(tables)} summary tables")
    for idx, table in enumerate(tables):
        print(f"Processing table {idx+1}")
        rows = table.find_all("tr")
        if idx < len(labels):
            prefix = labels[idx]
            for row in rows:
                cells = row.find_all("td")
                if len(cells) == 2:
                    label = cells[0].get_text(strip=True).replace(":", "").lower().replace(" ", "")
                    value = cells[1].get_text(strip=True)
                    key = f"{prefix}_{label}"
                    data[key] = value.replace("US $","").replace("-","")

    return data
def get_id_from_url(url):
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    item_no = ""
    cat_type = ""
    # Determine which parameter is present (S, M, or P)
    for key in ["S", "M", "P"]:
        if key in query:
            item_no = query[key][0]
            cat_type = key
            break
    return {
        "item_no": item_no,
        "cat_type": cat_type
    }

def sets_parser2(html,image_path,item_no):
    soup = BeautifulSoup(html, 'html.parser')
    data = {
        "item_number": item_no,
        "item_name": None,
        "item_id": None,
        "category": None,
        "year_released": None,
        "weight": None,
        "dimensions": None,
        "instructions": None,
        # "parts_count": None,
        # "parts_url": None,
        # "minifigs_count": None,
        # "minifigs_url": None,
        # "appears_in": None,
        "related_items": None,
        "image_url": None,
        "image_path": image_path,
    }
    h1 = soup.find("h1", id="item-name-title")
    if h1:
        data["item_name"] = h1.text.strip()
    
    for td in soup.find_all("td"):
        text = td.get_text(" ", strip=True)

        if "Catalog" in text:
            parts = text.split(":")
            parts = [p.strip() for p in parts if p.strip() and p.strip() != "Catalog"]
            if parts:
                # data["item_number"] = parts[-1]
                data["category"] = " > ".join(parts[:-1])

        if "Item Info" in text:
            year_match = re.search(r"Year Released:\s*(\d{4})", text)
            if year_match:
                data["year_released"] = year_match.group(1).strip().replace("?","")

            weight_match = re.search(r"Weight:\s*([^\s<]+)", text)
            if weight_match:
                data["weight"] = weight_match.group(1).strip().replace("?","")

            dim_match = re.search(r"Item Dim.:\s*([\d.x\s]+cm)", text)
            if dim_match:
                data["dimensions"] = dim_match.group(1).strip().replace("?","")

            instr_match = re.search(r"Instructions:\s*(Yes|No|\?)", text)
            if instr_match:
                data["instructions"] = instr_match.group(1).strip().replace("?","")
        if "Related Items:" in text:
            all_li=td.find_all("li")
            relatedItem=[]
            for li in all_li:
                result =get_id_from_url(li.find("a").get('href'))
                relatedItem.append(result["item_no"])
            data["related_items"]=relatedItem
        # if "Item Consists Of" in text:
        #     links = td.find_all("a", href=True)
        #     for a in links:
        #         if "Parts" in a.text:
        #             data["parts_url"] = urljoin(base_url, a['href'])
        #             data["parts_count"] = int(re.search(r"(\\d+)", a.text).group(1))
        #         if "Minifigure" in a.text:
        #             data["minifigs_url"] = urljoin(base_url, a['href'])
        #             data["minifigs_count"] = int(re.search(r"(\\d+)", a.text).group(1))

        # if "Item Appears In" in text:
        #     a = td.find("a", href=True)
        #     if a:
        #         data["appears_in"] = urljoin(base_url, a['href'])
        #     else:
        #         data["appears_in"] = text.split(":")[-1].strip().replace("Item Appears In","")

    for script in soup.find_all("script"):
        if script.string and "_var_item" in script.string:
            match = re.search(r"var\s+_var_item\s*=\s*(\{.+?\})\s*;", script.string, re.DOTALL)
            if match:
                var_item_str = match.group(1)
                var_item_data = demjson3.decode(var_item_str)
                data["item_id"] = var_item_data.get("idItem")
                data["image_url"] = var_item_data.get("strMainLImgUrl")
            break
    return data
def parse_price_tables(html):
    soup = BeautifulSoup(html, 'html.parser')
    data = {}
    tables = soup.find_all("table", class_="pcipgSummaryTable")
    labels = ["sales_6mo_new", "sales_6mo_used", "sales_now_new", "sales_now_used"]

    for idx, table in enumerate(tables):
        rows = table.find_all("tr")
        if idx < len(labels):
            prefix = labels[idx]
            for row in rows:
                cells = row.find_all("td")
                if len(cells) == 2:
                    label = cells[0].get_text(strip=True).replace(":", "").lower().replace(" ", "")
                    value = cells[1].get_text(strip=True).replace("US $", "").replace("-", "")
                    key = f"{prefix}_{label}"
                    data[key] = value
    return data

def export_to_excel(data_list, filename="bricklink_sets12.xlsx"):
    df = pd.DataFrame(data_list)
    df.to_excel(filename, index=False)

if __name__ == '__main__':
    url = "https://www.bricklink.com/v2/catalog/catalogitem_pgtab.page?idItem=940&idColor=11&st=2&gm=1&gc=0&ei=0&prec=2&showflag=0&showbulk=0&currency=1"
    html = fetch_html(url)
    with open("index1.html", 'w', encoding='utf-8') as file:
        file.write(html)
    result = parse_price_tables(html)
    # result = sets_parser(html)
    export_to_excel([result])
    print("Data exported successfully.")