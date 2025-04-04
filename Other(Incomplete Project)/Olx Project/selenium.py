from seleniumwire import webdriver  # Import from seleniumwire
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from urllib.parse import urlparse, parse_qs
import time
import json

# Set up Chrome options
chrome_options = webdriver.ChromeOptions()
# chrome_options.add_argument("--no-sandbox")
# chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--ignore-certificate-errors")  # Add this option
chrome_options.add_argument("--allow-running-insecure-content") 
seleniumwire_options = {
    'verify_ssl': False
}
# Set up the WebDriver
driver = webdriver.Chrome(seleniumwire_options=seleniumwire_options,options=chrome_options,)

# Navigate to the initial page
initial_url = "https://www.olx.ro"  # Replace with the actual URL where the link is located
driver.get(initial_url)

# Wait for the page to load
driver.implicitly_wait(15)  # Wait up to 10 seconds for elements to be available

link_element=driver.find_element(By.XPATH,'/html/body/div[2]/header/div/div/div[2]/a')
Actual_link=link_element.get_attribute("href")
print(Actual_link)
link_element.click()

driver.implicitly_wait(10)

email=driver.find_element(By.NAME,"username")
email.send_keys("saeedhuzaifa678@gmail.com")
password=driver.find_element(By.NAME,"password")
password.send_keys("Saeed@47864")
#driver.get(Actual_link)
# Pause to allow manual interaction
#input("Please manually click on the button and press Enter to continue...")
driver.implicitly_wait(5)
Submit_button=driver.find_element(By.XPATH,'//*[@id="__next"]/div/div[2]/div/div/div/div[2]/div[2]/div[2]/form/button[2]')
Submit_button.click()

# input("Please manually click on the button and press Enter to continue...")
# # Wait for the redirection
# time.sleep(5)  # Adjust as necessary

url_pattern_start = "https://www.olx.ro/d/callback/"
    
    # Monitor the URL until it matches the pattern
captured_url = None
for _ in range(30):  # Adjust the range to increase/decrease the wait time
    current_url = driver.current_url
    if current_url.startswith(url_pattern_start):
        captured_url = current_url
        break
    time.sleep(0.5)  # Wait for 1 second before checking again

if captured_url:
    print("Captured URL:", captured_url)
else:
    print("No matching URL found within the time limit.")


#time.sleep(10)
with open('requests_log.txt', 'w') as file:
        # Monitor XHR/fetch requests
    for request in driver.requests:
        if request.url=="https://ro.login.olx.com/oauth2/token":
            file.write(
                f"URL: {request.url}\n"
                f"Method: {request.method}\n"
                f"Request Headers: {request.headers}\n"
                f"Status Code: {request.response.status_code}\n"
                f"Response Headers: {request.response.headers}\n"
                f"Response Body: {request.response.body}\n"
                f"\n"
            )
            print(f"URL: {request.url}\n"
                f"Method: {request.method}\n"
                f"Request Headers: {request.headers}\n"
                f"Status Code: {request.response.status_code}\n"
                f"Response Headers: {request.response.headers}\n"
                f"Response Body: {request.response.body}\n"
                f"\n")
            file.write("\n" + "="*50 + "\n\n")

# Capture the redirected URL
# redirected_url = driver.current_url
# print("Redirected URL:", redirected_url)
# driver.get(redirected_url)
# # Extract the authorization code from the URL
# parsed_url = urlparse(redirected_url)
# cc = parse_qs(parsed_url.query).get('cc')[0]
# client_id = parse_qs(parsed_url.query).get('client_id')[0]
# code_challenge = parse_qs(parsed_url.query).get('code_challenge')[0]
# code_challenge_method = parse_qs(parsed_url.query).get('code_challenge_method')[0]
# redirected_uri = parse_qs(parsed_url.query).get('redirect_uri')[0]
# state = parse_qs(parsed_url.query).get('state')[0]
# st = parse_qs(parsed_url.query).get('st')[0]

# print("cc Code:", cc)
# print("client_id", client_id)
# print(code_challenge, code_challenge_method)
# print("Redirect URL", redirected_uri)

# authenticate_url = f"https://login.olx.ro/api/initiate-auth?client_id={client_id}&redirect_uri={redirected_uri}&code_challenge={code_challenge}&code_challenge_method={code_challenge_method}&state={state}%3D%3D&st={st}"
# print(authenticate_url)

