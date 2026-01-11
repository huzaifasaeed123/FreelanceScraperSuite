# # from curl_cffi import requests
# # import json
# # from datetime import datetime
# # import pandas as pd
# # # Configuration for the betting sites
# # APIS = {
# #     "netbet": {
# #         "url": "https://ws.netbet.fr/component/datatree",
# #         "origin": "https://www.netbet.fr",
# #         "referer": "https://www.netbet.fr/"
# #     },
# #     "genybet": {
# #         "url": "https://ws.genybet.fr/component/datatree",
# #         "origin": "https://sport.genybet.fr",
# #         "referer": "https://sport.genybet.fr/"
# #     },
# #     "olybet": {
# #         "url": "https://ws.olybet.fr/component/datatree",
# #         "origin": "https://www.olybet.fr",
# #         "referer": "https://www.olybet.fr/"
# #     }
# # }

# # def get_headers(origin, referer):
# #     return {
# #         "Sec-Ch-Ua-Platform": '"Windows"',
# #         "Accept-Language": "en-US,en;q=0.9",
# #         "Sec-Ch-Ua": '"Chromium";v="143", "Not A(Brand";v="24"',
# #         "Content-Type": "application/json",
# #         "Sec-Ch-Ua-Mobile": "?0",
# #         "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
# #         "Accept": "*/*",
# #         "Origin": origin,
# #         "Referer": referer,
# #         "Accept-Encoding": "gzip, deflate, br",
# #     }

# # def find_component(components, tree_compo_key):
# #     """Recursively find a component by its key (standard Sportnco structure)"""
# #     if not components:
# #         return None
# #     for component in components:
# #         if component.get("tree_compo_key") == tree_compo_key:
# #             return component
# #         nested = component.get("components", [])
# #         if nested:
# #             result = find_component(nested, tree_compo_key)
# #             if result:
# #                 return result
# #     return None

# # def format_date(iso_date_str):
# #     """Formats ISO date to a simpler format like in the Excel sheet"""
# #     try:
# #         dt = datetime.fromisoformat(iso_date_str.replace("Z", "+00:00"))
# #         return dt.strftime("%d/%m %H:%M")
# #     except Exception:
# #         return iso_date_str

# # def parse_bet_data(outright_data, site_name):
# #     """Parses the JSON data to match the Excel columns: Time, Site, Sport, Match, Bet, Cote"""
# #     rows = []
    
# #     if not outright_data:
# #         return rows

# #     events = outright_data.get("events", [])
# #     for event in events:
# #         try:
# #             # 1. TIME
# #             start_time = format_date(event.get("start", ""))
            
# #             # 2. SPORT
# #             sport = event.get("sport", {}).get("label", "Super Cotes")
            
# #             # 3. MATCH & BET
# #             # In 'Super Cotes', the event label often combines the match and the bet.
# #             # We try to split it if a standard separator exists, otherwise keep it whole.
# #             full_label = event.get("label", "")
# #             if " - " in full_label:
# #                 parts = full_label.split(" - ", 1)
# #                 match_name = parts[0].strip()
# #                 bet_name = parts[1].strip()
# #             else:
# #                 match_name = "-" # Often unspecified for accumulators/combos
# #                 bet_name = full_label

# #             # 4. ODDS (Cote)
# #             # We look for the "Oui" selection or the highest odd in the market
# #             cote = 0
# #             for market in event.get("markets", []):
# #                 for bet in market.get("bets", []):
# #                     for sel in bet.get("selections", []):
# #                         # Usually we want the 'Oui' selection or the one with actual odds
# #                         if sel.get("odds", 0) > 1:
# #                             cote = sel.get("odds_display", sel.get("odds"))
# #                             # If we found a valid odd, we add the row
# #                             rows.append({
# #                                 "Time": start_time,
# #                                 "Site": site_name.capitalize(),
# #                                 "Sport": sport,
# #                                 "Match": match_name,
# #                                 "Bet": bet_name,
# #                                 "Cote": cote
# #                             })
# #         except Exception as e:
# #             print(f"Error parsing event {event.get('id')}: {e}")
# #             continue
            
# #     return rows

# # def fetch_site_data(site_name):
# #     """Fetches data from a single site using curl_cffi"""
# #     config = APIS.get(site_name)
# #     headers = get_headers(config["origin"], config["referer"])
    
# #     payload = {
# #         "context": {
# #             "url_key": "/super-cotes",
# #             "clientIp": "",
# #             "version": "1.0.1",
# #             "device": "web_vuejs_desktop",
# #             "lang": "fr",
# #             "timezone": "Europe/Paris",
# #             "url_params": {}
# #         }
# #     }
    
# #     try:
# #         response = requests.post(
# #             config["url"], 
# #             headers=headers, 
# #             json=payload,
# #             impersonate="chrome", # Crucial for bypassing 403
# #             timeout=15
# #         )
        
