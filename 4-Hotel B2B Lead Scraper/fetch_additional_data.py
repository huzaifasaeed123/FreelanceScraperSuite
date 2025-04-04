import requests
from bs4 import BeautifulSoup
import json
from bs4 import BeautifulSoup
import time
from urllib.parse import urlparse
import dataset
import pandas as pd

# proxy = "198.204.241.50:17047"
# proxies = {
#     "http": f"http://{proxy}",
#     "https": f"http://{proxy}"
# }
# Define the headers
Main_list=[]
def list_to_csv(data_list, output_filename):
    
    # Convert list of dictionaries to pandas DataFrame
    df = pd.DataFrame(data_list)
    
    # Save DataFrame to CSV
    df.to_csv(output_filename, index=False)

def Scrape_Hotel_list(url,headers,session):
    # Make the request using the session
    response = session.get(url, headers=headers)

    # Check if the request was successful
    if response.status_code == 200:
        # Parse the content with BeautifulSoup
        soup = BeautifulSoup(response.content, 'html.parser')

        # Write the entire soup content to a text file
        # with open('soup_content3.txt', 'w', encoding='utf-8') as file:
        #     file.write(soup.prettify())

        # Find the first <script> tag of type application/ld+json
        script_tag = soup.find('script', type='application/ld+json')

        # Load the JSON data from the <script> tag
        json_data = json.loads(script_tag.string)

        # Extract and print the required information
        for agent in json_data:
            try:
                print("Inside Hotel List Request Individual")
                name = agent.get('name')
                url_hotel = agent.get('url')
                phone_Number = agent.get('telephone')
                address = agent.get('address', {})
                street_address = address.get('streetAddress')
                locality = address.get('addressLocality')
                region = address.get('addressRegion')
                postal_code = address.get('postalCode')
                country = address.get('addressCountry', {}).get('name')
                id=agent.get('@id')
                parsed_url = urlparse(id)
                # Split the path and extract the desired segment
                path_segments = parsed_url.path.split('/')
                id = path_segments[3]
                # Hotel_personal_website=Scrap_Personal_hotel_website(url_hotel,headers,session)
                # LeaderShipTeam=Scrap_Leadership_profile(session,id)
                data={
                    "id":id,
                    "Business_Name":name,
                    "street_address":street_address,
                    "Adress_locality":locality,
                    "Address_region":region,
                    "postal_code":postal_code,
                    "country":country,
                    "Phone_Number":phone_Number,
                    #"Local_Website":Hotel_personal_website,
                    "Buisness_Profile":url_hotel,
                    #"LeaderShipTeam":LeaderShipTeam
                }
                Main_list.append(data)
            except Exception as e:
                print(f"Exception has occur for following lisnk::{agent}")
    else:
        print(f"Failed to retrived Main pageand status code is:{response.status_code}")


