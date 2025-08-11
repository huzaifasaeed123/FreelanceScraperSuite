import requests
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
import dataset
import time
import os
import traceback
import re
from bs4 import BeautifulSoup
import json
import threading

lock = threading.Lock()
def ScrapeUrl(headers, internal_params, legal_form, name_letter,i):
    internal_url = "https://www.moneyhouse.ch/de/jx/advanced-search-results-partial"
    response2 = requests.get(internal_url, headers=headers, params=internal_params)
    
    if response2.status_code == 200:
        Main_data = response2.json()
        result = Main_data['data']['results']
        newlist = []
        for ind in result:
            uri = ind.get("uri", "")
            currentName = ind.get("currentName", "")
            street = zip = city = countryCode = state = ""
            
            try:
                address = ind.get("mainAddress", {})
                street = address.get("street", "")
                zip = address.get("zip", "")
                city = address.get("city", "")
                countryCode = address.get("countryCode", "")
                state = address.get("state", "")
            except Exception as e:
                print(f"Error in parsing data: {e}")
            
            # Prepare the data object
            obj = {
                "Url": uri,
                "Rechtsform": legal_form,
                "Name": currentName,
                "Adresse": street,
                "PLZ": zip,
                "ORT": city,
                "CountryCode": countryCode,
                "state": state,
                "SearchLetter": name_letter,
                "Scraped": False
            }
            newlist.append(obj)

        print(f"Page Url Threading Reached at ::{i}")
            # print(obj)

        # Return the list of scraped objects
        return newlist
    
def store_data_in_db(Main_list,database,databaseTable):
    # Connect to the existing SQLite database using dataset
    db = dataset.connect(f'sqlite:///{database}')

    # Create or connect to the 'scraped_data' table
    table = db[databaseTable]
    with lock:
        try:
            # Insert the entire list at once using insert_many
            table.insert_many(Main_list)
        except Exception as e:
            print(f"Error during database insertion: {e}")
    # Insert data into the table
    # for item in Main_list:
    #     # Upsert ensures that if a record with the same URL already exists, it will be updated
    #     table.upsert({
    #         'Url': item["Url"],
    #         'Rechtsform': item["Rechtsform"],
    #         'Name': item["Name"],
    #         'Adresse': item["Adresse"],
    #         'PLZ': item["PLZ"],
    #         'ORT': item["ORT"],
    #         'CountryCode': item["CountryCode"],
    #         'state': item["state"],
    #         'SearchLetter': item["SearchLetter"],
    #         'Scraped': item["Scraped"]
    #     }, ['Url'])  # 'Url' is used as a unique key

    # Commit and close the connection is handled automatically by dataset
