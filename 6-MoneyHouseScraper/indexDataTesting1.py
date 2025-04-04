# here i have apply some debugging to check how many data present in alphabets from a to z
# Alpha Count for a is :: 63764
# Alpha Count for b is :: 48570
# Alpha Count for c is :: 45860
# Alpha Count for d is :: 28936
# Alpha Count for e is :: 29869
# Alpha Count for f is :: 34758
# Alpha Count for g is :: 36733
# Alpha Count for h is :: 29592
# Alpha Count for i is :: 24418
# Alpha Count for j is :: 12453
# Alpha Count for k is :: 22216
# Alpha Count for l is :: 30940
# Alpha Count for m is :: 51194
# Alpha Count for n is :: 16575
# Alpha Count for o is :: 11894
# Alpha Count for p is :: 39869
# Alpha Count for q is :: 2201
# Alpha Count for r is :: 33800
# Alpha Count for s is :: 78288
# Alpha Count for t is :: 31030
# Alpha Count for u is :: 5999
# Alpha Count for v is :: 17259
# Alpha Count for w is :: 18562
# Alpha Count for x is :: 1351
# Alpha Count for y is :: 2631
# Alpha Count for z is :: 8040
# Total Data Set:: 726802 which is most near to my dataset
# As per these test,we can consider there is some other search alphabets or specail charecter which giving additional 5k data,i have also cehck german specail charecter but not successfull
import requests
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

# Base URL for the request
base_url = "https://www.moneyhouse.ch/de/jx/advanced-search-filter-partial"

# Shared list and lock for thread safety
Main_list = []
lock = Lock()  # To protect access to Main_list

def ScrapeUrl(headers, internal_params, legal_form, name_letter):
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
                "SearchLetter": name_letter
            }
            newlist.append(obj)
            print(obj)

        # Return the list of scraped objects
        return newlist

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
    sumcount=0
    alphacount=0
    # Outer loop to iterate over each letter from 'a' to 'z'
    for letter in alphabet:
        alphacount=0
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
                # print(f"Total count: {totalCount} for legalForm={legal_form}, letter={letter}")
                sumcount+=totalCount
                alphacount+=totalCount
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
                        # futures.append(executor.submit(ScrapeUrl, headers, internal_params, legal_form, letter))
                else:
                    print("Bug has been Found")
            else:
                print(f"Request failed for legalForm={legal_form}, letter={letter} with status code: {response.status_code}")
        print(f"Alpha Count for {letter} is :: {alphacount}")
    # Wait for all futures to complete and aggregate results safely
    for future in as_completed(futures):
        try:
            result_list = future.result()
            if isinstance(result_list, list):
                with lock:  # Ensure thread-safe access to the Main_list
                    Main_list.extend(result_list)
        except Exception as e:
            print(f"Error in thread: {e}")

# Convert the aggregated data to a DataFrame and save it to a CSV file
df = pd.DataFrame(Main_list)
df.to_csv('ScrapedData.csv', index=False)
print(sumcount)