def Scrap_Leadership_profile(session,id):
    payload = {
    "operationName": "getOfficeTeam",
    "query": """query getOfficeTeam($affiliate: String, $id: String!, $language: String!, $channel: String!, $page: String, $pageResults: String, $sortSeo: String, $cookies: String, $ajaxTarget: String) {
                  getOfficeTeam(affiliate: $affiliate, id: $id, language: $language, channel: $channel, page: $page, pageResults: $pageResults, sortSeo: $sortSeo, cookies: $cookies, ajaxTarget: $ajaxTarget) {
                    page, listingtotal, listingtotalall, ChannelKey, pagetotal, perpage, agents {agentId, name, Agent1NameFirst, Agent1Name, agenttitle, photo, nophotourl, phones {decrypted, name, __typename}, seoname, isteam, __typename}, __typename
                  }
                }""",
    "variables": {
        "id": id, "language": "eng", "channel": "leadership", 
        "sortSeo": "team-leader-sort", "ajaxTarget": "brokertabsdata_1", 
        "cookies": "4c605a2a-5858-41e0-a805-855ff7db611d|NEW"
    }
}       
    headers1 = {
    "authority": "middleware.sothebysrealty.com",
    "method": "POST",
    "path": "/graphql",
    "scheme": "https",
    "Accept": "*/*",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Accept-Language": "en-US,en;q=0.9",
    "Content-Length": str(len(json.dumps(payload))),  # Calculate content length
    "Content-Type": "application/json",
    "Origin": "https://www.sothebysrealty.com",
    "Priority": "u=1, i",
    "Referer": "https://www.sothebysrealty.com/eng/office/180-b-5084-4001306/premier-sothebys-international-realty-asheville",
    "Sec-Ch-Ua": "\"Not/A)Brand\";v=\"8\", \"Chromium\";v=\"126\", \"Microsoft Edge\";v=\"126\"",
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": "\"Windows\"",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-site",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 Edg/126.0.0.0"
}
    url="https://middleware.sothebysrealty.com/graphql"
    response = session.post(url, headers=headers1, data=json.dumps(payload))

        # Check the response
    if response.status_code == 200:
        print("Request was successful! For Leadership Profiles")
        json_data=response.json()
          # Print the JSON response
        agents = json_data['data']['getOfficeTeam']['agents']
        list=[]
        for agent in agents:
            try:
                agent_id = agent['agentId']
                name = agent['name']
                agent_title = agent['agenttitle']
                seoname = agent['seoname']
                
                # print(f"Agent ID: {agent_id}")
                # print(f"Name: {name}")
                # print(f"Agent Title: {agent_title}")
                make_url=f"https://www.sothebysrealty.com/eng/associate/{agent_id}/{seoname}"
                Email=Scrap_Email(make_url,headers,session)
                Personal_Website=Scrap_Personal_hotel_website(make_url,headers,session)
                
                # Extract and print phone numbers
                phones = agent['phones']
                phoneNum0=phoneNum1=None
                if len(phones) > 0:
                    phone_0 = phones[0]
                    phoneNum0=phone_0['decrypted']
                    #print(f"Phone ({phone_0['name']}): {phone_0['decrypted']}")
                else:
                    phoneNum0="Not Available"
                
                if len(phones) > 1:
                    phone_1 = phones[1]
                    phoneNum1=phone_1['decrypted']
                    #print(f"Phone ({phone_1['name']}): {phone_1['decrypted']}")
                else:
                    phoneNum1="Not Available"
                
                data={
                    "id":id,
                    "name":name,
                    "title":agent_title,
                    "mobile_No":phoneNum0,
                    "primary_No":phoneNum1,
                    "Email":Email,
                    "Profile_WebPage_url":make_url,
                    "Personal_WebPage":Personal_Website
                }
                list.append(data)
            except Exception as e:
                print(f"Exception has occur in leadership Profiles::{agent}")
        
        return list

    else:
        print(f"Failed to retrieve the data. Status code: {response.status_code}")
        print(response.text)
def Scrap_Email(url,headers,session):
    response=session.get(url,headers=headers)
    if response.status_code == 200:
        soup = BeautifulSoup(response.content, 'html.parser')

        # Find the <div> with class "GetInTouch__agent-emailvCard"
        email_div = soup.find('div', class_='GetInTouch__agent-emailvCard')

        if email_div:
            # Find the <a> tag within the <div>
            email_link = email_div.find('a', href=True)
            
            if email_link:
                # Extract the email address from the href attribute
                email = email_link['href'].replace('mailto:', '')
                return email
            else:
                print("No <a> tag with href found within the <div>.")
                return "No Email Found"
        else:
            print("No <div> element with class 'GetInTouch__agent-emailvCard' found.")
            return "No Email Found"
    else:
        print(f"Failed to retrieve the Email. Status code: {response.status_code}")