def threadingScrapeUrl(database,databaseTable):
    # Base URL for the request
    base_url = "https://www.moneyhouse.ch/de/jx/advanced-search-filter-partial"

    # Shared list and lock for thread safety
    Main_list = []
    # lock = Lock()  # To protect access to Main_list
        # List of legalForm values to iterate over
    legal_forms = [
        3, 8, 1, 1007, 84, 5, 4, 1010, 85, 2, 10, 89, 82, 7, 1021, 1022, 6, 92, 9
    ]

    # Alphabet letters for 'name' parameter
    alphabet = [chr(i) for i in range(ord('a'), ord('z') + 1)]

    # Headers (add your headers here as necessary)
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'Accept-Language': 'de-DE,de;q=0.9,en;q=0.8',
        'X-Requested-With': 'XMLHttpRequest',
        'Connection': 'keep-alive',
        'cookie': "mh_lifetime=80nf1vqm01ok4bc; __cmpconsent10444=CQDo93gQDo93gAfIPBENBCFsAP_gAEPgAAQ4J6pR9G7ebWlHOHpzYfsEaYUX11hp4sQhAACBA6IACBOA8IQG1GACIAyAJCACABAAoBZBIAFsGAhEAUAAAIAFIBAoQgAAAAAKIGAAAAERQ0AQCAgIAAAgQAAAAAAEAgAAgAAACBKIBIAAgIAACgAAAAABAAAAABIAAAAIABAAAAIAYAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAACB44AJBoVEAJRAhIQSBhBAgBEFYQAUCAAAAAgQICAAgQAOAEAlRgAgAAAAAAAAAAAKAAAQAACAAIRABAAACAACAQKAAAAAAACABgAAAAAUAAEAAICAAAIEAAAAAABAAAAIAAAAAQAAAAAAAAAAoAAAAAAQAAAAAAAAAACAA; __cmpcvcu10444=__s2215_s1574_s866_s1227_s74_c6302_s981_s1642_s1852_c16312_s94_s446_s1052_s40_s64_s73_s3022_s914_s335_s1255_s672_s640_s1259_s2379_s904_s28_s1989_s2003_s2351_s405_s1932_s457_s65_c10950_s23_s896_s1592_s1898_c56556_c14743_s2294_s571_s25_s1100_s56_s314_s336_s125_c10951_s239_s127_s7_c10254_c34768_s1656_s573_s1974_s312_s1591_s1655_s1_s26_s2612_s135_s1104_s2723_s2739_s1409_s905_s977_c10089_s46_s10_s24_s161_s1298_s37_s14_s1465_s561_s1475_c10274_s1442_s2103_c8346_s533_s2688_s2_s1315_c24245_c9657_s1399_s654_s6_s153_c34773_s220_s884_s216_s11_s1049_s322_s1934_s885_s338_s252_c9211_s1272_s4_s562_s1358_s267_s883_s1097_c7017_s49_s1085_s2546_s2492_s886_s1595_c13897_c11387_s1341_s2369_s460_s1327_s271_s291_s292_c9982_s2522_s358_s188_s191_s1659_c31009_s1658_s193_c35039_s19_s653_s748_c10083_s1068_s462_s1886_s441_s274_c28050_c10013_s2536_s52_s199_s1432_s1657_s1431_c10095_c22002_s605_s203_c9145_s32_s2297_s141_s1777_s1203_s77_s739_s60_c14426_c13900_s21_s679_s34_s67_s35_s3_s30_c10012_s1189_s1618__; __cmpcpcu10444=____; ens_mrcntcmp=; p4m_vid=eb8fea758cc48e2a9c0b4c9bdff7ecb75d6d0b78f0dfaf77eb2fb91ebae1ad93; pa_privacy=%22optin%22; _pcid=%7B%22browserId%22%3A%22m01okkoat68xem9t%22%2C%22_t%22%3A%22mfq3i20e%7Cm01okkoe%22%7D; _pctx=%7Bu%7DN4IgrgzgpgThIC4B2YA2qA05owMoBcBDfSREQpAeyRCwgEt8oBJAE0RXSwH18yBbAGYBHAMz0ATAAZBAH35SAjJQDWKyoJABfIA; _cc_id=8507958ff1a4191d436e7be8d71866cc; panoramaId_expiry=1724718205295; panoramaId=b851886c2d0100b160a53a03514a4945a70233a26a2deac4f5f20bb6da25016c; panoramaIdType=panoIndiv; cto_bundle=SwxfA19PQjIyZmszV3VUQzhUdjZZSUtKQkI5USUyRmx3N1ZXazR0MEw1bk5lWmYybUM2TTdsaUdDVHZZN3hha2hWQ2JNZ0pWbGtEJTJCd0ZmY1NqRDIyMUlCbXNNV2QlMkZDbCUyRjIlMkJsdGJ2RU84enFVNHRvOFZFJTJGelFOd0ZXS1FZaXFtSEFHWXNwa0ZzJTJGOTZsNUJaVmpTMWllWVNsSkdmczJwOTFJT21KMUh3OG53RVBZR3VnbG04JTJGV3VBYzBhd1IyMzhDTmZYUHBEUkY4RDNoeHV2ekszTGVxRWQ2Y09LOGRWRGVpOTFId3hQbU1yd1lYNjJQVFM5TE9RS05GMGQ2aEl6MlBmc2g5S2puYnMzeEx6bTg4ajVjcGxoUVlVJTJGUSUzRCUzRA; _gcl_au=1.1.1896058727.1724113533; _hjSessionUser_1177114=eyJpZCI6IjQ5Y2U3ODEzLWNmYTUtNTEwNS04MzliLTRlNjhkNTZlNjkxYiIsImNyZWF0ZWQiOjE3MjQxMTM1MzM1MDcsImV4aXN0aW5nIjp0cnVlfQ==; mh_session=4jqd1l1m01puvz2; mh_employee=; mh_employee_reason=; p4m_snot=3; _hjSession_1177114=eyJpZCI6ImMwNGE4OWUwLTNiYTktNDkyMC04NmFiLTM1MmMwZWU1ZjUwMyIsImMiOjE3MjQxMTkzMDc3NTMsInMiOjEsInIiOjEsInNiIjowLCJzciI6MCwic2UiOjAsImZzIjowLCJzcCI6MH0=; __vads=-fwIGzS0Un18m2ufmCFja06xG; _uetsid=b69c40105e8a11ef82cb4bac85656669; _uetvid=b69c7b905e8a11efb9a169ff75366d56; bclk=5359209766070114; __gads=ID=72138ccf30765566:T=1724119490:RT=1724120241:S=ALNI_MavVXybTWvdd_7doFFsTV_mPiuABA; __gpi=UID=00000ed1650d1248:T=1724119490:RT=1724120241:S=ALNI_MbqkelRAQ3yr3y5JZXlfjHpdqACQQ; __eoi=ID=fb5f6034f6622bc6:T=1724119490:RT=1724120241:S=AA-Afjbo20kwHai69SSry3-wFeMq; token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6MTU1OTA1NSwidGlkIjoxLCJpYXQiOjE3MjQxMjAzMjN9.wUW1f_hVm707-Q138SeQh0IKjqBm2RFQC_3X-qL8QhM; user=eyJpZCI6MTU1OTA1NSwiZ3VpZCI6ImQ3MzI2MTlmLTY0ZWUtNDNiMS05MWFmLTBjMGNiM2YwZWZmZCIsImNybV9pZCI6IjAwMVZqMDAwMDA2V1dSRElBNCJ9; session=eyJmbGFzaCI6e30sInBhc3Nwb3J0Ijp7InVzZXIiOiJ7XCJpZFwiOlwiMTAxMTM0ODcyXCIsXCJ0b2tlblwiOlwiZDczMjYxOWYtNjRlZS00M2IxLTkxYWYtMGMwY2IzZjBlZmZkXCJ9In19; session.sig=lETdHGb9_nCSBZJLv8yflV6Xn2I; mh_status=premium; ens_c1pid=101134872; p4m_inos=29; p4m_inot=43; p4m_sid=1724119303926_3495548763-4206934085-2698965808-617574777%3BTue%20Aug%2020%202024%2007%3A51%3A17%20GMT%2B0500%20(Pakistan%20Standard%20Time)"
    }

    # Iterate over each letter and legalForm value and make the request
    with ThreadPoolExecutor(max_workers=50) as executor:
        futures = []
        
        # Outer loop to iterate over each letter from 'a' to 'z'
        countindex=0
        for letter in alphabet:
            
            # Inner loop to iterate over each legal form
            for legal_form in legal_forms:
                params = {
                    'status': 1,
                    'name': letter,
                    'legalForm': legal_form
                }
                response = requests.get(base_url, headers=headers, params=params)

                # Check if the response was successful
                if response.status_code == 200:
                    # print(f"Request successful for legalForm={legal_form}, letter={letter}")
                    data = response.json()
                    totalCount = data['data']['totalCount']
                    print(f"Total count: {totalCount} for legalForm={legal_form}, letter={letter}")

                    if totalCount < 48000:
                        internalIteration = int(totalCount / 50)
                        for i in range(0, internalIteration + 1):
                            # print(f"Scheduling scraping for legalForm={legal_form}, letter={letter}, page={i}")
                            internal_params = {
                                'status': 1,
                                'name': letter,
                                'legalForm': legal_form,
                                'page': i,
                            }
                            # Submit tasks to the executor
                            countindex=countindex+1
                            futures.append(executor.submit(ScrapeUrl, headers, internal_params, legal_form, letter,countindex))
                            break
                else:
                    print(f"Request failed for legalForm={legal_form}, letter={letter} with status code: {response.status_code}")
                break
            break
        # Wait for all futures to complete and aggregate results safely
        for future in as_completed(futures):
            try:
                result_list = future.result()
                if isinstance(result_list, list):
                    with lock:  # Ensure thread-safe access to the Main_list
                        Main_list.extend(result_list)
            except Exception as e:
                print(f"Error in thread: {e}")

    # Store data in Database
    # database='ScrapedData.db'
    store_data_in_db(Main_list,database,databaseTable)
    # Convert the aggregated data to a DataFrame and save it to a CSV file
    print(f"Page Url Scraping is Completed Now,\nDatabase Table with Named Scraped_data has been created which contain Page Url")
    df = pd.DataFrame(Main_list)
    df.to_csv('ScrapedData.csv', index=False)

