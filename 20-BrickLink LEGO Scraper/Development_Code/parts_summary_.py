# parser.py
import os
import re
import json
import pandas as pd
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, parse_qs
from multiprocessing import Pool, cpu_count
from tqdm import tqdm
import time
import demjson3
import requests

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    # "Connection": "close"
}

def fetch_html(url):
    response = requests.get(url, headers=HEADERS,timeout=50)
    response.raise_for_status()
    return response.text

def parse_color_summary_table(soup, item_number=None):
    results = []
    
    # Find the summary table using the same approach as extract_summary_table
    summary_element = soup.find(string=lambda text: text and "Summary:" in text)
    if not summary_element:
        return results
    
    # Find the closest table
    parent = summary_element.parent
    if not parent:
        return results
    
    table = parent.find("table") or parent.find_next("table")
    if not table:
        return results
    
    # Process the rows for color data
    current_section = None
    
    for row in table.find_all("tr"):
        # Skip header row (purple background)
        if row.get("bgcolor") == "#5E5A80":
            continue
        
        # Check if this is a category row (black background)
        if row.get("bgcolor") == "#000000":
            section_text = row.get_text(strip=True)
            
            # # Handle all possible section types
            # if "Appears As Regular" in section_text:
            #     current_section = "Regular"
            # elif "Appears As Extra" in section_text:
            #     current_section = "Extra"
            # elif "Appears As Counterpart" in section_text:
            #     current_section = "Counterpart"
            # elif "Appears As Alternate" in section_text:
            #     current_section = "Alternate"
            # else:
                # Extract section name if it follows "Appears As X:" pattern
            match = re.search(r"Appears As ([^:]+):", section_text)
            if match:
                current_section = match.group(1)
            continue
        
        # Process data rows
        if current_section:
            cells = row.find_all("td")
            
            # Handle rows with different cell structures
            try:
                # For rows with the specific structure with nested tables
                if len(cells) >= 6:
                    # Extract color from the 4th cell
                    color = cells[3].get_text(strip=True) if cells[3] else ""
                    
                    # Extract in_sets from the 5th cell
                    in_sets = cells[4].get_text(strip=True) if cells[4] else ""
                    
                    # Extract total_qty from the 6th cell
                    total_qty = cells[5].get_text(strip=True) if cells[5] else ""
                else:
                    continue
                # Clean up values
                color = color.strip()
                in_sets = ''.join(c for c in in_sets if c.isdigit())
                total_qty = ''.join(c for c in total_qty if c.isdigit())
                
                # Skip rows with no meaningful data
                if not color or color == "Color":
                    continue
                
                # Add to results
                results.append({
                    "item_number": item_number,
                     "appears_as": current_section,
                    "color": color,
                    "in_sets": int(in_sets) if in_sets.isdigit() else in_sets,
                    "total_qty": int(total_qty) if total_qty.isdigit() else total_qty
                })
            except Exception as e:
                print(f"Error parsing color row: {e}")
    
    return results


def test_parse_color_summary(html_content):

    soup = BeautifulSoup(html_content, "html.parser")
    # print(soup)
    color_data = parse_color_summary_table(soup)
    
    # Print the results for verification
    print(f"Found {len(color_data)} color entries:")
    if not color_data:
        print("No color data found. Examining HTML structure...")
        
        # Look for summary tables
        tables = soup.find_all('table')
        print(f"Found {len(tables)} tables in the HTML")
        
        # Check for tables with certain characteristics
        for i, table in enumerate(tables):
            headers = table.find_all('th')
            print(f"Table {i+1} has {len(headers)} headers")
            if headers:
                print(f"Headers: {[h.get_text(strip=True) for h in headers]}")
    else:
        for item in color_data:
            print(f"Item: {item['item_number']}, Appears As: {item['appears_as']}, "
                  f"Color: {item['color']}, Sets: {item['in_sets']}, Qty: {item['total_qty']}")
    
    return color_data
def parts_parser(html,image_path,item_no):
    soup = BeautifulSoup(html, 'html.parser')
    data = {
        "item_number": item_no,
        "item_name": None,
        "item_id": None,
        "category": None,
        "year_released": None,
        "weight": None,
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
            # Year Released - handle both single year and year ranges
            year_match = re.search(r"Years? Released:\s*(\d{4})(?:\s*-\s*(\d{4}))?", text)
            if year_match:
                if year_match.group(2):  # If there's a range
                    data["year_released"] = f"{year_match.group(1)} - {year_match.group(2)}"
                else:
                    data["year_released"] = year_match.group(1)
                
                # Remove question marks
                data["year_released"] = data["year_released"].replace("?", "")

            # Weight
            weight_match = re.search(r"Weight:\s*([^\s<]+)", text)
            if weight_match:
                data["weight"] = weight_match.group(1).strip().replace("?", "")

            # Item Dimensions
            dim_match = re.search(r"Item Dim\.:\s*([\d.x\s]+(?:cm|in studs))", text)
            if dim_match:
                data["dimensions"] = dim_match.group(1).strip().replace("?", "")

            # Stud Dimensions
            stud_dim_match = re.search(r"Stud Dim\.:\s*((?:\d+(?:\.\d+)?\s*x\s*)*\d+(?:\.\d+)?\s*(?:in studs|cm)|[?])", text)
            if stud_dim_match:
                data["stud_dimensions"] = stud_dim_match.group(1).strip().replace("?", "")

            # Pack Dimensions
            pack_dim_match = re.search(r"Pack\. Dim\.:\s*((?:\d+(?:\.\d+)?\s*x\s*)*\d+(?:\.\d+)?\s*(?:in studs|cm)(?:\s*\([VH]\))?|\?)", text)
            if pack_dim_match:
                data["pack_dimensions"] = pack_dim_match.group(1).strip().replace("?", "")

            # Instructions
            instr_match = re.search(r"Instructions:\s*(Yes|No|\?)", text)
            if instr_match:
                data["instructions"] = instr_match.group(1).strip().replace("?", "")
        if "Related Items:" in text:
            all_li=td.find_all("li")
            relatedItem=[]
            for li in all_li:
                result =get_id_from_url(li.find("a").get('href'))
                relatedItem.append(result["item_no"])
            data["related_items"]=relatedItem

    for script in soup.find_all("script"):
        if script.string and "_var_item" in script.string:
            match = re.search(r"var\s+_var_item\s*=\s*(\{.+?\})\s*;", script.string, re.DOTALL)
            if match:
                var_item_str = match.group(1)
                var_item_data = demjson3.decode(var_item_str)
                data["item_id"] = var_item_data.get("idItem")
                data["image_url"] = var_item_data.get("strMainLImgUrl")
            break
    # print(data)
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
def main():
    url = "https://www.bricklink.com/v2/catalog/catalogitem.page?P=52054pb01#T=P&C=5"  # Using the item from your images
    html = fetch_html(url)
    parts_parser(html,"image_path","item_no")
    # test_parse_color_summary(html)



if __name__ == "__main__":
    main()