import requests
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from alive_progress import alive_bar
# URL of the service
def getsingleRequest(payload,headers,page):
    try:
        url = 'https://www.ambitionbox.com/servicegateway-ambitionbox/company-services/v0/listing/cards/search'
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code == 200:
            # Parse the JSON response
            data = response.json()
            cards= data["cards"]
            for card in cards:
                name=urlName=shortName=shortName=logoUrl=reviewCount=salariesCount=interviewsCount=jobsCount=benefitsCount=photosCount=newsCount=qnaQuestionsCount=""
                primaryIndustry=totalEmployeesIndia=totalEmployees=companyRating=topLocationDetail=tag=""
                name=card["name"]
                urlName=card["urlName"]
                shortName=card["shortName"]
                companyId=card["companyId"]
                logoUrl=card["logoUrl"]
                reviewCount=card["reviewCount"]
                salariesCount=card["salariesCount"]
                interviewsCount=card["interviewsCount"]
                jobsCount=card["jobsCount"]
                benefitsCount=card["benefitsCount"]
                photosCount=card["photosCount"]
                newsCount=card["newsCount"]
                qnaQuestionsCount=card["qnaQuestionsCount"]
                primaryIndustry=card["primaryIndustry"]
                totalEmployeesIndia=card["totalEmployeesIndia"]
                totalEmployees=card["totalEmployees"]
                companyRating=card["companyRating"]
                if card["topLocationDetail"]:
                    topLocationDetail=card["topLocationDetail"]["name"]
                if card["tag"]:
                    tag=card["tag"]["Name"]
                highelyRatings=card["highlyRatedFor"]
                Company_Culture=Work_Life_Balance=Work_Satisfaction=Job_Security=Promotions_Appraisal=Skill_Development_Learning=Salary_Benefits="Not Found"
                for single in highelyRatings:
                    if single['name']=="Company Culture":
                        Company_Culture=single["ratings"]
                    elif single['name']=="Work Life Balance":
                        Work_Life_Balance=single["ratings"]
                    elif single['name']=="Work Satisfaction":
                        Work_Satisfaction=single["ratings"]
                    elif single['name']=="Job Security":
                        Job_Security=single["ratings"]
                    elif single['name']=="Promotions / Appraisal":
                        Promotions_Appraisal=single["ratings"]
                    elif single['name']=="Skill Development / Learning":
                        Skill_Development_Learning=single["ratings"]
                    elif single['name']=="Salary & Benefits":
                        Salary_Benefits=single["ratings"]
                obj={
                    "Name":name,
                    "Uri Name": urlName,
                    "Short Name": shortName,
                    "Company ID": companyId,
                    "Url Logo":logoUrl,
                    "Review Count": reviewCount,
                    "Salieries Count":salariesCount,
                    "Interviews Count": interviewsCount,
                    "Jobs Count": jobsCount,
                    "Benefit Count": benefitsCount,
                    "Photos Count": photosCount,
                    "News Count": newsCount,
                    "Qna Questions Count": qnaQuestionsCount,
                    "primaryIndustry": primaryIndustry,
                    "Indian Employees": totalEmployeesIndia,
                    "Total Employees": totalEmployees,
                    "City":topLocationDetail,
                    "Type": tag,
                    "Company Overall Rating": companyRating,
                    "Company_Culture (Rating)":Company_Culture,
                    "Work_Life_Balance (Rating)": Work_Life_Balance,
                    "Work_Satisfaction (Rating)":Work_Satisfaction,
                    "Job_Security (Rating)": Job_Security,
                    "Promotions_Appraisal (Rating)":Promotions_Appraisal,
                    "Skill_Development_Learning (Rating)":Skill_Development_Learning,
                    "Salary_Benefits (Rating)":Salary_Benefits,
                }
                # Main_list.append(obj)
                return obj
            print(f'Page {page}: Retrieved')
            
            # Here, you could process or store the data as needed
        else:
            print(f'Failed to fetch data for page {page}. Status code: {response.status_code}')
    except Exception as e:
        print(f"Page is : {page}")
        print(f"Exception has been occue as : {e}")
    # break