# #         if response.status_code == 200:
# #             data = response.json()
            
# #             # Extract the 'outright' section where Super Cotes live
# #             components = data.get("tree", {}).get("components", [])
# #             featured = find_component(components, "sport_page_featured")
            
# #             if featured and "data" in featured:
# #                 return featured["data"].get("outright")
            
# #             # Fallback: sometimes data is directly in different structures, 
# #             # but usually it's in sport_page_featured for these sites.
# #             return None
# #         else:
# #             print(f"[{site_name}] Failed with status: {response.status_code}")
# #             return None
            
# #     except Exception as e:
# #         print(f"[{site_name}] Connection error: {e}")
# #         return None

# # def main():
# #     print(f"{'Time':<15} | {'Site':<10} | {'Sport':<12} | {'Match':<25} | {'Bet':<40} | {'Cote'}")
# #     print("-" * 120)

# #     all_rows = []

# #     for site in APIS.keys():
# #         # Fetch raw data
# #         raw_data = fetch_site_data(site)
        
# #         # Parse into Excel-like rows
# #         site_rows = parse_bet_data(raw_data, site)
# #         all_rows.extend(site_rows)

# #     df=pd.DataFrame(all_rows)
# #     df.to_excel("Result.xlsx",index=False)
# #     # Display results
# #     for row in all_rows:
# #         # Truncate strings for display purposes
# #         match_display = (row['Match'][:22] + '..') if len(row['Match']) > 22 else row['Match']
# #         bet_display = (row['Bet'][:37] + '..') if len(row['Bet']) > 37 else row['Bet']
        
# #         print(f"{row['Time']:<15} | {row['Site']:<10} | {row['Sport']:<12} | {match_display:<25} | {bet_display:<40} | {row['Cote']}")

# # if __name__ == "__main__":
# #     main()

# from curl_cffi import requests
# import json
# from datetime import datetime
# import pandas as pd
# import os

# # Configuration for the betting sites
# APIS = {
#     "netbet": {
#         "url": "https://ws.netbet.fr/component/datatree",
#         "origin": "https://www.netbet.fr",
#         "referer": "https://www.netbet.fr/"
#     },
#     "genybet": {
#         "url": "https://ws.genybet.fr/component/datatree",
#         "origin": "https://sport.genybet.fr",
#         "referer": "https://sport.genybet.fr/"
#     },
#     "olybet": {
#         "url": "https://ws.olybet.fr/component/datatree",
#         "origin": "https://www.olybet.fr",
#         "referer": "https://www.olybet.fr/"
#     }
# }

# def get_headers(origin, referer):
#     return {
#         "Sec-Ch-Ua-Platform": '"Windows"',
#         "Accept-Language": "en-US,en;q=0.9",
#         "Sec-Ch-Ua": '"Chromium";v="143", "Not A(Brand";v="24"',
#         "Content-Type": "application/json",
#         "Sec-Ch-Ua-Mobile": "?0",
#         "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
#         "Accept": "*/*",
#         "Origin": origin,
#         "Referer": referer,
#         "Accept-Encoding": "gzip, deflate, br",
#     }

# def find_component(components, tree_compo_key):
#     """Recursively find a component by its key (standard Sportnco structure)"""
#     if not components:
#         return None
#     for component in components:
#         if component.get("tree_compo_key") == tree_compo_key:
#             return component
#         nested = component.get("components", [])
#         if nested:
#             result = find_component(nested, tree_compo_key)
#             if result:
#                 return result
#     return None

# def format_date(iso_date_str):
#     """Formats ISO date to a simpler format like in the Excel sheet"""
#     try:
#         dt = datetime.fromisoformat(iso_date_str.replace("Z", "+00:00"))
#         return dt.strftime("%d/%m %H:%M")
#     except Exception:
#         return iso_date_str

# def parse_bet_data(outright_data, site_name):
#     """Parses the JSON data to match the Excel columns: Time, Site, Sport, Match, Bet, Cote"""
#     rows = []
    
#     if not outright_data:
#         return rows

#     events = outright_data.get("events", [])
#     for event in events:
#         try:
#             # 1. TIME
#             start_time = format_date(event.get("start", ""))
            
#             # 2. SPORT
#             sport = event.get("sport", {}).get("label", "Super Cotes")
            
#             # 3. MATCH & BET
#             full_label = event.get("label", "")
#             print(full_label)
#             # Logic to try and separate Match from Bet
#             if " - " in full_label:
#                 parts = full_label.split(" - ", 1)
#                 match_name = parts[0].strip()
#                 bet_name = parts[1].strip()
#             else:
#                 # If no separator (common in Olybet), we mark match as Special/Combo
#                 # checking if "vs" is inside might indicate it's a match, but hard to extract cleanly
#                 match_name = "Special / Combo" 
#                 bet_name = full_label