'''
Now The Following Function is For Individual Page Scraping 
read_db_to_dict_list(table)> this Function is used to convert into dict for only those rows whose scraped column is False
retriveIndividualPages(obj1,index):: This Function is used to scrap Individual Buisness Page to extract all relavant Information
threadingIndividualPages(ScrapedData,Scrapedtable,UpdatedTable)  This Function is responsible For threading Managment and call up retriveIndividualPages(obj1,index) 
sql_table_to_csv   :: This function finally convert the list UpdatedTable of SQL Database into CSV that contain all relavant Information


'''
def read_db_to_dict_list(table):
    # Connect to the SQLite database using the provided database name
    # db = dataset.connect(f'sqlite:///{database}')
    
    # # Assume the table name is 'scraped_data' (same as used in previous examples)
    # table = db[databaseTable]
    
    # Fetch all rows from the table
    rows = table.find(Scraped=False)
    
    # Convert the result to a list of dictionaries
    rows_list = [dict(row) for row in rows]
    
    return rows_list
def get_management_info(record,headers):
    linkedin_link = ""
    president_name = ""
    branch_leader=""
    try:
        # Extract URL path from the full URL
        base_url = "https://www.moneyhouse.ch/de/company/"
        url_path = record['Url']
        
        management_url = f"{base_url}{url_path}/management"
        # Headers (to mimic a real browser)
        # Send GET request
        response = requests.get(management_url, headers=headers)

        # Check if the request was successful
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, "html.parser")
            key_classes = soup.find_all("td", class_="entity-name")

            rechtsform_id = int(record.get('Rechtsform', 0))
            
            for key in key_classes:
                president_span = key.find("span", class_="role bean bean-col-mandate")
                if president_span:
                    if rechtsform_id == 3:
                        if "Verwaltungsrat-Präsident" in president_span.text:
                            president_name_a = key.find("a", class_="name-link l-mobile-one-whole")
                            if president_name_a:
                                president_name = president_name_a.text.strip()

                            entity_follow = key.find_next_sibling("td", class_="entity-follow")
                            if entity_follow:
                                a = entity_follow.find("a", class_="icon-linkedIn linkedin-link")
                                if a:
                                    linkedin_link = a.get("href", "")
                            break
                            
                    elif rechtsform_id == 9:
                        if "Leiter der Zweigniederlassung" in president_span.text:
                            president_name_a = key.find("a", class_="name-link l-mobile-one-whole")
                            if president_name_a:
                                branch_leader = president_name_a.text.strip()

                            entity_follow = key.find_next_sibling("td", class_="entity-follow")
                            if entity_follow:
                                a = entity_follow.find("a", class_="icon-linkedIn linkedin-link")
                                if a:
                                    linkedin_link = a.get("href", "")
                            break

            # print(f"Management info scraped for record ID: {record.get('Url', 'Unknown')}")
            
            return {
                "Präsident": president_name,
                "Leiter der Zweigniederlassungen": branch_leader,
                "LinkedIn Link": linkedin_link,
            }
        else:
            print(f"Failed to retrieve management page. Status code: {response.status_code} for record ID: {record.get('Url', 'Unknown')}")
            return{
                "Präsident": president_name,
                "Leiter der Zweigniederlassungen": branch_leader,
                "LinkedIn Link": linkedin_link,
            }
    except Exception as e:
        print(f"Exception occurred for record ID {record.get('Url', 'Unknown')}: {e}")
        traceback.print_exc()
        return{
                "Präsident": president_name,
                "Leiter der Zweigniederlassungen": branch_leader,
                "LinkedIn Link": linkedin_link,
            }