def getRequestCount(payload):
    url_Search="https://www.ambitionbox.com/servicegateway-ambitionbox/company-services/v0/listing/filters/search"
    headers = {
                "Accept": "application/json, text/plain, */*",
                "Accept-Encoding": "gzip, deflate, br, zstd",
                "Accept-Language": "en-US,en;q=0.9",
                "Appid": "901",
                "Content-Length": "264",
                "Content-Type": "application/json",
                # "Cookie": "_t_ds=a3830eb81723760522-39a3830eb8-0a3830eb8; showChatbot=y; ak_bmsc=5763FCFDD7C0858C612AE0E03B00AE85~000000000000000000000000000000~YAAQm+JIF9vUJpmRAQAAeZBuvBlPuN33p3brV9m3PxwoXaC/bznMvl6Yx5CT4zjzkDV34riApHb89vIp3l0Nkzw03aKYs2BkRxKK0VOHXrBtIzAHxTP2AcWxQSEMga/63sp1F3wbAUkQ0KJnTswImPCXk3cx2144VLucghWdPyCDh09szGoEO5zS6K75QncNxiqsLZhxXUIgI7XXC1r83L4E0xqHxvqb+uJfOLngB+d7mmy267lsSE7jGuPHre0NfC5Xesfm52WF3MibFJRUja5ia22aBSXYVLzWukNCCWUGWnu3H559cHciAqekraXzSJ/gY3RwL2CesK18jzKFZKZBzxy283UmjPVIdGnvifTa9qZ6uOW2dX7TuC5EhCNNTEGVLp7rs/Aqk5JesyEFmsqIDMYXdM1DExbvzIUdOi46ObPXPR0ItjaJqlKoQUTJCLCe0e/gZ+NyNXhguBvmBRWJBg==; PHPSESSID=2c88aed804adb3d2348fb1190e5beefd; _gid=GA1.2.1342657428.1725449210; _ga=GA1.1.18927355.1723760594; ums=6e6f74616d656d626572; _ga_HV7DJVVBCW=GS1.1.1725447255.10.1.1725449620.60.0.0; bm_sv=8683F80F79001243A33D8F498AE80F73~YAAQm+JIF1d9J5mRAQAACsnPvBl+XxG1eBKSLnEg0LVddIm64U3bVkzJLoh2pnFgb94G8O63qvVVpAinaSFaFIigBYnCZNO37bd2tayhTlgiO+k7lboGJZ1bPZl8qj75HxPJZ0FjXXS+/xlKNZxhaAY2zkbDXOragLBKJWCLbGkFJUFU2+QC393M/w26Je4Opd03MTNkZFxyKKFmj/vhQAp75UkWjYCx6y8HGGYDemKk5hnpYn4dqJ1xJ/b5ZYuT4X/M/RDvCQ==~1",
                "Origin": "https://www.ambitionbox.com",
                "Priority": "u=1, i",
                "Referer": "https://www.ambitionbox.com/list-of-companies?knownFor=company-culture&locations=new-delhi&ratings=3.75&sortBy=popular&globalEmployeeCounts=1001-5000,501-1000,100001,50001-100000,10001-50000,5001-10000,201-500,51-200,11-50,1-10",
                "Sec-CH-UA": '"Chromium";v="128", "Not;A=Brand";v="24", "Google Chrome";v="128"',
                "Sec-CH-UA-Mobile": "?0",
                "Sec-CH-UA-Platform": '"Windows"',
                "Sec-Fetch-Dest": "empty",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Site": "same-origin",
                "Systemid": "loc",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
            }
    response_Search = requests.post(url_Search, json=payload, headers=headers)
    if response_Search.status_code == 200:
        data = response_Search.json()
        return data["filterData"]
    else:
        print(f"request Is not Successfull::{response_Search.status_code}")