def Scrap_Personal_hotel_website(url,headers,session):
    response=session.get(url,headers=headers)
    if response.status_code == 200:
            # Parse the content with BeautifulSoup
        soup = BeautifulSoup(response.content, 'html.parser')
        networks_ul = soup.find('ul', class_='Networks')
        #print(networks_ul)
            # Ensure that the <ul> element exists
        if networks_ul:
                # Find the first <li> element within the <ul>
            first_li = networks_ul.find_all('li', class_='Networks__item')
                
                # Ensure that the <li> element exists
            if len(first_li) == 2 or len(first_li) == 3 or len(first_li) > 3:
            # Find the <a> tag within the first <li> element
                first_a_tag = first_li[0].find('a', class_='Networks__link')
            
            # Ensure that the <a> tag exists and get its href attribute
                if first_a_tag and 'href' in first_a_tag.attrs:
                    link = first_a_tag['href']
                    #print(f"Personal Hotel Website Link: {link}")
                    return link
                    
                else:
                    print("No <a> tag with class 'Networks__link' found within the first <li> element.")
            else:
                print("Personal website Link For Leaedership Team Member not found")
                return "Personal Link Not Found"
        else:
            print("No <ul> element with class 'Networks' found.")
    else:
        print(f"Failed to retrieve the Scrap_Personal_hotel_website. Status code: {response.status_code}")
# def save_to_db(main_list):
#     db = dataset.connect('sqlite:///hotels.db')

#     # Create tables
#     db.query('''CREATE TABLE IF NOT EXISTS offices (
#                     id TEXT PRIMARY KEY,
#                     Business_Name TEXT,
#                     street_address TEXT,
#                     Adress_locality TEXT,
#                     Address_region TEXT,
#                     postal_code TEXT,
#                     country TEXT,
#                     Phone_Number TEXT,
#                     Local_Website TEXT,
#                     Buisness_Profile TEXT
#                 )''')

#     db.query('''CREATE TABLE IF NOT EXISTS leaders (
#                     id INTEGER PRIMARY KEY AUTOINCREMENT,
#                     office_id TEXT,
#                     name TEXT,
#                     title TEXT,
#                     mobile_No TEXT,
#                     primary_No TEXT,
#                     Email TEXT,
#                     Profile_WebPage_url TEXT,
#                     Personal_WebPage TEXT,
#                     FOREIGN KEY(office_id) REFERENCES offices(id)
#                 )''')

#     for entry in main_list:
#         office_data = {
#             "id": entry["id"],
#             "Business_Name": entry["Business_Name"],
#             "street_address": entry["street_address"],
#             "Adress_locality": entry["Adress_locality"],
#             "Address_region": entry["Address_region"],
#             "postal_code": entry["postal_code"],
#             "country": entry["country"],
#             "Phone_Number": entry["Phone_Number"],
#             "Local_Website": entry["Local_Website"],
#             "Buisness_Profile": entry["Buisness_Profile"]
#         }
#         db['offices'].upsert(office_data, ['id'])

#         for leader in entry["LeaderShipTeam"]:
#             leader_data = {
#                 "office_id": entry["id"],
#                 "name": leader["name"],
#                 "title": leader["title"],
#                 "mobile_No": leader["mobile_No"],
#                 "primary_No": leader["primary_No"],
#                 "Email": leader["Email"],
#                 "Profile_WebPage_url": leader["Profile_WebPage_url"],
#                 "Personal_WebPage": leader["Personal_WebPage"]
#             }
#             db['leaders'].insert(leader_data)

# def export_to_csv():
#     db = dataset.connect('sqlite:///hotels.db')

#     office_df = pd.DataFrame(db['offices'].all())
#     leader_df = pd.DataFrame(db['leaders'].all())

#     office_df.to_csv('offices.csv', index=False)
#     leader_df.to_csv('leaders.csv', index=False)