def retriveIndividualPages(obj1):
    try:
        base_url="https://www.moneyhouse.ch/de/company/"
        url = f"{base_url}{obj1['Url']}"

        # Headers (to mimic a real browser)
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Accept-Language': 'de-DE,de;q=0.9,en;q=0.8',
            'X-Requested-With': 'XMLHttpRequest',
            'Connection': 'keep-alive',
            "cookie": "mh_lifetime=1edan612e8mbyykjhk; __cmpconsent10444=CQTFvHgQTFvHgAfIPBENBvFsAP_gAEPgAAQ4J6pR9G7ebWlHODp3YfsEaYQX11hp4sQhAgCBA6IACBOA8IQG1GAiIAyAJCACABAAoBRBIAFsGAhEAUAAAIAFIBCoQAAAAAAKIGAAAAERQ0AQCAgIAAAgQAAAAABEAhAAgAAACBKIBIAAgIAACgAAAAABAAAAAQIAAAAIQBAAAAIAYAAAEAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAAAAAAACCN4AJBoVEEJRAAIRCBhBAgAEFYQAUCAIAAAgQICAAgQAOAEAFRgIgAAAAAAAAAAAIAAAQAACAAIRABAAACAACAQKAAAAAAACABgAAAAAUAAEAAICAAAIEAAAAAARAAQAIAAAAAQAAAAAAAAAAoAAAAAAAAAAAAAAAAACAAAAAAAAAAAAAAAAAAAAAAAAAAACAA; __cmpcvcu10444=__s2215_c57305_s1574_s866_s1227_s74_c6302_s981_s1642_s1852_c16312_s94_s446_s154_s1052_s40_s64_s73_s3022_s914_s335_s1255_s672_s640_s1259_s1651_s2379_s904_s28_s1989_s2003_s2351_s405_s1932_s457_s65_c10950_s23_s896_s1592_s1898_c56556_c14743_s2294_s571_s1254_s25_s1100_s56_s314_s336_s125_c10951_s239_s127_s7_c10254_c34768_s1656_s573_s1974_s312_s1591_s1655_s1_s26_s2612_s135_s1104_s2723_s2739_s1409_s905_s977_c10089_s46_s10_s24_s161_s1298_s37_s14_s1465_s561_s3118_s1475_c10274_s1442_s2103_c8346_s533_s2688_s2_s1315_c24245_c9657_s1399_s654_s6_s153_c34773_s220_s884_s216_s11_s1049_s322_s1934_s885_s338_s252_s1365_c9211_s1272_c60588_s4_s562_s1358_s741_s267_s883_s1097_c44896_c44894_c7017_s49_s1085_s2546_s2492_s886_s1595_c13897_c11387_s1341_s2369_s460_s1327_s271_s291_s292_c9982_s2522_s188_s191_s1659_c31009_s1658_s193_c35039_s19_s653_s748_c10083_s1068_s462_s1886_s441_s274_c28050_c10013_s2536_s52_s199_s1432_s1657_s1431_c10095_c22002_s605_s203_c9145_s32_s2297_s141_s1777_s1203_s77_s739_s60_c14426_c13900_s21_s679_s34_s67_s35_s3_s30_c10012_s1189_s1618__; __cmpcpcu10444=____; p4m_inot=1; p4m_snot=1; ens_mrcntcmp=; p4m_vid=427221db20435cd97c0a144309c4f8502257b9b7b32b4e207b4e0f4636092c79; _cc_id=16cbce3265c0efac8910ac910fa09b8c; __vads=rYIZv0M33vWogpqSpHZcI5YAK; __gads=ID=af3a05297f3b417e:T=1750070143:RT=1751151156:S=ALNI_MYl_HHFQ9ULoYgV-1eXchxOQz9MAg; __gpi=UID=000011305e493c0a:T=1750070143:RT=1751151156:S=ALNI_MaDnhfpDNKIIOxEebT2t9eHk6axRA; __eoi=ID=593a7767b288a491:T=1750070143:RT=1751151156:S=AA-AfjZr0HjpRGYYY67VUeVKyMTZ; bclk=2442708271100794; token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6MTU1OTA1NSwidGlkIjoxLCJpYXQiOjE3NTExNTIxMTZ9.vonHLziUyFkikbFliwJjr_5DsZmjt2DwmEQiZ6lMqHI; user=eyJpZCI6MTU1OTA1NSwiZ3VpZCI6ImQ3MzI2MTlmLTY0ZWUtNDNiMS05MWFmLTBjMGNiM2YwZWZmZCIsImNybV9pZCI6IjAwMVZqMDAwMDA2V1dSRElBNCIsInNlc3Npb25faWQiOiJjMDEzMjdkOC1kYzJhLTQ2ZTYtYTNkNC0zZGY2ODg2MTdmMTQifQ%3D%3D; _sharedid=05ef558e-a31b-4441-aae8-53c3fb7e9b46; _sharedid_cst=NCw%2BLJcs4Q%3D%3D; pbjs-unifiedid=%7B%22TDID%22%3A%225be9da22-4874-4640-9426-6f6f9a467aad%22%2C%22TDID_LOOKUP%22%3A%22TRUE%22%2C%22TDID_CREATED_AT%22%3A%222025-06-15T12%3A48%3A58%22%7D; pbjs-unifiedid_cst=NCw%2BLJcs4Q%3D%3D; cto_bidid=61fJa183RVU2c3VKWUp3cGlxQXdSUlBQczlGeGR0VldhbWF3ell4dkF2WmJRTVh5R0NONFBCY3g0eEdyQUh2aUhuOERNd2RUaFpwSFQlMkZRNk1DWmIyQjNLdmZHWVFkeE96TE45elZKYmJBWHpMWllJJTNE; _criteoId=%7B%22criteoId%22%3A%2261fJa183RVU2c3VKWUp3cGlxQXdSUlBQczlGeGR0VldhbWF3ell4dkF2WmJRTVh5R0NONFBCY3g0eEdyQUh2aUhuOERNd2RUaFpwSFQlMkZRNk1DWmIyQjNLdmZHWVFkeE96TE45elZKYmJBWHpMWllJJTNE%22%7D; _criteoId_cst=NCw%2BLJcs4Q%3D%3D; panoramaId_expiry=1753188551818; panoramaId=b1c8e448054e53dadb5d753b581e4945a70257f982097a444aa3a19955c5839d; panoramaIdType=panoIndiv; cto_bundle=nVflVV9ibXM5Nm9mbmpBRlBYOWVvOHRnNm1MUUJFZkc4bkZkY2h1VlpCREhwd1IlMkZ0OXlOZUVkZ3h0R2xCTUg5Vkg4ekdkM2Z6VDQxUCUyQjd2dnVubUJ0MUtkVEpGenlRaHdMQ1pxVHo1ZERBWnJBSUNpemx5OURoaCUyRjR3JTJCeVRuNHVzYnVTQzdmc0xNY2M5R0xadiUyQkpCZnFGZW0wdlVuajFzS29nJTJGWnVNaWFJeHUlMkJncyUzRA; mh_session=z67xm9omd9mz70y; session=eyJmbGFzaCI6e30sInBhc3Nwb3J0Ijp7InVzZXIiOiJ7XCJpZFwiOlwiMTAxMTM0ODcyXCIsXCJ0b2tlblwiOlwiZDczMjYxOWYtNjRlZS00M2IxLTkxYWYtMGMwY2IzZjBlZmZkXCIsXCJzZXNzaW9uSWRcIjpcImMwMTMyN2Q4LWRjMmEtNDZlNi1hM2Q0LTNkZjY4ODYxN2YxNFwifSJ9fQ==; session.sig=fkzyED-Dwreb3R7RZ5T3NXQVPZA; mh_status=premium; _sp_ses.becb=*; _sp_id.becb=c07cfa08-d4ee-4a4d-b5cc-5426e0c428aa.1750070139.14.1752892696.1752857079.e60659ac-8589-432d-a189-cf461057c07c.5f20e5cb-2fb7-4c6c-950d-ab9cb0786bbb.2e7a8fd7-6598-4fca-adfd-0fb5de860567.1752892576798.12"
            # Add any additional headers you need
        }

        # Send GET request
        response = requests.get(url, headers=headers)

        # Check if the request was successful
        if response.status_code == 200:
            # Parse the content with BeautifulSoup
            Alter_der_Firma=Umsatz_in_CHF=Mitarbeiter=Rechtsform=""
            telephone=Email=website=""
            Management=Firmenzweck=branche=uidNumber=""
            managment1=newsetVor=newsetZei=""
            soup = BeautifulSoup(response.content, "html.parser")
            key_classes=soup.find_all("h4",class_="key")
            # 
            for key in key_classes:
                if "Alter der Firma" in key.text:
                    Alter_der_Firma=key.find_next_sibling('span').text
                elif "Umsatz in CHF" in key.text:
                    Umsatz_in_CHF=key.find_next_sibling('span').text
                elif "Mitarbeiter" in key.text:
                    Mitarbeiter=key.find_next_sibling('span').text
                elif "Rechtsform" in key.text:
                    Rechtsform=key.find_next_sibling('p',class_="value").text
                elif "Geschäftsleitung" ==key.text:
                    managment1=key.find_next_sibling('p').text
                elif "neueste Verwaltungsräte" ==key.text:
                    newsetVor=key.find_next_sibling('p').text
                elif "neuste Zeichnungsberechtigte" ==key.text:
                    newsetZei=key.find_next_sibling('p').text
                 
                
            # print(Alter_der_Firma,Umsatz_in_CHF,Mitarbeiter,Rechtsform)
            connection_rows=soup.find_all("div",class_="connections-row")
            # 
            for connection in connection_rows:
                check=connection.find("a").get("href")
                if "tel:" in check:
                    telephone=connection.find("a").text
                elif "mailto:" in check:
                    Email=connection.find("a").text
                else:
                    website=connection.find("a").text
            # print(telephone,Email,website)
            allH2=soup.find_all("h2")
            # pattern = r"^Management(?: \((\d*)\))?$"
            # for h2 in allH2:
            #     if re.fullmatch(pattern, h2.text):
            #         section=h2.find_next_sibling('div', class_='section')
            #         if section:
            #             Management_Para=section.find("p")
            #             if Management_Para:
            #                 Management=Management_Para.text
            #             # print(f"Management is:{Management}")
            script_tag = soup.find('script', {'type': 'application/ld+json'})
            
            if script_tag:
                # Load the content as JSON
                json_content = json.loads(script_tag.string)
                if json_content:
                    # Extract the 'description' field
                    Firmenzweck = json_content.get("description", "Description not found")
                    
                    # print("Firmenzweck:", Firmenzweck)
            branche_ele=soup.find('div',class_="branch overview-branch-holder")
            if branche_ele:
                branche=branche_ele.text.replace("Branche:","").strip()
            uidNumber_ele=soup.find('div',class_="chnr")
            if uidNumber_ele:
                uidNumber=uidNumber_ele.get_text().replace("Handelsregister-Nr.:&nbsp", "").strip()
            if Rechtsform=="":
                Rechtsform_ele=soup.find("div",class_="company-legal-form company-info-block")
                if Rechtsform_ele:
                    Rechtsform=Rechtsform_ele.text.replace("Rechtsform:","").strip()
            Kanton=obj1["state"]
            if Kanton=="nan":
                Kanton_ele=soup.find("div",class_="company-canton company-info-block")
                if Kanton_ele:
                    Kanton=Kanton_ele.text.replace("Rechtsform:","").strip()
            # print(f"branche is ::{branche}")
            print(f"Individual Threading Reached at ::{obj1['id']}")
            try:
                plz1=int(obj1["PLZ"])
            except Exception as e:
                plz1=str(obj1["PLZ"])
            if telephone!="":
                telephone=f"'{telephone}'"
            if obj1["Rechtsform"] in [3,9,'3','9']:
                obj3=get_management_info(obj1,headers)
            else:
                obj3={
                "Präsident": "",
                "Leiter der Zweigniederlassungen": "",
                "LinkedIn Link": "",
            }
            obj2={
                "Url": url,
                "Name": obj1["Name"],
                "Kanton": Kanton,
                "Rechtsform": Rechtsform,
                "Alter":Alter_der_Firma,
                "Umsatz": Umsatz_in_CHF,
                "Mitarbeiter":f"'{Mitarbeiter}'",
                "Adresse": obj1["Adresse"],
                "PLZ": plz1,
                "ORT":obj1["ORT"],
                "Telefonnummer":telephone,
                "Webseite":str(website),
                "Emailadresse":str(Email),
                # "Management":str(Management),
                "Geschäftsleitung":managment1,
                "neuste Zeichnungsberechtigte": newsetZei,
                "neueste Verwaltungsräte":newsetVor,
                "Branche":branche,
                "Firmenzweck":Firmenzweck,
                "UID Number":uidNumber,
                "Rechtsform 2(Extra For Testing)": obj1["Rechtsform"]
            }
            obj2.update(obj3)
            return obj2
        else:
            values_list = list(obj1.values())
            print(f"Failed to retrieve the page. Status code: {response.status_code}")
            return values_list
    except Exception as e:
        print("Exception has been Occur",e)
        values_list = list(obj1.values())
        traceback.print_exc()
        return values_list
    


