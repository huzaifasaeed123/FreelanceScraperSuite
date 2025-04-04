import requests
from bs4 import BeautifulSoup
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
import traceback
import re
import dataset
# URL of the target page
def retriveIndividualPages(obj1,index):
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
            "cookie": "mh_lifetime=80nf1vqm01ok4bc; __cmpconsent10444=CQDo93gQDo93gAfIPBENBCFsAP_gAEPgAAQ4J6pR9G7ebWlHOHpzYfsEaYUX11hp4sQhAACBA6IACBOA8IQG1GACIAyAJCACABAAoBZBIAFsGAhEAUAAAIAFIBAoQgAAAAAKIGAAAAERQ0AQCAgIAAAgQAAAAAAEAgAAgAAACBKIBIAAgIAACgAAAAABAAAAABIAAAAIABAAAAIAYAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAACB44AJBoVEAJRAhIQSBhBAgBEFYQAUCAAAAAgQICAAgQAOAEAlRgAgAAAAAAAAAAAKAAAQAACAAIRABAAACAACAQKAAAAAAACABgAAAAAUAAEAAICAAAIEAAAAAABAAAAIAAAAAQAAAAAAAAAAoAAAAAAQAAAAAAAAAACAA; __cmpcvcu10444=__s2215_s1574_s866_s1227_s74_c6302_s981_s1642_s1852_c16312_s94_s446_s1052_s40_s64_s73_s3022_s914_s335_s1255_s672_s640_s1259_s2379_s904_s28_s1989_s2003_s2351_s405_s1932_s457_s65_c10950_s23_s896_s1592_s1898_c56556_c14743_s2294_s571_s25_s1100_s56_s314_s336_s125_c10951_s239_s127_s7_c10254_c34768_s1656_s573_s1974_s312_s1591_s1655_s1_s26_s2612_s135_s1104_s2723_s2739_s1409_s905_s977_c10089_s46_s10_s24_s161_s1298_s37_s14_s1465_s561_s1475_c10274_s1442_s2103_c8346_s533_s2688_s2_s1315_c24245_c9657_s1399_s654_s6_s153_c34773_s220_s884_s216_s11_s1049_s322_s1934_s885_s338_s252_c9211_s1272_s4_s562_s1358_s267_s883_s1097_c7017_s49_s1085_s2546_s2492_s886_s1595_c13897_c11387_s1341_s2369_s460_s1327_s271_s291_s292_c9982_s2522_s358_s188_s191_s1659_c31009_s1658_s193_c35039_s19_s653_s748_c10083_s1068_s462_s1886_s441_s274_c28050_c10013_s2536_s52_s199_s1432_s1657_s1431_c10095_c22002_s605_s203_c9145_s32_s2297_s141_s1777_s1203_s77_s739_s60_c14426_c13900_s21_s679_s34_s67_s35_s3_s30_c10012_s1189_s1618__; __cmpcpcu10444=____; ens_mrcntcmp=; p4m_vid=eb8fea758cc48e2a9c0b4c9bdff7ecb75d6d0b78f0dfaf77eb2fb91ebae1ad93; pa_privacy=%22optin%22; _pcid=%7B%22browserId%22%3A%22m01okkoat68xem9t%22%2C%22_t%22%3A%22mfq3i20e%7Cm01okkoe%22%7D; _pctx=%7Bu%7DN4IgrgzgpgThIC4B2YA2qA05owMoBcBDfSREQpAeyRCwgEt8oBJAE0RXSwH18yBbAGYBHAMz0ATAAZBAH35SAjJQDWKyoJABfIA; _cc_id=8507958ff1a4191d436e7be8d71866cc; panoramaId_expiry=1724718205295; panoramaId=b851886c2d0100b160a53a03514a4945a70233a26a2deac4f5f20bb6da25016c; panoramaIdType=panoIndiv; cto_bundle=SwxfA19PQjIyZmszV3VUQzhUdjZZSUtKQkI5USUyRmx3N1ZXazR0MEw1bk5lWmYybUM2TTdsaUdDVHZZN3hha2hWQ2JNZ0pWbGtEJTJCd0ZmY1NqRDIyMUlCbXNNV2QlMkZDbCUyRjIlMkJsdGJ2RU84enFVNHRvOFZFJTJGelFOd0ZXS1FZaXFtSEFHWXNwa0ZzJTJGOTZsNUJaVmpTMWllWVNsSkdmczJwOTFJT21KMUh3OG53RVBZR3VnbG04JTJGV3VBYzBhd1IyMzhDTmZYUHBEUkY4RDNoeHV2ekszTGVxRWQ2Y09LOGRWRGVpOTFId3hQbU1yd1lYNjJQVFM5TE9RS05GMGQ2aEl6MlBmc2g5S2puYnMzeEx6bTg4ajVjcGxoUVlVJTJGUSUzRCUzRA; _gcl_au=1.1.1896058727.1724113533; _hjSessionUser_1177114=eyJpZCI6IjQ5Y2U3ODEzLWNmYTUtNTEwNS04MzliLTRlNjhkNTZlNjkxYiIsImNyZWF0ZWQiOjE3MjQxMTM1MzM1MDcsImV4aXN0aW5nIjp0cnVlfQ==; mh_session=4jqd1l1m01puvz2; mh_employee=; mh_employee_reason=; p4m_snot=3; _hjSession_1177114=eyJpZCI6ImMwNGE4OWUwLTNiYTktNDkyMC04NmFiLTM1MmMwZWU1ZjUwMyIsImMiOjE3MjQxMTkzMDc3NTMsInMiOjEsInIiOjEsInNiIjowLCJzciI6MCwic2UiOjAsImZzIjowLCJzcCI6MH0=; __vads=-fwIGzS0Un18m2ufmCFja06xG; _uetsid=b69c40105e8a11ef82cb4bac85656669; _uetvid=b69c7b905e8a11efb9a169ff75366d56; bclk=5359209766070114; __gads=ID=72138ccf30765566:T=1724119490:RT=1724120241:S=ALNI_MavVXybTWvdd_7doFFsTV_mPiuABA; __gpi=UID=00000ed1650d1248:T=1724119490:RT=1724120241:S=ALNI_MbqkelRAQ3yr3y5JZXlfjHpdqACQQ; __eoi=ID=fb5f6034f6622bc6:T=1724119490:RT=1724120241:S=AA-Afjbo20kwHai69SSry3-wFeMq; token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6MTU1OTA1NSwidGlkIjoxLCJpYXQiOjE3MjQxMjAzMjN9.wUW1f_hVm707-Q138SeQh0IKjqBm2RFQC_3X-qL8QhM; user=eyJpZCI6MTU1OTA1NSwiZ3VpZCI6ImQ3MzI2MTlmLTY0ZWUtNDNiMS05MWFmLTBjMGNiM2YwZWZmZCIsImNybV9pZCI6IjAwMVZqMDAwMDA2V1dSRElBNCJ9; session=eyJmbGFzaCI6e30sInBhc3Nwb3J0Ijp7InVzZXIiOiJ7XCJpZFwiOlwiMTAxMTM0ODcyXCIsXCJ0b2tlblwiOlwiZDczMjYxOWYtNjRlZS00M2IxLTkxYWYtMGMwY2IzZjBlZmZkXCJ9In19; session.sig=lETdHGb9_nCSBZJLv8yflV6Xn2I; mh_status=premium; ens_c1pid=101134872; p4m_inos=29; p4m_inot=43; p4m_sid=1724119303926_3495548763-4206934085-2698965808-617574777%3BTue%20Aug%2020%202024%2007%3A51%3A17%20GMT%2B0500%20(Pakistan%20Standard%20Time)"
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
                elif "neueste Vorstandsmitglieder" ==key.text:
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
            print(f"Individual Threading Reached at ::{index}")
            try:
                plz1=int(obj1["PLZ"])
            except Exception as e:
                plz1=str(obj1["PLZ"])
            if telephone!="":
                telephone=f"'{telephone}'"
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
                "neueste Vorstandsmitglieder":newsetVor,
                "Branche":branche,
                "Firmenzweck":Firmenzweck,
                "UID Number":uidNumber,
                "Rechtsform 2(Extra For Testing)": obj1["Rechtsform"]
            }
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
   


