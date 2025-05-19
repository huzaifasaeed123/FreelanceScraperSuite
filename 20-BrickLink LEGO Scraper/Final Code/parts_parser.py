# parts_parser.py
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
import dataset
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("parts_parser.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def separate_by_cat_type(items):
    """Separate items by their category type."""
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
    """Extract item number and category type from a URL."""
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

def parse_color_summary_table(soup, item_number=None):
    """Parse the color summary table from the soup object."""
    results = []
    
    # Find the summary table
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
            match = re.search(r"Appears As ([^:]+):", section_text)
            if match:
                current_section = match.group(1)
            continue
        
        # Process data rows
        if current_section:
            cells = row.find_all("td")
            
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
                    "in_sets": int(in_sets) if in_sets.isdigit() else 0,
                    "total_qty": int(total_qty) if total_qty.isdigit() else 0
                })
            except Exception as e:
                logger.error(f"Error parsing color row: {e}")
    
    return results

def parts_parser(html, image_path, item_no):
    """Parse the main part data from HTML."""
    soup = BeautifulSoup(html, 'html.parser')
    data = {
        "item_number": item_no,
        "item_name": None,
        "item_id": None,
        "category": None,
        "year_released": None,
        "weight": None,
        "dimensions": None,
        "stud_dimensions": None,
        "pack_dimensions": None,
        "instructions": None,
        "related_items": None,
        "image_url": None,
        "image_path": image_path,
    }
    
    # Extract item name
    h1 = soup.find("h1", id="item-name-title")
    if h1:
        data["item_name"] = h1.text.strip()
    
    # Extract various metadata
    for td in soup.find_all("td"):
        text = td.get_text(" ", strip=True)

        if "Catalog" in text:
            parts = text.split(":")
            parts = [p.strip() for p in parts if p.strip() and p.strip() != "Catalog"]
            if parts:
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
                
        # Extract related items
        if "Related Items:" in text:
            all_li = td.find_all("li")
            relatedItem = []
            for li in all_li:
                a_tag = li.find("a")
                if a_tag and a_tag.has_attr('href'):
                    result = get_id_from_url(a_tag.get('href'))
                    relatedItem.append(result["item_no"])
            data["related_items"] = relatedItem

    # Extract item ID and image URL from JavaScript variable
    for script in soup.find_all("script"):
        if script.string and "_var_item" in script.string:
            match = re.search(r"var\s+_var_item\s*=\s*(\{.+?\})\s*;", script.string, re.DOTALL)
            if match:
                var_item_str = match.group(1)
                try:
                    var_item_data = demjson3.decode(var_item_str)
                    data["item_id"] = var_item_data.get("idItem")
                    data["image_url"] = var_item_data.get("strMainLImgUrl")
                except Exception as e:
                    logger.error(f"Error parsing _var_item: {e}")
            break
            
    return data

def parse_price_tables(html):
    """Parse price tables from HTML."""
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

def get_records_in_batches(table, batch_size=1000):
    """Fetch records in batches to optimize memory usage."""
    offset = 0
    while True:
        records = list(table.find(_limit=batch_size, _offset=offset))
        if not records:
            break
        yield records
        offset += batch_size

def process_row(args):
    """Process a single row with color summary parsing in a separate structure."""
    row, _ = args
    try:
        item_no = row["item_no"]
        
        # Check for large responses and missing data
        if len(row["table_response"].encode("utf-8")) > 10 * 1024 * 1024:
            logger.warning(f"Skipping {item_no}: Table response too large")
            return None, None
            
        if not row.get("main_response") or not row.get("table_response"):
            logger.warning(f"Skipping {item_no}: Missing required responses")
            return None, None
        
        # Parse main part data
        main_data = parts_parser(row["main_response"], row.get('image_path', ''), row["item_no"])
        
        # Parse price data
        price_data = parse_price_tables(row["table_response"])
        main_data.update(price_data)
        
        # Parse color summary data (to be stored in a separate table)
        color_data = []
        if row.get("consist_of_response"):
            soup = BeautifulSoup(row["consist_of_response"], 'html.parser')
            color_data = parse_color_summary_table(soup, item_no)
        
        # Convert all lists to strings to make DB-safe
        for key in main_data:
            if isinstance(main_data[key], list):
                main_data[key] = ", ".join(map(str, main_data[key]))

        return main_data, color_data
    except Exception as e:
        logger.error(f"❌ Failed to parse {row.get('item_no', 'unknown')}: {e}")
        return None, None

def parse_all_parts_data(raw_table, parsed_table, color_table, batch_size=1000, output_excel=None):
    """Main function to parse all data from raw table to parsed table and color table."""
    all_results = []
    all_color_results = []
    num_workers = max(cpu_count() - 1, 2)
    full_start_time = time.perf_counter()
    
    # Get total count for progress reporting
    total_count = raw_table.count()
    processed_count = 0
    
    logger.info(f"Starting to process {total_count} parts")
    
    for batch in get_records_in_batches(raw_table, batch_size):
        batch_start_time = time.perf_counter()
        
        # Create args (is_parts is always True for this script)
        batch_args = [(row, True) for row in batch]
        
        with Pool(processes=num_workers) as pool:
            results = list(tqdm(
                pool.imap(process_row, batch_args),
                total=len(batch_args),
                desc=f"Processing batch {processed_count+1}-{processed_count+len(batch_args)}/{total_count}"
            ))
        
        # Filter out None results and separate main and color data
        main_results = []
        color_results = []
        
        for main_result, color_result in results:
            if main_result:
                main_results.append(main_result)
            if color_result:
                color_results.extend(color_result)
        
        # Insert data into respective tables
        if main_results:
            parsed_table.insert_many(main_results)
            all_results.extend(main_results)
            
        if color_results:
            color_table.insert_many(color_results)
            all_color_results.extend(color_results)

        processed_count += len(batch_args)
        batch_end_time = time.perf_counter()
        logger.info(f"⏳ Batch processed in {batch_end_time - batch_start_time:.2f} sec with {num_workers} CPUs")
        logger.info(f"   Added {len(main_results)} parts and {len(color_results)} color entries")

    full_end_time = time.perf_counter()
    logger.info(f"🚀 Total execution time: {full_end_time - full_start_time:.2f} sec")
    logger.info(f"📊 Processed {len(all_results)} parts with {len(all_color_results)} color entries")
    
    # Export to Excel if path provided
    if output_excel and all_results:
        df = pd.DataFrame(all_results)
        df.to_excel(output_excel, index=False)
        
        # Also export color data
        if all_color_results:
            color_df = pd.DataFrame(all_color_results)
            color_excel = output_excel.replace('.xlsx', '_colors.xlsx')
            color_df.to_excel(color_excel, index=False)
            logger.info(f"✅ Color data exported to {color_excel}")
            
        logger.info(f"✅ Part data exported to {output_excel}")
    
    return all_results, all_color_results