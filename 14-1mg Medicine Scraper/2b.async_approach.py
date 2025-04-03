#File Name=2b.async_approach.py
#The Following Code used the Medicine links and related Information that we scraped previously  from scrap_urls.py file
#Then this code hit on each medicine links and store the html content in Database
#The Following Code used the Async Approach and Proxies
#Due to asynch approach with proxies,its not work properly and website block after some time
#So This Code has not been used to do this Project
import aiohttp
import asyncio
import pandas as pd
import dataset
from bs4 import BeautifulSoup
from alive_progress import alive_bar
from aiohttp import DummyCookieJar
# -------------------
# Global setup
# -------------------
proxy_url = "http://adf1f9b7b95b8a8e4bcc__cr.sg:eb3d6@gw.dataimpulse.com:823"
db = dataset.connect("sqlite:///MedicineMain2.db")
table = db["Scraped"]

def read_excel_to_dict(file_name: str):
    """
    Reads the Excel file and converts it to a list of dictionaries.
    Exactly like your original function, no async needed.
    """
    df = pd.read_excel(file_name)
    return df.to_dict(orient="records")

async def fetch_and_parse(session, entry):
    """
    Single async task that:
      - Gets the URL from entry["Link"]
      - Requests it using aiohttp (with proxy)
      - Parses or simply stores HTML in entry
    """
    url = entry.get("Link")
    index = entry.get("index")
    if not url:
        return None
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        # "cookie": 'city=Gurgaon; abVisitorId=228927; abExperimentShow=true; jarvis-id=07d7d2fb-03da-4856-8e0b-c81bdfae4d3b; rl_page_init_referrer=RudderEncrypt%3AU2FsdGVkX19gqBiLCWKfsaFdlLqmPGi0Qje%2BFcO2%2B5M%3D; rl_page_init_referring_domain=RudderEncrypt%3AU2FsdGVkX1%2FAdlgsK%2BW%2BG9GkPFVFik5iJLXedmNGAsA%3D; geolocation=false; _gcl_au=1.1.1245232553.1741862117; _ga=GA1.2.830488652.1741862118; _gid=GA1.2.1524283589.1741862118; _nv_did=173339004.1741862117.2171222026hzxyk; __adroll_consent=CQONUAAQONUAAAAACBENAMFgAAAAAAAAABBoARwAAAjgAAAA%23U4ZFS2QH4VB65A54O43AEQ; singular_device_id=68f9c72a-ba4d-4de1-90a0-a47a55be6a16; __adroll_fpc=900353b8458e20973c7ab0cea3940862-1741911204265; VISITOR-ID=bd9c4361-30aa-4e4b-8bd5-1a22887d6f73_XIqV7KMdM0_1015_1741984034466; session=jyB2HkkEfKMhcodA8yssoA.AdKf0AgqH6u-1LAk0slB2LmGOTf5Kf_t9hTwdOsXchE0keAt2FomATo5xUdyBH7dDe91riRiFG1cr-GAvTeX5dXHNtY-aGRgKACsipEUIQb5wIxPRqVDeMmzn81EaSeFTF6QkbGe8-55zt2qbTwYUA.1741984034247.144000000.ELgs6MPKA3zU0TzroTwUq5-ywtMo7DEiSSHPBLN5ONM; MgidSensorNVis=1; MgidSensorHref=https://www.1mg.com/?login=true&followup=https://www.1mg.com/drugs-all-medicines; _csrf=1uKobaRApBAAiD6D40YWMoo9; isLocaleRedirect=false; isLocaleUIChange=false; synapse:init=false; synapse:platform=web; is_cp_member=false; rl_user_id=RudderEncrypt%3AU2FsdGVkX18Ej5RQZhOZgaodco1HGClDZ7TfMcHZQZA%3D; rl_trait=RudderEncrypt%3AU2FsdGVkX1%2Fum3A1BVY2jCJznRnOJ7D2KuS5ikW1voo%3D; rl_group_id=RudderEncrypt%3AU2FsdGVkX1%2F5EKAPIgj0d9mFN2JndT2RiIqmbOpI9cg%3D; rl_group_trait=RudderEncrypt%3AU2FsdGVkX1%2FmT0sfcpOkCdC6wYm2y07IXd6ae2XRwBY%3D; rl_anonymous_id=RudderEncrypt%3AU2FsdGVkX1%2FpvOINzEawWMFADJes2R4uctZR6VrQXBdlXdzyyoJHS5z%2FTDF%2BN75LZ6HtA8zw%2FReHa%2F6wslsrGA%3D%3D; rl_session=RudderEncrypt%3AU2FsdGVkX1%2F56DgBhNvvD332Fnt2XtRKYRzBSYaZOfrHq7bAiS0CcS0zkXGVjPpgIxjhVcK%2B9El1Ij83snw9%2FSVsWF9E7b4Xl%2FJ4IqcvI%2F6lTG%2F2wZQBqM5w6QEP5WAjKjZk2IB0A8fWbMSBKqhlVA%3D%3D; _nv_uid=173339004.1741862117.6097ccd9-0135-4250-b9b3-df46933cc93a.1741984038.1742034022.6.0; _nv_utm=173339004.1741862117.6.1.dXRtc3JjPShkaXJlY3QpfHV0bWNjbj0oZGlyZWN0KXx1dG1jbWQ9KG5vbmUpfHV0bWN0cj0obm90IHNldCl8dXRtY2N0PShub3Qgc2V0KXxnY2xpZD18dXRtYWRncD0=; cto_bundle=Xiz9EF9obE03cSUyRkFHNzZGVnZ5U2JRVzBzQXN2SG53SWxBRngzc2ViWjdwS01pQ0wlMkJIUElUcnNUbXRIYWY2JTJCZnJQMUFFbGMlMkZmTzE5b3c5bXdDJTJGUHp2N1A1S3RPJTJGYXE5YmUlMkZwYjNQQTR1eXpjaWJLemFjem02V0YlMkJZUGYyUDFQcnhpSGROS0dxQ0d3SDVQZHQ5YTBxaElmcmlRJTNEJTNE; __ar_v4=KJTLL7NSNRFA5J3GVYGJVJ%3A20250313%3A126%7C6PFMKMAZXFGFLMSXPCJHFF%3A20250313%3A126%7CU4ZFS2QH4VB65A54O43AEQ%3A20250313%3A126; shw_13453=6; _nv_banner_x=13453; _nv_hit=173339004.1742034022.cHZpZXc9MXxidmlldz1bIjEzNDUzIl0=; AWSALBTG=nKLdUDrSiVkaLuK3a5ENumfYi2UZGYdhS7aSQT5cKIyM3JdNITKGagnCShv/0neJ8th+r0LRIvecPvzvwIEsuwntAKgFTne4Kpm0sQhkKNKSqJj5h+gLuqvno3n1XtaDXkRT6tHsd6XqnU989F1/8cq1ssygQ92e/wyz6QqfAcwd; AWSALBTGCORS=nKLdUDrSiVkaLuK3a5ENumfYi2UZGYdhS7aSQT5cKIyM3JdNITKGagnCShv/0neJ8th+r0LRIvecPvzvwIEsuwntAKgFTne4Kpm0sQhkKNKSqJj5h+gLuqvno3n1XtaDXkRT6tHsd6XqnU989F1/8cq1ssygQ92e/wyz6QqfAcwd'
    }
    # Optional: Retry logic if you want multiple attempts
    while True:
        try:
            # jar = aiohttp.CookieJar(unsafe=True)
            # async with aiohttp.ClientSession(cookie_jar=None) as session:
                async with session.get(url,headers=headers, proxy=proxy_url) as resp:
                    if resp.status == 200:
                        content = await resp.text()
                        soup = BeautifulSoup(content, "html.parser")
                        soup=soup.find(id="container")
                        if soup:
                            # print("successfull")
                            # with open(f"test/output{index}.html", "w", encoding="utf-8") as file:
                            #     file.write(str(soup))
                            entry["Html_Content"] = str(soup)
                        return entry
                    else:
                        print(f"Request failed with status code: {resp.status}")
        except Exception as e:
            print(f"Failed to fetch {url}: {e}")

    # If you only want to try once, do this:
    # try:
    #     async with session.get(url, proxy=proxy_url) as resp:
    #         if resp.status == 200:
    #             content = await resp.text()
    #             entry["Html_Content"] = content
    #             return entry  # Return the updated entry
    #         else:
    #             print(f"Failed to retrieve {url}. Status: {resp.status}")
    #             return None
    # except Exception as e:
    #     print(f"Error occurred for {url}: {e}")
    #     return None