#             # 4. ODDS (Cote)
#             cote = 0
#             for market in event.get("markets", []):
#                 for bet in market.get("bets", []):
#                     for sel in bet.get("selections", []):
#                         if sel.get("odds", 0) > 1:
#                             cote = sel.get("odds_display", sel.get("odds"))
#                             rows.append({
#                                 "Time": start_time,
#                                 "Site": site_name.capitalize(),
#                                 "Sport": sport,
#                                 "Match": match_name,
#                                 "Bet": bet_name,
#                                 "Cote": cote
#                             })
#         except Exception as e:
#             print(f"Error parsing event {event.get('id')}: {e}")
#             continue
            
#     return rows

# def fetch_site_data(site_name):
#     """Fetches data from a single site using curl_cffi and saves raw JSON"""
#     config = APIS.get(site_name)
#     headers = get_headers(config["origin"], config["referer"])
    
#     payload = {
#         "context": {
#             "url_key": "/super-cotes",
#             "clientIp": "",
#             "version": "1.0.1",
#             "device": "web_vuejs_desktop",
#             "lang": "fr",
#             "timezone": "Europe/Paris",
#             "url_params": {}
#         }
#     }
    
#     try:
#         print(f"Fetching {site_name}...")
#         response = requests.post(
#             config["url"], 
#             headers=headers, 
#             json=payload,
#             impersonate="chrome", 
#             timeout=15
#         )
        
#         if response.status_code == 200:
#             data = response.json()
            
#             # --- NEW: Save Raw JSON for analysis ---
#             filename = f"{site_name}_raw_data.json"
#             with open(filename, "w", encoding="utf-8") as f:
#                 json.dump(data, f, ensure_ascii=False, indent=4)
#             print(f"  -> Saved raw data to {filename}")
#             # ---------------------------------------

#             # Extract the 'outright' section
#             components = data.get("tree", {}).get("components", [])
#             featured = find_component(components, "sport_page_featured")
            
#             if featured and "data" in featured:
#                 return featured["data"].get("outright")
            
#             return None
#         else:
#             print(f"[{site_name}] Failed with status: {response.status_code}")
#             return None
            
#     except Exception as e:
#         print(f"[{site_name}] Connection error: {e}")
#         return None

# def main():
#     print(f"{'Time':<15} | {'Site':<10} | {'Sport':<12} | {'Match':<25} | {'Bet':<40} | {'Cote'}")
#     print("-" * 120)

#     all_rows = []

#     for site in APIS.keys():
#         # Fetch raw data
#         raw_data = fetch_site_data(site)
        
#         # Parse into Excel-like rows
#         site_rows = parse_bet_data(raw_data, site)
#         all_rows.extend(site_rows)

#     # Save to Excel
#     if all_rows:
#         df = pd.DataFrame(all_rows)
#         df.to_excel("Result.xlsx", index=False)
#         print("\nSuccessfully saved Result.xlsx")
#     else:
#         print("\nNo data found to save.")

#     # Display results in console
#     for row in all_rows:
#         match_display = (row['Match'][:22] + '..') if len(row['Match']) > 22 else row['Match']
#         bet_display = (row['Bet'][:37] + '..') if len(row['Bet']) > 37 else row['Bet']
#         print(f"{row['Time']:<15} | {row['Site']:<10} | {row['Sport']:<12} | {match_display:<25} | {bet_display:<40} | {row['Cote']}")

# if __name__ == "__main__":
#     main()


# import time
# import undetected_chromedriver as uc
# from selenium.webdriver.common.by import By
# from bs4 import BeautifulSoup

# URL = "https://www.winamax.fr/paris-sportifs/sports/100000"

# def main():
#     # Start undetected chrome
#     options = uc.ChromeOptions()
#     options.add_argument("--disable-blink-features=AutomationControlled")
#     options.add_argument("--start-maximized")
#     # options.add_argument("--headless")  # Uncomment if you want headless

#     driver = uc.Chrome(options=options)

#     print("[INFO] Opening site...")
#     driver.get(URL)

#     # Wait for page and dynamic content
#     print("[INFO] Waiting for content to load…")
#     time.sleep(8)  # Increase if needed

#     # Get full page HTML
#     html = driver.page_source

#     # Close browser
#     driver.quit()

#     # BeautifulSoup parsing
#     soup = BeautifulSoup(html, "html.parser")

#     # Find all divs with the exact class
#     divs = soup.find_all("div", class_="sc-iPRpaO xNyLa")

#     print(f"[INFO] Found {len(divs)} divs with class sc-iPRpaO xNyLa\n")

#     for i, div in enumerate(divs, start=1):
#         print(f"------ DIV #{i} ------")
#         print(div.get_text(strip=True))
#         print("-----------------------\n")

# if __name__ == "__main__":
#     main()