def save_to_db(main_list):
    db = dataset.connect('sqlite:///hotels.db')

    # Create tables
    db.query('''CREATE TABLE IF NOT EXISTS offices (
                    id TEXT PRIMARY KEY,
                    Business_Name TEXT,
                    street_address TEXT,
                    Adress_locality TEXT,
                    Address_region TEXT,
                    postal_code TEXT,
                    country TEXT,
                    Phone_Number TEXT,
                    Local_Website TEXT,
                    Buisness_Profile TEXT
                )''')

    db.query('''CREATE TABLE IF NOT EXISTS leaders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    office_id TEXT,
                    name TEXT,
                    title TEXT,
                    mobile_No TEXT,
                    primary_No TEXT,
                    Email TEXT,
                    Profile_WebPage_url TEXT,
                    Personal_WebPage TEXT,
                    FOREIGN KEY(office_id) REFERENCES offices(id)
                )''')

    for entry in main_list:
        office_data = {
            "id": entry["id"],
            "Business_Name": entry["Business_Name"],
            "street_address": entry["street_address"],
            "Adress_locality": entry["Adress_locality"],
            "Address_region": entry["Address_region"],
            "postal_code": entry["postal_code"],
            "country": entry["country"],
            "Phone_Number": entry["Phone_Number"],
            "Local_Website": entry["Local_Website"],
            "Buisness_Profile": entry["Buisness_Profile"]
        }
        db['offices'].upsert(office_data, ['id'])

        for leader in entry["LeaderShipTeam"]:
            leader_data = {
                "office_id": entry["id"],
                "name": leader["name"],
                "title": leader["title"],
                "mobile_No": leader["mobile_No"],
                "primary_No": leader["primary_No"],
                "Email": leader["Email"],
                "Profile_WebPage_url": leader["Profile_WebPage_url"],
                "Personal_WebPage": leader["Personal_WebPage"]
            }
            db['leaders'].insert(leader_data)

def export_joined_data_to_csv():
    db = dataset.connect('sqlite:///hotels.db')

    # SQL query to join the offices and leaders tables
    query = '''
    SELECT
        o.id AS office_id,
        o.Business_Name,
        o.street_address,
        o.Adress_locality,
        o.Address_region,
        o.postal_code,
        o.country,
        o.Phone_Number AS Office_Phone_Number,
        o.Local_Website,
        o.Buisness_Profile,
        l.name AS Leader_Name,
        l.title AS Leader_Title,
        l.mobile_No AS Leader_Mobile_No,
        l.primary_No AS Leader_Primary_No,
        l.Email AS Leader_Email,
        l.Profile_WebPage_url AS Leader_Profile_WebPage,
        l.Personal_WebPage AS Leader_Personal_WebPage
    FROM
        offices o
    LEFT JOIN
        leaders l
    ON
        o.id = l.office_id
    '''

    result = db.query(query)
    result_df = pd.DataFrame(result)

    # Export the result to a single CSV file
    result_df.to_csv('joined_data.csv', index=False)
