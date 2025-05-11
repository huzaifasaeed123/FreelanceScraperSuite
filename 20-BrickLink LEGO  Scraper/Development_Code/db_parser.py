import os
import re
import json
import dataset
import pandas as pd
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import demjson3
from urllib.parse import urlparse, parse_qs
from multiprocessing import Pool, cpu_count
from tqdm import tqdm
import time


#Below All Function is for Consist Of parser
def separate_by_cat_type(items):
    parts = []
    minifigs = []
    sets = []

    for entry in items:
        cat = entry.get("cat_type")
        item_no = entry.get("item_no")
        if cat == "P":
            parts.append(item_no)
        elif cat == "M":
            minifigs.append(item_no)
        elif cat == "S":
            sets.append(item_no)

    return parts, minifigs, sets

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

def extract_summary_table(soup):
    """
    Extracts the summary table values with custom key format in the exact sequence.
    Format: Unique_SectionWord_ItemType, Total_SectionWord_ItemType
    Example: Unique_Regular_Parts, Total_Regular_Parts, Unique_Regular_Minifigures, etc.
    """
    result = {
    # Regular Items section
    "Unique_Regular_Parts": "",          
    "Total_Regular_Parts": "",          
    "Unique_Regular_Minifigures": "",      # Empty string (not in table)
    "Total_Regular_Minifigures": "",       # Empty string (not in table)
    
    # Extra Items section
    "Unique_Extra_Parts": "",              # Empty string (not in table)
    "Total_Extra_Parts": "",               # Empty string (not in table)
    "Unique_Extra_Minifigures": "",        # Empty string (not in table)
    "Total_Extra_Minifigures": "",         # Empty string (not in table)
    
    # Counterparts section
    "Unique_Counterparts_Parts": "",       # Empty string (not in table)
    "Total_Counterparts_Parts": "",        # Empty string (not in table)
    "Unique_Counterparts_Minifigures": "", # Empty string (not in table)
    "Total_Counterparts_Minifigures": "",  # Empty string (not in table)
    
    # New Items section
    "Unique_New_Parts": "",                # Empty string (not in table)
    "Total_New_Parts": "",                 # Empty string (not in table)
    "Unique_New_Minifigures": "",          # Empty string (not in table)
    "Total_New_Minifigures": "",           # Empty string (not in table)
    
    # Alternate Items section
    "Unique_Alternate_Parts": "",          # Empty string (not in table)
    "Total_Alternate_Parts": "",           # Empty string (not in table)
    "Unique_Alternate_Minifigures": "",    # Empty string (not in table)
    "Total_Alternate_Minifigures": ""      # Empty string (not in table)
}
    
    # Find the summary text
    summary_element = soup.find(string=lambda text: text and "Summary:" in text)
    if not summary_element:
        return result
    
    # Find the closest table
    parent = summary_element.parent
    if not parent:
        return result
    
    table = parent.find("table") or parent.find_next("table")
    if not table:
        return result
    
    # Define sections and their shorthand names
    section_mapping = {
        "Regular Items": "Regular",
        "Extra Items": "Extra", 
        "Counterparts": "Counterparts",
        "New Items": "New",
        "Alternate Items": "Alternate"
    }
    
    # Store data in the order it appears in the table
    data = []
    current_section = None
    # First pass: collect all data in sequence
    for tr in table.find_all("tr"):
        # Skip header row
        if tr.get("bgcolor") == "#5E5A80":
            continue
        
        # Check for section header
        if tr.get("bgcolor") == "#000000":
            section_text = tr.get_text(strip=True).replace(":", "")
            # Map to shorthand name
            if section_text in section_mapping:
                current_section = section_mapping[section_text]
            else:
                current_section = section_text.split()[0]
            continue
        
        # Process data rows
        cells = tr.find_all("td")
        if current_section and len(cells) >= 3:
            item_type = cells[0].get_text(strip=True)
            unique_lots = cells[1].get_text(strip=True)
            total_qty = cells[2].get_text(strip=True)
            
            # Store in sequence
            data.append({
                "section": current_section,
                "type": item_type,
                "unique": unique_lots,
                "total": total_qty
            })
    
    # Second pass: create the dictionary with custom keys in sequence
    for item in data:
        # Create keys using your format
        unique_key = f"Unique_{item['section']}_{item['type']}"
        total_key = f"Total_{item['section']}_{item['type']}"
        
        # Add to result dictionary
        result[unique_key] = item['unique']
        result[total_key] = item['total']
    
    return result
