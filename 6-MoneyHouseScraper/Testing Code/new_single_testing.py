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



def retriveIndividualPages(obj1):
    try:
        # base_url="https://www.moneyhouse.ch/de/company/"
        # url = f"{base_url}{obj1['Url']}"
        url="https://www.moneyhouse.ch/de/company/job-schweiz-ag-5197161621"
        # Headers (to mimic a real browser)
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Accept-Language': 'de-DE,de;q=0.9,en;q=0.8',
            'X-Requested-With': 'XMLHttpRequest',
            'Connection': 'keep-alive',
            "cookie": "mh_lifetime=1edan612e8mbyykjhk; __cmpconsent10444=CQTFvHgQTFvHgAfIPBENBvFsAP_gAEPgAAQ4J6pR9G7ebWlHODp3YfsEaYQX11hp4sQhAgCBA6IACBOA8IQG1GAiIAyAJCACABAAoBRBIAFsGAhEAUAAAIAFIBCoQAAAAAAKIGAAAAERQ0AQCAgIAAAgQAAAAABEAhAAgAAACBKIBIAAgIAACgAAAAABAAAAAQIAAAAIQBAAAAIAYAAAEAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAAAAAAACCN4AJBoVEEJRAAIRCBhBAgAEFYQAUCAIAAAgQICAAgQAOAEAFRgIgAAAAAAAAAAAIAAAQAACAAIRABAAACAACAQKAAAAAAACABgAAAAAUAAEAAICAAAIEAAAAAARAAQAIAAAAAQAAAAAAAAAAoAAAAAAAAAAAAAAAAACAAAAAAAAAAAAAAAAAAAAAAAAAAACAA; __cmpcvcu10444=__s2215_c57305_s1574_s866_s1227_s74_c6302_s981_s1642_s1852_c16312_s94_s446_s154_s1052_s40_s64_s73_s3022_s914_s335_s1255_s672_s640_s1259_s1651_s2379_s904_s28_s1989_s2003_s2351_s405_s1932_s457_s65_c10950_s23_s896_s1592_s1898_c56556_c14743_s2294_s571_s1254_s25_s1100_s56_s314_s336_s125_c10951_s239_s127_s7_c10254_c34768_s1656_s573_s1974_s312_s1591_s1655_s1_s26_s2612_s135_s1104_s2723_s2739_s1409_s905_s977_c10089_s46_s10_s24_s161_s1298_s37_s14_s1465_s561_s3118_s1475_c10274_s1442_s2103_c8346_s533_s2688_s2_s1315_c24245_c9657_s1399_s654_s6_s153_c34773_s220_s884_s216_s11_s1049_s322_s1934_s885_s338_s252_s1365_c9211_s1272_c60588_s4_s562_s1358_s741_s267_s883_s1097_c44896_c44894_c7017_s49_s1085_s2546_s2492_s886_s1595_c13897_c11387_s1341_s2369_s460_s1327_s271_s291_s292_c9982_s2522_s188_s191_s1659_c31009_s1658_s193_c35039_s19_s653_s748_c10083_s1068_s462_s1886_s441_s274_c28050_c10013_s2536_s52_s199_s1432_s1657_s1431_c10095_c22002_s605_s203_c9145_s32_s2297_s141_s1777_s1203_s77_s739_s60_c14426_c13900_s21_s679_s34_s67_s35_s3_s30_c10012_s1189_s1618__; __cmpcpcu10444=____; p4m_inot=1; p4m_snot=1; ens_mrcntcmp=; p4m_vid=427221db20435cd97c0a144309c4f8502257b9b7b32b4e207b4e0f4636092c79; _cc_id=16cbce3265c0efac8910ac910fa09b8c; _sharedid=05ef558e-a31b-4441-aae8-53c3fb7e9b46; _sharedid_cst=NCw%2BLJcs4Q%3D%3D; pbjs-unifiedid=%7B%22TDID%22%3A%225be9da22-4874-4640-9426-6f6f9a467aad%22%2C%22TDID_LOOKUP%22%3A%22TRUE%22%2C%22TDID_CREATED_AT%22%3A%222025-06-15T12%3A48%3A58%22%7D; pbjs-unifiedid_cst=NCw%2BLJcs4Q%3D%3D; cto_bidid=61fJa183RVU2c3VKWUp3cGlxQXdSUlBQczlGeGR0VldhbWF3ell4dkF2WmJRTVh5R0NONFBCY3g0eEdyQUh2aUhuOERNd2RUaFpwSFQlMkZRNk1DWmIyQjNLdmZHWVFkeE96TE45elZKYmJBWHpMWllJJTNE; _criteoId=%7B%22criteoId%22%3A%2261fJa183RVU2c3VKWUp3cGlxQXdSUlBQczlGeGR0VldhbWF3ell4dkF2WmJRTVh5R0NONFBCY3g0eEdyQUh2aUhuOERNd2RUaFpwSFQlMkZRNk1DWmIyQjNLdmZHWVFkeE96TE45elZKYmJBWHpMWllJJTNE%22%7D; _criteoId_cst=NCw%2BLJcs4Q%3D%3D; mh_session=f9bnb3wf4mdu6qi3x; session=eyJmbGFzaCI6e319; session.sig=QsAL5IpsbwVXLXHAECwhGVVU_tg; _sp_ses.becb=*; __vads=rd5SLjrubcNFuw-1xsV8AOC_s; panoramaId_expiry=1754739895493; panoramaId=b1c8e448054e53dadb5d753b581e4945a70257f982097a444aa3a19955c5839d; panoramaIdType=panoIndiv; cto_bundle=whtu6F9ibXM5Nm9mbmpBRlBYOWVvOHRnNm1QQVA1aVZ1d3ZmQmZ5JTJGWW5VdDNIanJlUFh3dmpHeSUyRml4c3N3dURRc3BQTG5XM2o3cG9VRTFITXVyT29ieW5TdnVoMThxNGE4cGhEamVraXQlMkJocWlkeGtjRG1NOWpwdjFMSnNNMlVCVWs0WDkweWRUamNvdTBPUmphclBDUHloNVQ0c1ZidGE1V0VKTFh0M2hLcXMySmMlM0Q; __gads=ID=af3a05297f3b417e:T=1750070143:RT=1754135800:S=ALNI_MYl_HHFQ9ULoYgV-1eXchxOQz9MAg; __gpi=UID=000011305e493c0a:T=1750070143:RT=1754135800:S=ALNI_MaDnhfpDNKIIOxEebT2t9eHk6axRA; __eoi=ID=593a7767b288a491:T=1750070143:RT=1754135800:S=AA-AfjZr0HjpRGYYY67VUeVKyMTZ; _sp_id.becb=c07cfa08-d4ee-4a4d-b5cc-5426e0c428aa.1750070139.22.1754135804.1753724122.6ad19506-98c1-4b6d-8de1-a36b916cbada.94854ed0-fb1e-461b-bd64-6baa70c45637.8e98a36c-84e2-4b85-808d-c5e6df4dafb7.1754135086066.24"
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
                # print(key)
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
                    print(newsetVor)
                elif "neuste Zeichnungsberechtigte" ==key.text:
                    newsetZei=key.find_next_sibling('p').text
                 
                
            # # print(Alter_der_Firma,Umsatz_in_CHF,Mitarbeiter,Rechtsform)
            # connection_rows=soup.find_all("div",class_="connections-row")
            # # 
            # for connection in connection_rows:
            #     check=connection.find("a").get("href")
            #     if "tel:" in check:
            #         telephone=connection.find("a").text
            #     elif "mailto:" in check:
            #         Email=connection.find("a").text
            #     else:
            #         website=connection.find("a").text
            # # print(telephone,Email,website)
            # allH2=soup.find_all("h2")
            # # pattern = r"^Management(?: \((\d*)\))?$"
            # # for h2 in allH2:
            # #     if re.fullmatch(pattern, h2.text):
            # #         section=h2.find_next_sibling('div', class_='section')
            # #         if section:
            # #             Management_Para=section.find("p")
            # #             if Management_Para:
            # #                 Management=Management_Para.text
            # #             # print(f"Management is:{Management}")
            # script_tag = soup.find('script', {'type': 'application/ld+json'})
            
            # if script_tag:
            #     # Load the content as JSON
            #     json_content = json.loads(script_tag.string)
            #     if json_content:
            #         # Extract the 'description' field
            #         Firmenzweck = json_content.get("description", "Description not found")
                    
            #         # print("Firmenzweck:", Firmenzweck)
            # branche_ele=soup.find('div',class_="branch overview-branch-holder")
            # if branche_ele:
            #     branche=branche_ele.text.replace("Branche:","").strip()
            # uidNumber_ele=soup.find('div',class_="chnr")
            # if uidNumber_ele:
            #     uidNumber=uidNumber_ele.get_text().replace("Handelsregister-Nr.:&nbsp", "").strip()
            # if Rechtsform=="":
            #     Rechtsform_ele=soup.find("div",class_="company-legal-form company-info-block")
            #     if Rechtsform_ele:
            #         Rechtsform=Rechtsform_ele.text.replace("Rechtsform:","").strip()
            # Kanton=obj1["state"]
            # if Kanton=="nan":
            #     Kanton_ele=soup.find("div",class_="company-canton company-info-block")
            #     if Kanton_ele:
            #         Kanton=Kanton_ele.text.replace("Rechtsform:","").strip()
            # # print(f"branche is ::{branche}")
            # print(f"Individual Threading Reached at ::{obj1['id']}")
            # try:
            #     plz1=int(obj1["PLZ"])
            # except Exception as e:
            #     plz1=str(obj1["PLZ"])
            # if telephone!="":
            #     telephone=f"'{telephone}'"
            # obj2={
            #     "Url": url,
            #     "Name": obj1["Name"],
            #     "Kanton": Kanton,
            #     "Rechtsform": Rechtsform,
            #     "Alter":Alter_der_Firma,
            #     "Umsatz": Umsatz_in_CHF,
            #     "Mitarbeiter":f"'{Mitarbeiter}'",
            #     "Adresse": obj1["Adresse"],
            #     "PLZ": plz1,
            #     "ORT":obj1["ORT"],
            #     "Telefonnummer":telephone,
            #     "Webseite":str(website),
            #     "Emailadresse":str(Email),
            #     # "Management":str(Management),
            #     "Geschäftsleitung":managment1,
            #     "neuste Zeichnungsberechtigte": newsetZei,
            #     "neueste Vorstandsmitglieder":newsetVor,
            #     "Branche":branche,
            #     "Firmenzweck":Firmenzweck,
            #     "UID Number":uidNumber,
            #     "Rechtsform 2(Extra For Testing)": obj1["Rechtsform"]
            # }
            # return obj2
        else:
            values_list = list(obj1.values())
            print(f"Failed to retrieve the page. Status code: {response.status_code}")
            return values_list
    except Exception as e:
        print("Exception has been Occur",e)
        values_list = list(obj1.values())
        traceback.print_exc()
        return values_list
    
retriveIndividualPages("")