headers = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,/;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "max-age=0",
    "Cookie": "_gcl_au=1.1.1521752300.1719180735; _gid=GA1.2.1259318958.1719180735; _fbp=fb.1.1719180735384.735425129121416645; notice_preferences=2:; notice_gdpr_prefs=0,1,2:; cmapi_gtm_bl=; cmapi_cookie_privacy=permit 1,2,3; _ga_PC49B06VQR=GS1.1.1719181436.4.0.1719181436.0.0.0; _ga_N4QYX2W6ZC=GS1.1.1719181436.2.0.1719181436.0.0.0; LanguagePreference=eng; Currency=USD; notice_behavior=implied,eu; lastSearchLocation=int; allSeoLocations=%5B%7B%22name%22%3A%22All%20locations%22%2C%22idregion%22%3A%22-1%22%2C%22seo%22%3A%22int%22%2C%22level%22%3A%22International%22%2C%22countryiso3%22%3Anull%2C%22stateiso2%22%3Anull%2C%22lng%22%3A%22-4%22%2C%22lat%22%3A%2244%22%2C%22__typename%22%3A%22LocationsModule%22%7D%5D; userLocationName=; userLocation=int; ASP.NET_SessionId=z1w30y23gzdulq2pjjyqrfxc; _ga_DZ1NB496EH=GS1.1.1719268642.1.1.1719269716.0.0.0; _ga_BS92M94N9R=GS1.1.1719268701.1.1.1719269716.0.0.0; _ga_0QLKQS5MQZ=GS1.1.1719268761.1.1.1719269718.0.0.0; _ga_NNJSZ4YQ6X=GS1.1.1719330416.2.1.1719330501.0.0.0; currentSearchQuery=int%2F180-a-828-4014123-agentid; _ga_07J12X0FK6=GS1.1.1719348995.5.1.1719352036.0.0.0; _ga_T4VSWQZ89K=GS1.1.1719351094.1.1.1719352036.0.0.0; _ga=GA1.2.301310539.1719157283; _ga_0LDHHV8QEH=GS1.1.1719353885.20.0.1719353885.0.0.0; aws-waf-token=3b0b5532-5d1c-4dc9-98bc-fdd5c35bce1f:EQoAYb2bgpU6AAAA:Rr9R3gvTmIT0VNmXZcAK3jQgZF3xYD3qDjp0ZSLfi5A5qRTgw9keGHX9C81xFrsjDN9Ease+LJkaT+MiuEyh2l9hENcGKGtQpoWpYbvXMGx+XVWjvhH/nVAi2ozbM6M2b+WJKOTkrFrenQCd2c5BFc4+l+73iaQs/AF+2ob6XB6bxj79oXnca0OdtGSgLkBb9aCax0vYstan3QXYismTMHQ0Vs/bFf5Ln8V3p55blCfnyf4vOKF4ebHR0Q==",
    "If-None-Match": "\"54d10-VfYuf5L+eho+DdnhVGZekgtieSo\"",
    "Priority": "u=0, i",
    "Referer": "https://www.sothebysrealty.com/eng/offices  /int/",
    "Sec-Ch-Ua": "\"Not/A)Brand\";v=\"8\", \"Chromium\";v=\"126\", \"Google Chrome\";v=\"126\"",
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": "\"Windows\"",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
}

# URL to scrape

# Create a session object
session = requests.Session()
 # Read the input CSV file
df = pd.read_csv("result.csv")

# Initialize an empty list to collect the output rows
output_rows = []

# Iterate over each row in the input DataFrame
for index, row in df.iterrows():
    # Extract the URL and ID from the specified columns
    url_hotel = row["Buisness_Profile"]
    id_value = row["id"]

    # Call the scraping functions
    Hotel_personal_website = Scrap_Personal_hotel_website(url_hotel, headers, session)
    LeaderShipTeam = Scrap_Leadership_profile(session, id_value)

    # Prepare the base data for the current row
    base_data = row.to_dict()
    base_data['Hotel_personal_website_link'] = Hotel_personal_website

    # If there are leadership team members, create multiple rows
    if LeaderShipTeam:
        for leader in LeaderShipTeam:
            combined_data = {**base_data, **leader}
            output_rows.append(combined_data)
    else:
        # If no leadership team members, add the base data as is
        output_rows.append(base_data)

# Convert the output rows to a DataFrame
output_df = pd.DataFrame(output_rows)

# Save the output DataFrame to a new CSV file
output_df.to_csv("AdditonalData.csv", index=False)

# Hotel_personal_website=Scrap_Personal_hotel_website(url_hotel,headers,session)
LeaderShipTeam=Scrap_Leadership_profile(session,id)
# for i in range(1, 76):
#     if i==1:
#         url="https://www.sothebysrealty.com/eng/offices/int"
#     else:
#         url = f'https://www.sothebysrealty.com/eng/offices/int/{i}-pg'
    
#     print(f"Page No::{i}")
#     Scrape_Hotel_list(url,headers,session)


# list_to_csv(Main_list,"OveralIds")
# # Save data to SQLite
# save_to_db(Main_list)

# # Export data to CSV
# #export_to_csv()
# export_joined_data_to_csv()

# # Make the request using the session
# response = session.get(url, headers=headers)

# # Check if the request was successful
# if response.status_code == 200:
#     # Parse the content with BeautifulSoup
#     soup = BeautifulSoup(response.content, 'html.parser')