def threadingIndividualPages(ScrapedData,Scrapedtable,UpdatedTable):
    Main_list=[]
    MissingData=[]
    with ThreadPoolExecutor(max_workers=50) as executor:
        futures = []
        for index, obj in enumerate(ScrapedData):
            # if index>=500001 and index<=600000:
            # if obj['id']>=10 and obj['id']<=30:
                # print("Printing ID",obj["id"])
                futures.append(executor.submit(retriveIndividualPages, obj))
                # break
        for future in as_completed(futures):
            try:
                result_list = future.result()
                if isinstance(result_list, dict):
                        Main_list.append(result_list)
                        base_url="https://www.moneyhouse.ch/de/company/"
                        # url = f"{base_url}{result_list['Url']}"
                        # print(result_list['Url'].replace(base_url,""))
                        updated_url=result_list['Url'].replace(base_url,"")
                        
                        with lock:
                            Scrapedtable.update({'Url': updated_url, 'Scraped': True}, ['Url'])
                            UpdatedTable.insert(result_list)
                if isinstance(result_list, list):
                        MissingData.append(result_list)
            except Exception as e:
                print(f"Error in thread: {e}")

    # df = pd.DataFrame(Main_list)
    # df = df.astype(str)
    # df.to_csv('FinalIndividualPages10.csv', index=False)

    # df1 = pd.DataFrame(MissingData)
    # df1 = df1.astype(str)
    # df1.to_csv('Missing10.csv', index=False)
    # print(list1[0]["Url"])
