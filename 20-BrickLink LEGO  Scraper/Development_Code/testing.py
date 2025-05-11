import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, parse_qs
import re

HEADERS = {"User-Agent": "Mozilla/5.0"}

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
    print(table.text)
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

def extract_links_from_inventory(url):
    response = requests.get(url, headers=HEADERS)
    response.raise_for_status()
    with open("index.html", 'r', encoding='utf-8') as file:
        html_content = file.read()
    soup = BeautifulSoup(response.text, "html.parser")
    soup = BeautifulSoup(html_content, "html.parser")
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
    print(obj)
    return 

# Example usage
if __name__ == "__main__":
    url = "https://www.bricklink.com/catalogItemInv.asp?S=10454-1"
    url = "https://www.bricklink.com/catalogItemInv.asp?P=970c00"
    extract_links_from_inventory(url)
    # print(f"Parts: {len(parts)}")
    # print(f"Minifigures: {len(minifigs)}")
    # print(f"Sets: {len(sets)}")