#     # Write the entire soup content to a text file
#     with open('soup_content3.txt', 'w', encoding='utf-8') as file:
#         file.write(soup.prettify())

#     # Find the first <script> tag of type application/ld+json
#     script_tag = soup.find('script', type='application/ld+json')

#     # Load the JSON data from the <script> tag
#     json_data = json.loads(script_tag.string)

#     # Extract and print the required information
#     for agent in json_data:
#         name = agent.get('name')
#         url = agent.get('url')
#         address = agent.get('address', {})
#         street_address = address.get('streetAddress')
#         locality = address.get('addressLocality')
#         region = address.get('addressRegion')
#         postal_code = address.get('postalCode')
#         country = address.get('addressCountry', {}).get('name')
        
       
#         # Write the entire soup content to a text file
#         with open('htm3ndcontent.html', 'w', encoding='utf-8') as file:
#             file.write(soup.prettify())

#         payload = {
#     "operationName": "getOfficeTeam",
#     "query": """query getOfficeTeam($affiliate: String, $id: String!, $language: String!, $channel: String!, $page: String, $pageResults: String, $sortSeo: String, $cookies: String, $ajaxTarget: String) {
#                   getOfficeTeam(affiliate: $affiliate, id: $id, language: $language, channel: $channel, page: $page, pageResults: $pageResults, sortSeo: $sortSeo, cookies: $cookies, ajaxTarget: $ajaxTarget) {
#                     page, listingtotal, listingtotalall, ChannelKey, pagetotal, perpage, agents {agentId, name, Agent1NameFirst, Agent1Name, agenttitle, photo, nophotourl, phones {decrypted, name, __typename}, seoname, isteam, __typename}, __typename
#                   }
#                 }""",
#     "variables": {
#         "id": "180-b-5084-4001306", "language": "eng", "channel": "leadership", 
#         "sortSeo": "team-leader-sort", "ajaxTarget": "brokertabsdata_1", 
#         "cookies": "4c605a2a-5858-41e0-a805-855ff7db611d|NEW"
#     }
# }       
#         headers1 = {
#     "authority": "middleware.sothebysrealty.com",
#     "method": "POST",
#     "path": "/graphql",
#     "scheme": "https",
#     "Accept": "*/*",
#     "Accept-Encoding": "gzip, deflate, br, zstd",
#     "Accept-Language": "en-US,en;q=0.9",
#     "Content-Length": str(len(json.dumps(payload))),  # Calculate content length
#     "Content-Type": "application/json",
#     "Origin": "https://www.sothebysrealty.com",
#     "Priority": "u=1, i",
#     "Referer": "https://www.sothebysrealty.com/eng/office/180-b-5084-4001306/premier-sothebys-international-realty-asheville",
#     "Sec-Ch-Ua": "\"Not/A)Brand\";v=\"8\", \"Chromium\";v=\"126\", \"Microsoft Edge\";v=\"126\"",
#     "Sec-Ch-Ua-Mobile": "?0",
#     "Sec-Ch-Ua-Platform": "\"Windows\"",
#     "Sec-Fetch-Dest": "empty",
#     "Sec-Fetch-Mode": "cors",
#     "Sec-Fetch-Site": "same-site",
#     "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 Edg/126.0.0.0"
# }
#         url="https://middleware.sothebysrealty.com/graphql"
#         response = session.post(url, headers=headers1, data=json.dumps(payload))

#         # Check the response
#         if response.status_code == 200:
#             print("Request was successful!")
#             print(response.json())  # Print the JSON response
#         else:
#             print(f"Failed to retrieve the data. Status code: {response.status_code}")
#             print(response.text)
        
        
#         # print(f"Name: {name}")
#         # print(f"URL: {url}")
#         # print(f"Address: {street_address}, {locality}, {region}, {postal_code}, {country}")
#         # print("-" * 40)
#         break

# else:
#     print(f"Failed to retrieve the page. Status code: {response.status_code}")