# # JavaScript payload to send the request
# payload = {
#     "auth_parameters": {
#         "login": "saeedhuzaifa678@gmail.com",
#         "password": "Saeed@47864"
#     },
#     "user_context_data": {
#         "encoded_data": "eyJwYXlsb2FkIjoie1wiY29udGV4dERhdGFcIjp7XCJVc2VyQWdlbnRcIjpcIk1vemlsbGEvNS4wIChXaW5kb3dzIE5UIDEwLjA7IFdpbjY0OyB4NjQpIEFwcGxlV2ViS2l0LzUzNy4zNiAoS0hUTUwsIGxpa2UgR2Vja28pIENocm9tZS8xMjYuMC4wLjAgU2FmYXJpLzUzNy4zNlwiLFwiRGV2aWNlSWRcIjpcIjdvd3QyaWJobHdrYTA0eDB2dnFwOjE3MTk3MzA3Mjg5NzJcIixcIkRldmljZUxhbmd1YWdlXCI6XCJlbi1VU1wiLFwiRGV2aWNlRmluZ2VycHJpbnRcIjpcIk1vemlsbGEvNS4wIChXaW5kb3dzIE5UIDEwLjA7IFdpbjY0OyB4NjQpIEFwcGxlV2ViS2l0LzUzNy4zNiAoS0hUTUwsIGxpa2UgR2Vja28pIENocm9tZS8xMjYuMC4wLjAgU2FmYXJpLzUzNy4zNlBERiBWaWV3ZXI6Q2hyb21lIFBERiBWaWV3ZXI6Q2hyb21pdW0gUERGIFZpZXdlcjpNaWNyb3NvZnQgRWRnZSBQREYgVmlld2VyOldlYktpdCBidWlsdC1pbiBQREY6ZW4tVVNcIixcIkRldmljZVBsYXRmb3JtXCI6XCJXaW4zMlwiLFwiQ2xpZW50VGltZXpvbmVcIjpcIjA1OjAwXCJ9LFwidXNlcm5hbWVcIjpcInNhZWVkaHV6YWlmYTY3OEBnbWFpbC5jb21cIixcInVzZXJQb29sSWRcIjpcIlwiLFwidGltZXN0YW1wXCI6XCIxNzE5NzUxNTE3MTExXCJ9Iiwic2lnbmF0dXJlIjoiY2hmUGhwb0NFQnc0Q1N5MEFnOFgvYVh1NER0SGpzWlk3N0tITnpUMEc4TT0iLCJ2ZXJzaW9uIjoiSlMyMDE3MTExNSJ9"
#     }
# }