# Common headers
headers = {
    'accept': 'application/json, text/plain, */*',
    'accept-encoding': 'gzip, deflate, br, zstd',
    'accept-language': 'en-US,en;q=0.9',
    'appid': '901',
    'content-type': 'application/json',
    'origin': 'https://www.ambitionbox.com',
    'referer': 'https://www.ambitionbox.com/list-of-companies?knownFor=company-culture&sortBy=popular&ratings=4.5',
    'sec-ch-ua': '"Not)A;Brand";v="99", "Google Chrome";v="127", "Chromium";v="127"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'same-origin',
    'systemid': 'loc',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36',
    # 'cookie': '_t_ds=a3830eb81723760522-39a3830eb8-0a3830eb8; _ga=GA1.1.18927355.1723760594; showChatbot=y; ak_bmsc=A79681A4B34394A5B9AA5DAB42DB0FC4~000000000000000000000000000000~YAAQfqUQAu4qHWGRAQAARL3wcRikrYN2MOYbUoI/UfZih4n4Sq0OLihe8oXwuI/8d7Qse2SuL52Zid5fpbGuybj4sOPqAYl9vsMJ/x9fayi4A20Qrec+acQesZn+XJ2Mzx+j4i0+Owgj0fziOUzLdTWWbGj70btyGnagiQdBJVp9uUo+NzE1jLCcMf9SnirrCdNGy2ceGlj+PJZWB9p7HHidy1sEAb5T2dJYHQ61az1AKSlur4qFWziDgg4dyOPeEKvGFxcf1XOtz2738hXbGR8PRuoeRAG2xvE/WjsPs2emJ5ul7p+FMt7vsIi9w7tkjlcwElLcYAYyfXd5VBq63BB4uzYaSEK+bATW90Acsqq4xm+Edm5KJ1O2UjQNq6ntfu4BGeyPt3P23Gi+HEt+65eec0d23pZiNtJ9deETAFZ3lGzaFeuxyNGziScDyWgGObzdQ7MN; bm_mi=97804DD24CC8F3F49E30213945B22954~YAAQfqUQAlorHWGRAQAA5NXwcRh8C+jYWoC0XvzUtBbrq8uPmXAjlXkI/NZbTpQHUItSbpl2YWtRISW4jPWFTOFyVC5bLvxRJLWyCOrmk9Cc87r+bFdJ42cq2noo6jTtdm15xMNlLJK4dkqHCqwD9aiRf4Xc3h3j/Z13V3eQJIHKMCEUyhpEF7ZiZZUrRp+3+txH/UueucZYP9rcSewu9Sk3iU1gEGZBqrV1ZyhM0qoE0mtlkuI9NcV6XMsn86Xu3DcRCRsA8/WtJ2+GxxGIBL2Cz2ToHoIBjZjvY9jeVXici1J5y2q6Z3LgEbsjF5Xtt7P1N2i/OAxyIBHumiZaNsDLvs0=~1; _ga_HV7DJVVBCW=GS1.1.1724193489.4.1.1724194305.32.0.0; bm_sv=CA4A5981CD80D3322B7B9C9298B40EAB~YAAQfqUQArFoHWGRAQAAkZD9cRgZk483E1y3qZP/uX7qwZh+XOWdcwYOrCZP1+7FuKYik2FFgO9WfSqjd3Ay9TCWcr+PzDRL0vLyFneydhnFcnN/uCk3p2r9Uy3Br7qsFbmITwQX5koS6UERlu1IiQCaw7KghfyMBmyp2ZrrNmlDVyCqf89nRNST4Irk1ntM9nw7SMnapcEuUWnzrOWMGAYupPvHSvOOP4lDPaMnruE8AYSDWvhsWz1Mk3WyhZB/5FQEGL5S~1'  # Add full cookie string as required
}

# Payload template

Main_list=[]
categories = [
    "company-culture",
    "skill-development-learning",
    "work-satisfaction",
    "work-life-balance",
    "job-security",
    "salary-benefits",
    "promotions-appraisal"
]
ratings=["4.0","4.5","3.75","3.5"]
main_count=0
# Iterate over pages from 1 to 500
processes = []
results = []
Missing = []

# Use ThreadPoolExecutor for threading and alive_bar for progress display
with alive_bar(5000000) as bar:
    with ThreadPoolExecutor(max_workers=50) as executor:
        for category in categories:
            print(f"Stats For Category::{category}")
            for rating in ratings:
                print(f"Stats For Rating::{rating}")
                for index_search in range(1, 51):
                    payload_Search = {
                        "knownFor": [category],
                        "isFilterApplied": True,
                        "limit": 20,
                        "page": index_search,
                        "ratings": rating,
                        "type": "locations"
                    }
                    location_list = getRequestCount(payload_Search)
                    if location_list:
                        location_list = location_list["locations"]
                        for location in location_list:
                            location_Name = location["urlName"]
                            Location_Count = location["docCount"]
                            main_count += Location_Count
                            loop_range = min(int(Location_Count / 20) + 2, 500)
                            for page in range(1, loop_range):
                                payload = {
                                    'isFilterApplied': True,
                                    'knownFor': [category],
                                    'locations': [location_Name],
                                    'limit': 20,
                                    'ratings': rating,
                                    'sortBy': 'rating',  # popular
                                    "page": page
                                }
                                # Submit each request to ThreadPoolExecutor
                                processes.append(executor.submit(getsingleRequest, payload, headers, page))
                                bar()
                        break
                break
            break
        # Process the results as the threads complete
        for task in as_completed(processes):
            result = task.result()
            if isinstance(result, dict):
                results.extend(result)
            else:
                Missing.append(result)

print(main_count)
df =pd.DataFrame(Main_list)
df.to_csv("IndianProjectSample4.csv",index=False)