async def async_scrape(entries):
    """
    Orchestrates the asynchronous scraping:
      - Creates a single aiohttp.ClientSession
      - Spawns tasks for each entry in entries
      - Uses asyncio.as_completed to handle them as they finish
      - Inserts each successful scrape into the DB
    """
    # We build tasks list outside the progress loop so the bar has the correct total
    tasks = []
    # cookie_jar = aiohttp.CookieJar(unsafe=True)
    async with aiohttp.ClientSession(cookie_jar=None) as session:
        with alive_bar(len(entries)) as bar:
            # Create a task for each entry you want to process
            for entry in entries:
                # If you only want to scrape entries with index >= 10000
                if entry["index"] > 132000  and entry["index"] < 200000:
                #     continue
                    tasks.append(fetch_and_parse(session, entry))

            # Process tasks as they finish
            for coro in asyncio.as_completed(tasks):
                result = await coro
                if result:  # If we got valid data back
                    table.insert(result)  # Insert into your DB
                    print(f'Successfully scraped index: {result["index"]}')
                bar()  # Update the progress bar on each completed task

def main():
    # Read data from Excel (blocking)
    file_name = "index2.xlsx"
    data_dict = read_excel_to_dict(file_name)

    # Run our async scraper
    asyncio.run(async_scrape(data_dict))

main()