# # JavaScript code to send the request using fetch
# fetch_js = f"""
# fetch("{authenticate_url}", {{
#     method: "POST",
#     headers: {{
#         "Accept": "*/*",
#         "Accept-Encoding": "gzip, deflate, br, zstd",
#         "Accept-Language": "en-US,en;q=0.9",
#         "Content-Type": "application/json",
#         "Sec-Ch-Ua": '"Not/A)Brand";v="8", "Chromium";v="126", "Google Chrome";v="126"',
#         "Sec-Ch-Ua-Mobile": "?0",
#         "Cookie": "eupubconsent-v2=CQBEK_gQBEK_gAcABBENA7E8AP_gAAAAAAYgJ9NV_G_fbXlj8Xp0aftkeY1f99h7rsQxBhfJk-4FyLuW_JwX32EzNA16pqYKmRIEu3bBIQFlHIDUDUCgaogVrTDMakWMgTNKJ6BEiFMRe2dYCF5vmQFD-QKY5tptd3d52Re9_dv83dzyz4Vnn3Kp_2e1WJCdA5cgAAAAAAAAAAAAAAAQAAAAAAAAAQAIAAAAAAAAAAAAAAAAAAAAF_cAAAMAAABQSCAAAgABcAFAAVAA4AB4AEEALwA1AB4AEQAJgAVQA3gB6AD8AISAQwBEgCOAEsAJoAYAAw4BlAGWANkAc8A7gDvgHsAfEA-wD9gH-AgABFICLgIwARoAksBPwFBgKgAq4BcwC9AGKANEAbQA3ABxIEegSIAnYBQ4CjwFIgLYAXIAu8BeYDBgGGwMjAyQBk4DLgGZgM5gauBrIDYwG3gN1AcEA5MBy4QAsAA4AEgARwCDgEcAJoAX0BKwCbQFIAK5AWEAsQBeQDEAGLAMhAaMA1MBtADbgG6DgFQACIAHAAeABcAEgAPwAjgBQADQAI4AcgBAICDgIQAREAjgBNACoAHSAQgAlYBMQCZQE2gKTgVyBXYCxAFqALoAYIAxABiwDIQGTANGAamA14BtADbAG3AN0AceA5aBzoHPjoJQAC4AKAAqABwAEEALgA1AB4AEQAJgAVYAuAC6AGIAN4AegA_QCGAIkASwAmgBRgDAAGGAMoAaIA2QBzwDuAO8Ae0A-wD9AH_ARQBGICOgJLAT8BQYCogKuAWIAucBeQF6AMUAbQA3ABxADqAH2ARfAj0CRAEyAJ2AUPAo8CkAFNAKsAWKAtgBboC4AFyALtAXeAvMBfQDBgGGgMegZGBkgDJwGVQMsAy4BmYDOQGmwNXA1gBt4DdQHFgOTAcuQAKgAIAAeAGgAcgBHACxAF9ATaApMBXICxAF5AMEAZ4A0YBqYDbAG3AN0AcsA58hAhAAWABQAFwANQAmABVAC4AGIAN4AegBHADAAHPAO4A7wB_gEUAJSAUGAqICrgFzAMUAbQA6gCPQFNAKsAWKAtEBcAC5AGRgMnAZySgQgAIAAWABQADgAPAAiABMACqAFwAMUAhgCJAEcAKMAYAA2QB3gD8gKiAq4BcwDFAHUARMAi-BHoEiAKPAWKAtgBecDIwMkAZOAzkBrADbyQBEAC4ARwB3AEAAIOARwAqACVgExAJtAUmAxYBlgDPAG5AN0AcsUgcgALgAoACoAHAAQQA0ADUAHgARAAmABVADEAH6AQwBEgCjAGAAMoAaIA2QBzgDvgH4AfoBFgCMQEdASUAoMBUQFXALmAXkAxQBtADcAHUAPaAfYBEwCL4EegSIAnYBQ4CkAFWALFAWwAuABcgC7QF5gL6AYbAyMDJAGTwMsAy4BnMDWANZAbeA3UBwQDkygB8AC4AJAAXAAyACOAI4AcgA7gB9gEAAIOAWIAuoBrwDtgH_ATEAm0BUgCuwF0ALyAYIAxYBkwDPAGjANTAa8A3QBywA.f_wAAAAAAAAA; laquesis=aut-2972@a#aut-2979@c#cou-1751@b#erm-1605@a#jobs-7504@b#olxeu-41153@b#olxeu-41791@b#olxeu-41945@b#tsm-208@b; laquesisff=aut-1425#aut-388#buy-2279#buy-2489#dat-2874#de-2724#decision-256#decision-657#do-3481#euonb-114#f8nrp-1779#jobs-7611#kuna-307#mart-1341#oesx-1437#oesx-2798#oesx-2864#oesx-2926#oesx-3150#oesx-3713#oesx-645#oesx-867#srt-1289#srt-1346#srt-1434#srt-1593#srt-1758#srt-684#uacc-529#uacc-561#up-90; _pcid=%7B%22browserId%22%3A%22ly2j2sf6m3uv7hgb%22%7D; cX_P=ly2j2sf6m3uv7hgb; _pctx=%7Bu%7DN4IgrgzgpgThIC4B2YA2qA05owMoBcBDfSREQpAeyRCwgEt8oBJAEzIEYOBmAVg4AMAJgEA2IQE5RAgBwCA7PP4gAvkA; deviceGUID=019a066f-d6b5-408c-8308-2738a88e4095; a_access_token=052f79c26fe05d2980a52711c748a3889591463c; a_refresh_token=2966ed13865d20813fec2030b1d3207c9b46848f; a_grant_type=device; user_business_status=private; cX_G=cx%3A43f6bovvv9wp2cp16f3mre1ts%3A3d6n4db4lz4ov; _gid=GA1.2.1926716726.1719811028; _gcl_au=1.1.794827934.1719811039; laquesissu=297@ad_page|1#297@reply_phone_1step|1#302@jobs_applications|0#690@ad_page|1#690@listing|1; ldctx=eyJrZXkiOiI2OGE4NWM2Zi03MTY3LTQ2NzYtOTc5ZS1kZWUwNGY2YjZmZDEifQ==; ldff=AUT-2453#AUT-2591#enable-friction-ready-state#enable-overlay#enable-sst-custom-message#enable_eprivacy_integration#store-url-params; thememode=light; OTAdditionalConsentString=1~; _hjSessionUser_2218929=eyJpZCI6IjhkMzdjNWQ3LTg4NWItNWIwMi1iZjUwLWFkODBlZTc3Y2JiOSIsImNyZWF0ZWQiOjE3MTk4MTEwMjMxODQsImV4aXN0aW5nIjp0cnVlfQ==; user_id=1069456274; __user_id_P&S=1069456274; user_uuid=; observed_aui=f677b3432d314192bc615ed10464afc3; PHPSESSID=6t0251f3384eg0dar2kvvvfe0n; _hjSession_2218929=eyJpZCI6IjgzNjVlM2M5LWFjN2YtNDkwNS1hYzU1LTRmZWMzMTQ0MWE2YSIsImMiOjE3MTk4MTY5MDQxNTMsInMiOjAsInIiOjAsInNiIjowLCJzciI6MCwic2UiOjAsImZzIjowLCJzcCI6MH0=; ldTd=true; __gads=ID=1b0fe9917c44cbec:T=1719811026:RT=1719816905:S=ALNI_MbZmNOHglhQO9kyovtxV2kec5V2LQ; __gpi=UID=00000e75d7863220:T=1719811026:RT=1719816905:S=ALNI_MbXbeWx34ZBFGS19JIKPfpe52jSuA; __eoi=ID=1e82b37dbe6d7c81:T=1719811026:RT=1719816905:S=AA-AfjbDNKp4U3xfxJA1iNz7e6HT; ab.storage.sessionId.674798dd-1b17-48b5-8ecb-a2cbcb42cb5d=%7B%22g%22%3A%22711437bb-36ec-a6a8-ec10-1d571257ef91%22%2C%22e%22%3A1719818706792%2C%22c%22%3A1719816906792%2C%22l%22%3A1719816906792%7D; ab.storage.deviceId.674798dd-1b17-48b5-8ecb-a2cbcb42cb5d=%7B%22g%22%3A%22d6577e70-ee08-aa06-a7a8-c33f6429a05b%22%2C%22c%22%3A1719811028744%2C%22l%22%3A1719816906794%7D; ab.storage.userId.674798dd-1b17-48b5-8ecb-a2cbcb42cb5d=%7B%22g%22%3A%223a34190d-808f-45bf-9f14-ce0b30e707a3%22%2C%22c%22%3A1719731010247%2C%22l%22%3A1719816906796%7D; _gat_clientNinja=1; cto_bundle=i3GH_V9QJTJGMDVvNkd5Z0ZOSGklMkJHN0ZrVmJOamMyNTRWNzlxZWRjbmFjZkt3WFR4b0FydlA0aEs0YVhXVTltYSUyQjdkVDVOdjN4WU1lVmpsTnU2NTFtT0tyV0NMQXdNWnBjcUlESlZOMUVTb01XcWVjT0tqRGMlMkJ6aFBYU25MelBzZkFmcFFDeXRQc2FuZDluRXpPQnpFWTd3R1pVZyUzRCUzRA; AuthState=unlogged; OptanonAlertBoxClosed=2024-07-01T06:55:22.528Z; OptanonConsent=isGpcEnabled=0&datestamp=Mon+Jul+01+2024+11%3A55%3A22+GMT%2B0500+(Pakistan+Standard+Time)&version=202401.2.0&browserGpcFlag=0&isIABGlobal=false&hosts=&genVendors=&consentId=f015372c-62a5-4458-8751-a2071fceccd7&interactionCount=6&landingPath=NotLandingPage&groups=C0001%3A1%2CC0002%3A1%2CC0003%3A1%2CC0004%3A1%2Cgad%3A1&geolocation=PK%3BKP&AwaitingReconsent=false; evid_set_0046=1; lqstatus=1719818287|1906d1363d1x77c7ed86|aut-2979||; evid_0046=cx:2rn4x98v168px3ryhkad73u3qc:229modx55iegi; adptset_0046=1; _ga_NK3K3T1FT5=GS1.1.1719816908.8.1.1719816924.0.0.0; _ga=GA1.1.416008534.1719765367; _ga_Q0GQ41R48F=GS1.1.1719816909.8.1.1719816924.0.0.0; _ga_1XTP46N9VR=GS1.1.1719816908.8.1.1719816924.0.0.0; onap=1906ac1af48x50243e5d-3-1906d1363d1x77c7ed86-10-1719818728; aws-waf-token=c622b95c-84eb-4ed9-892a-263ef136e99b:DQoAeW4vKt1TAAAA:xS/vkdXQXm0KnF/ZYUuVng3ADz+p9HCL4dx6dAD1Z17MA/kgFlfqNqZbHTyFdIAXkPCWZ4aTVM19/m/x2yiZd76/4Wxm/0q8YOXS+Vcia/fg3CngpHrc+VgTV774YyTMu1qlMtJIBR41d6Gp7/zIAAk3vUtrSrWPfL9C2s3Ppn2kbt1PbxPXKODa/st3LWAJN3ZfNGuZ8eqE0iSWtE1npXi69bG752x1vCvr5vD0YWF7EyUdhDTUAFfNAlwkYeK9oAp6",
#         "Friction-Token": "eyJhbGciOiJSUzI1NiIsImtpZCI6ImRiM2I1ZTRiLTllM2ItNDU5YS05MjBhLTIwMjgwNWVhYzI1YiIsInR5cCI6IkpXVCJ9.eyJhdWQiOiJhdXRoIiwiYWN0aW9uIjoibG9naW4iLCJhY3RvciI6eyJ1c2VybmFtZSI6InNhZWVkaHV6YWlmYTY3OEBnbWFpbC5jb20iLCJkZXNpcmVkX2VtYWlsIjoiIiwiZGVzaXJlZF9waG9uZSI6IiIsImlwIjoiMTU0LjE5OC43Ni4xNjIiLCJpcF9jb3VudHJ5IjoiUEsifSwic2NlbmUiOnsic2l0ZWNvZGUiOiJvbHhybyJ9LCJpc3MiOiJodHRwczovL2ZyaWN0aW9uLm9seGdyb3VwLmNvbSIsImlhdCI6MTcxOTgxNjkyNiwiZXhwIjoxNzE5ODE2OTQxfQ.tfbq6qJibArEAWXd7P06wE6SVLHlv40XUKjpswE4M7amkIPfd0jeWJFN3kBRWTCTY45p85c3vEZsDAI16dSRVvBnARNnXG2BkW_r7opmyeTDq9Y2Zsng8XuuSYUO2WS60z3BFgeDkbnC_yhaFFWkcsjaDXBb3uG-N7Hd5OJDzZIER0T4tq_xzlY4mbr1Mxd-wf9KkU6pu_dR1YvOsKh4nps7RAcHUCcb_pny5JuvzzLTI6JHOeXHAA3rzNsLPnOHFHlWU2IJLQZEhFlR-KH7qlsmlmdzWilUkhjPqv7RAchuPeQmeQEeYwrWPkUiZ0_MEdau3ePQ0mnEEOB9AXHmqw",
#         "Sec-Ch-Ua-Platform": '"Windows"',
#         "Sec-Fetch-Dest": "empty",
#         "Sec-Fetch-Mode": "cors",
#         "Sec-Fetch-Site": "same-origin",
#         "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
#     }},
#     body: JSON.stringify({json.dumps(payload)})
# }}).then(response => response.text())
#   .then(data => {{
#       console.log('Response:', data);
#       window.authResponse = data;
#   }})
#   .catch(error => console.error('Error:', error));
# """

# Execute the JavaScript code in the Selenium session
#driver.execute_script(fetch_js)

# Wait for the request to complete
#time.sleep(5)  # Adjust as necessary

# Retrieve the response from the JavaScript execution
# auth_response = driver.execute_script("return window.authResponse;")
# print("Authentication Response:", auth_response)

# Close the browser
driver.quit()