# Main Function for capturing Relation And Connections
def parse_consist_of(html):

    soup = BeautifulSoup(html, "html.parser")
    links = []

    for tr in soup.find_all("tr", class_="IV_ITEM"):
        td = tr.find("td", attrs={"nowrap": True})
        if td:
            a_tag = td.find("a", href=True)
            if a_tag:
                links.append(get_id_from_url(a_tag.get("href")))
                
    summary = extract_summary_table(soup)
    parts, minifigs, sets=separate_by_cat_type(links)
    obj={
        "parts_relation":parts,
        "minifigs_relation":minifigs,
        "sets_relation":sets
    }
    obj.update(summary)
    return obj

# -- Existing sets_parser from index.py --
def sets_parser(html,image_path,item_no):
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

# -- New parser for 'consist_of_response' page --

# -- New parser for 'table_response' page (sales summary) --



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

# -- Read and parse all stored data --

def get_records_in_batches(table, batch_size=1000):
    """Fetch records in batches to optimize memory usage."""
    offset = 0
    while True:
        records = list(table.find(_limit=batch_size, _offset=offset))
        if not records:
            break
        yield records
        offset += batch_size
def process_row(row):
    try:
        item_no = row["item_no"]

        if len(row["table_response"].encode("utf-8")) > 10 * 1024 * 1024:
            return None
        if not row.get("main_response") or not row.get("table_response"):
            return None
        main_data = sets_parser(row["main_response"], row['image_path'], row["item_no"])
        price_data = parse_price_tables(row["table_response"])
        # consist_data = parse_consist_of(row["consist_of_response"])

        main_data.update(price_data)
        
        # Convert all lists to strings to make DB-safe
        for key in main_data:
            if isinstance(main_data[key], list):
                main_data[key] = ", ".join(map(str, main_data[key]))

        return main_data
    except Exception as e:
        print(f"❌ Failed to parse {row['item_no']}: {e}")
        return None
# Main function with multiprocessing
def scrape_bricklink_data(batch_size=1000):
    db = dataset.connect("sqlite:///bricklink_data_part_1.db")
    table_set = db["part"]
    db_parse = dataset.connect("sqlite:///bricklink_parse.db")
    table_parse = db_parse["part_parse"]

    all_results = []
    num_workers = max(cpu_count() - 1, 2)
    full_start_time = time.perf_counter()
    for batch in get_records_in_batches(table_set, batch_size):
        batch_start_time = time.perf_counter()

        with Pool(processes=num_workers) as pool:
            results = pool.map(process_row, batch)

        results = [r for r in results if r is not None]
        if results:
            table_parse.insert_many(results)
            all_results.extend(results)

        batch_end_time = time.perf_counter()
        print(f"⏳ Batch Processed in {batch_end_time - batch_start_time:.2f} sec with {num_workers} CPUs")

    full_end_time = time.perf_counter()
    print(f"🚀 Total Execution Time: {full_end_time - full_start_time:.2f} sec")
    return all_results

if __name__ == "__main__":
    batch_size = 1000
    parsed_data = scrape_bricklink_data(batch_size)
    df = pd.DataFrame(parsed_data)
    df.to_excel("parsed_bricklink_data.xlsx", index=False)
    print("✅ Data exported to Excel")