def sql_table_to_csv(UpdatedTable ,csv_file_path):
    # Connect to the database
    # db = dataset.connect(f'sqlite:///{db_name}')
    
    # # Retrieve all data from the specified table
    # table = db[table_name]
    rows = list(UpdatedTable.all())  # Convert the iterator to a list of dictionaries
    
    # Convert the list of dictionaries to a pandas DataFrame
    df = pd.DataFrame(rows)
    
    # Save the DataFrame to a CSV file
    df.to_csv(csv_file_path, index=False)
    
    print(f"Data from table '{UpdatedTable}' has been successfully written to '{csv_file_path}'.")

def main():
    database='Final_Combined.db'
    databaseTable="MoneyHouse_Url"
    if not os.path.exists(database):
        print(f"DataBase with Named {database} have not been found For Url")
        print("So Scraping For Url Has been start,\noverall almost 14k Request for Scraping Url has been Performed")
        threadingScrapeUrl(database,databaseTable)
    print("Page Url Scraping Done,Now reading Database")
    db = dataset.connect(f'sqlite:///{database}')
    Scrapedtable = db[databaseTable]
    UpdatedTable=db['MoneyHouse']
    time.sleep(5) 
    ScrapedData=read_db_to_dict_list(Scrapedtable)
    threadingIndividualPages(ScrapedData,Scrapedtable,UpdatedTable)
    # FinalDataCSVName="FinalDataDB.xlsx"
    # sql_table_to_csv(UpdatedTable,FinalDataCSVName)
    # print(list[1])

main()