def readCSV(filePath):
    df = pd.read_csv(filePath)

    # Convert each row to a dictionary (header: value) and store them in a list
    rows_list = df.to_dict(orient='records')
    return rows_list
    # # Now you can iterate over the list and access each item by its headers
    # for row in rows_list:
    #     for key, value in row.items():
    #         print(f"{key}: {value}")
    #     print("--- End of Row ---")
def Final_updation_inDB(UpdatedTable,list):
    UpdatedTable.insert_many(list)
    print("Done Insertionion of Updated Database")
def sql_table_to_csv(UpdatedTable ,csv_file_path):
    # Connect to the database
    # db = dataset.connect(f'sqlite:///{db_name}')
    
    # # Retrieve all data from the specified table
    # table = db[table_name]
    rows = list(UpdatedTable.all())  # Convert the iterator to a list of dictionaries
    
    # Convert the list of dictionaries to a pandas DataFrame
    df = pd.DataFrame(rows)
    
    # Save the DataFrame to a CSV file
    df.to_excel(csv_file_path, index=False)
    
    print(f"Data from table '{UpdatedTable}' has been successfully written to '{csv_file_path}'.")

ScrapedData=readCSV("MainMissing.csv")
Main_list=[]
MissingData=[]
with ThreadPoolExecutor(max_workers=50) as executor:
    futures = []
    for index, obj in enumerate(ScrapedData):
        if index>=50000 and index<=83000:
            futures.append(executor.submit(retriveIndividualPages, obj,index))
            # break
    for future in as_completed(futures):
        try:
            result_list = future.result()
            if isinstance(result_list, dict):
                    Main_list.append(result_list)
            if isinstance(result_list, list):
                    MissingData.append(result_list)
        except Exception as e:
            print(f"Error in thread: {e}")
program=13
df = pd.DataFrame(Main_list)
df = df.astype(str)
df.to_csv(f"FinalIndividualPages{program}.csv", index=False)
db = dataset.connect(f'sqlite:///FinalData{program}.db')
UpdatedTable=db['FinalData']
Final_updation_inDB(UpdatedTable,Main_list)
sql_table_to_csv(UpdatedTable,f"FinalData{program}.xlsx")
df1 = pd.DataFrame(MissingData)
df1 = df1.astype(str)
df1.to_csv(f'Missing{program}.csv', index=False)
# print(list1[0]["Url"])