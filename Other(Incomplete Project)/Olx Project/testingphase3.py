import base64
import hashlib
import os
import requests

def generate_code_verifier():
    code_verifier = base64.urlsafe_b64encode(os.urandom(32)).decode('utf-8').rstrip('=')
    return code_verifier

def generate_code_challenge(code_verifier):
    code_challenge = hashlib.sha256(code_verifier.encode('utf-8')).digest()
    code_challenge = base64.urlsafe_b64encode(code_challenge).decode('utf-8').rstrip('=')
    return code_challenge

# Generate code_verifier and code_challenge
code_verifier = generate_code_verifier()
code_challenge = generate_code_challenge(code_verifier)

import requests

url = "https://www.olx.ro/api/open/oauth/token/"
data = {
    "grant_type": "authorization_code",
    "code": "your_authorization_code",  # Replace with the actual authorization code
    "redirect_uri": "your_redirect_uri",  # Same as the redirect URI used to get the code
    "client_id": "your_client_id",
    "client_secret": "your_client_secret",
    "code_verifier": "your_code_verifier"  # The code verifier you generated
}

response = requests.post(url, data=data)
tokens = response.json()
access_token = tokens['access_token']
refresh_token = tokens['refresh_token']

print("Access Token:", access_token)
print("Refresh Token:", refresh_token)




# from olx.partner import Auth


# auth = Auth(
#   client_id="7gantjdsv7233vniq4dthhm2hh",
#   client_secret="hu7610Wue78XZRbhhuVJwmJmlAdn0Lts3ZI4Vdk31gXkRn0",
# )
# auth.authenticate(code='ebe6c25c-4463-4351-a13d-1c5fac99dab8')
# access_token = auth.access_token

# print(access_token)



# import requests
# #import requests
# headers = {
#     "Accept": "*/*",
#     "Accept-Encoding": "gzip, deflate, br, zstd",
#     "Accept-Language": "en-US,en;q=0.9",
#     "Content-Length": "1078",
#     "Content-Type": "application/json",
#     # Place for cookies
#     #"Cookie": "deviceGUID=f252b0c3-daad-43ab-9f79-8ae768f63d6e; a_access_token=16818532713f6ffb82d110502c50c4eea99dd975; a_refresh_token=f004296563f337764f16b060480226f96560fd6b; a_grant_type=device; observed_aui=be35e553e90346278c14e4c8dba5fe45; __user_id_P&S=1068532468; eupubconsent-v2=CQBA4DgQBA4DgAcABBENA7E8AP_gAAAAAAYgJ9NV_G_fbXlj8Xp0aftkeY1f99h7rsQxBhfJk-4FyLuW_JwX32EzNA16pqYKmRIEu3bBIQFlHIDUDUCgaogVrTDMakWMgTNKJ6BEiFMRe2dYCF5vmQFD-QKY5tptd3d52Re9_dv83dzyz4Vnn3Kp_2e1WJCdA5cgAAAAAAAAAAAAAAAQAAAAAAAAAQAIAAAAAAAAAAAAAAAAAAAAF_cAAAMAAABQSCAAAgABcAFAAVAA4AB4AEEALwA1AB4AEQAJgAVQA3gB6AD8AISAQwBEgCOAEsAJoAYAAw4BlAGWANkAc8A7gDvgHsAfEA-wD9gH-AgABFICLgIwARoAksBPwFBgKgAq4BcwC9AGKANEAbQA3ABxIEegSIAnYBQ4CjwFIgLYAXIAu8BeYDBgGGwMjAyQBk4DLgGZgM5gauBrIDYwG3gN1AcEA5MBy4QAsAA4AEgARwCDgEcAJoAX0BKwCbQFIAK5AWEAsQBeQDEAGLAMhAaMA1MBtADbgG6DgFQACIAHAAeABcAEgAPwAjgBQADQAI4AcgBAICDgIQAREAjgBNACoAHSAQgAlYBMQCZQE2gKTgVyBXYCxAFqALoAYIAxABiwDIQGTANGAamA14BtADbAG3AN0AceA5aBzoHPjoJQAC4AKAAqABwAEEALgA1AB4AEQAJgAVYAuAC6AGIAN4AegA_QCGAIkASwAmgBRgDAAGGAMoAaIA2QBzwDuAO8Ae0A-wD9AH_ARQBGICOgJLAT8BQYCogKuAWIAucBeQF6AMUAbQA3ABxADqAH2ARfAj0CRAEyAJ2AUPAo8CkAFNAKsAWKAtgBboC4AFyALtAXeAvMBfQDBgGGgMegZGBkgDJwGVQMsAy4BmYDOQGmwNXA1gBt4DdQHFgOTAcuQAKgAIAAeAGgAcgBHACxAF9ATaApMBXICxAF5AMEAZ4A0YBqYDbAG3AN0AcsA58hAhAAWABQAFwANQAmABVAC4AGIAN4AegBHADAAHPAO4A7wB_gEUAJSAUGAqICrgFzAMUAbQA6gCPQFNAKsAWKAtEBcAC5AGRgMnAZySgQgAIAAWABQADgAPAAiABMACqAFwAMUAhgCJAEcAKMAYAA2QB3gD8gKiAq4BcwDFAHUARMAi-BHoEiAKPAWKAtgBecDIwMkAZOAzkBrADbyQBEAC4ARwB3AEAAIOARwAqACVgExAJtAUmAxYBlgDPAG5AN0AcsUgcgALgAoACoAHAAQQA0ADUAHgARAAmABVADEAH6AQwBEgCjAGAAMoAaIA2QBzgDvgH4AfoBFgCMQEdASUAoMBUQFXALmAXkAxQBtADcAHUAPaAfYBEwCL4EegSIAnYBQ4CkAFWALFAWwAuABcgC7QF5gL6AYbAyMDJAGTwMsAy4BnMDWANZAbeA3UBwQDkygB8AC4AJAAXAAyACOAI4AcgA7gB9gEAAIOAWIAuoBrwDtgH_ATEAm0BUgCuwF0ALyAYIAxYBkwDPAGjANTAa8A3QBywA.f_wAAAAAAAAA; OTAdditionalConsentString=1~89.320.1421.1423.1659.1985.1987.2008.2072.2135.2322.2465.2501.2958.2999.3028.3225.3226.3231.3234.3235.3236.3237.3238.3240.3244.3245.3250.3251.3253.3257.3260.3270.3272.3281.3288.3290.3292.3293.3296.3299.3300.3306.3307.3309.3314.3315.3316.3318.3324.3328.3330.3331.3531.3731.3831.3931.4131.4531.4631.4731.4831.5231.6931.7235.7831.7931.8931.9731.10231.10631.10831.11031.11531.12831.13632.13731.14237.14332.15731.16831.16931.21233.23031.24431.25731.25931.26031.26831.27731.27831.28031.28731.28831.29631.31631; laquesis=aut-2972@c#aut-2979@c#cou-1751@b#erm-1605@a#jobs-7504@b#olxeu-41153@b#olxeu-41791@b#olxeu-41945@a#tsm-208@b; laquesisff=aut-1425#aut-388#buy-2279#buy-2489#dat-2874#de-2724#decision-256#decision-657#do-3481#euonb-114#f8nrp-1779#jobs-7611#kuna-307#mart-1341#oesx-1437#oesx-2798#oesx-2864#oesx-2926#oesx-3150#oesx-3713#oesx-645#oesx-867#srt-1289#srt-1346#srt-1434#srt-1593#srt-1758#srt-684#uacc-529#uacc-561#up-90; laquesissu=303@jobs_preferences_click|0#303@jobs_save_preferred_position|0#303@jobs_select_preferred_time|0#303@jobs_select_preferred_contract|0#303@jobs_save_preferred_salary|0#470@candidate_forcontact|0#470@candidate_reject|0#470@amp_note_new_save|0#470@amp_note_edit_save|0#470@applications_filter_valid|0#470@applications_sort_valid|0#470@applications_status_valid|0#470@candidate_rating_ok|0#470@candidate_rating_undecided|0#470@candidate_rating_notfitting|0#470@ep_predefined_cv_request|0#470@amp_download_cv|0#470@%20amp_preview_cv|0#470@%20cp_preview_click|0#470@applications_rating_valid|0; _pctx=%7Bu%7DN4IgrgzgpgThIC4B2YA2qA05owMoBcBDfSREQpAeyRCwgEt8oBJAEzIEYOBmAVg4AMAJgEA2IQE5RAgBwCA7PP4gAvkA; _pcid=%7B%22browserId%22%3A%22ly1j5n4kmnqleuyt%22%7D; cX_P=ly1j5n4kmnqleuyt; _gid=GA1.2.595618769.1719750691; _gcl_au=1.1.1168772018.1719750692; cX_G=cx%3Agp6xer18o0ph20r3yuu0vz9dq%3A128w1ew56hcum; __rtbh.lid=%7B%22eventType%22%3A%22lid%22%2C%22id%22%3A%22STBI44o86ssiHGhSJVB8%22%7D; evid_0046=ad20a439-8d82-4434-b299-00263fabc937; ab.storage.deviceId.674798dd-1b17-48b5-8ecb-a2cbcb42cb5d=%7B%22g%22%3A%22dcc6a8a4-b6ae-fa15-929d-0ff10a34d45c%22%2C%22c%22%3A1719750702340%2C%22l%22%3A1719750702340%7D; session_start_date=1719768101903; _hjSessionUser_2218929=eyJpZCI6ImQ5NzkyNTEwLTcxZDQtNWFkNi04ZWQyLTNkMDc4NTNkNmNiMyIsImNyZWF0ZWQiOjE3MTk3NTA2OTM4ODIsImV4aXN0aW5nIjp0cnVlfQ==; _hjSession_2218929=eyJpZCI6Ijg4Zjk4NDZlLTc3YWQtNDVlYS1hNGUxLWJhYWQ2NzAyNWVkYiIsImMiOjE3MTk3NjYzMDM3OTIsInMiOjAsInIiOjAsInNiIjowLCJzciI6MCwic2UiOjAsImZzIjowLCJzcCI6MH0=; adptset_0046=1; PHPSESSID=3hcb9npnla9jtrff9p108o2l8f; user_id=1068532468; user_uuid=; user_business_status=private; cto_bundle=7Ud6uF8xcW5xNGs3WSUyRkZBQm9hRlVDTGs1Q2RhREZqNnN2U2twYkV1MnYwR0E2ZG9PMWJHYXNVdVhWJTJCRDdJTFElMkIySkVibnQyd3FjV1dRRU1WTFZydjclMkJnWUVVbEdHU1JJaW5HZW9QYWpQWVN2c0Myd3BKNXJTMFhBclI4dVVIWGVPQ0lrOXNjOWFjbk9pTHExcUM2V2lwbHglMkZBJTNEJTNE; __gads=ID=ec97dec8d51e5a58:T=1719750687:RT=1719766308:S=ALNI_MYZPmKSrCSWgrdP-f4t7QJsUfYZZg; __gpi=UID=00000e6afbb13ada:T=1719750687:RT=1719766308:S=ALNI_MaOwTEo-VuSR4QYdillLjq9mB8XZg; __eoi=ID=493dd9e1722ccd99:T=1719750687:RT=1719766308:S=AA-Afjb6ifA7Org3Vhf4biO041_n; OptanonAlertBoxClosed=2024-06-30T16:53:06.206Z; ldTd=true; _ga=GA1.1.70471942.1719750687; lqstatus=1719767522|1906a0f83f9x44aaf123|aut-2979||; _gat_clientNinja=1; onap=1906920f541x3ccdc07-2-1906a0f83f9x44aaf123-11-1719768216; _ga_NK3K3T1FT5=GS1.1.1719766323.2.1.1719766417.0.0.0; _ga_Q0GQ41R48F=GS1.1.1719766323.2.1.1719766417.0.0.0; _ga_1XTP46N9VR=GS1.1.1719766322.2.1.1719766417.0.0.0; evid_set_0046=2; OptanonConsent=isGpcEnabled=0&datestamp=Sun+Jun+30+2024+21%3A53%3A39+GMT%2B0500+(Pakistan+Standard+Time)&version=202401.2.0&browserGpcFlag=0&isIABGlobal=false&hosts=&genVendors=&consentId=fca5f20f-1ba9-4b5d-aa2b-d67db950c231&interactionCount=5&landingPath=NotLandingPage&groups=C0001%3A1%2CC0002%3A1%2CC0003%3A1%2CC0004%3A1%2Cgad%3A1&geolocation=FR%3B&AwaitingReconsent=false; _legacy_auth0.7gantjdsv7233vniq4dthhm2hh.is.authenticated=true; auth0.7gantjdsv7233vniq4dthhm2hh.is.authenticated=true; auth_state=eyJzdWIiOiIzYTM0MTkwZC04MDhmLTQ1YmYtOWYxNC1jZTBiMzBlNzA3YTMifQ==; access_token=eyJraWQiOiJqWnZWYlA2WndLQlZrTFhtQ3dVcjA5Z0RSejRkN29wVzJDUWNDVDVIZ253PSIsImFsZyI6IlJTMjU2In0.eyJzdWIiOiIzYTM0MTkwZC04MDhmLTQ1YmYtOWYxNC1jZTBiMzBlNzA3YTMiLCJlbWFpbF92ZXJpZmllZCI6dHJ1ZSwiaXNzIjoiaHR0cHM6XC9cL2NvZ25pdG8taWRwLmV1LWNlbnRyYWwtMS5hbWF6b25hd3MuY29tXC9ldS1jZW50cmFsLTFfZ1M0MEJ0VDRwIiwiY29nbml0bzp1c2VybmFtZSI6Ijg1YzhhM2M4LTUzYjAtNGY5Ni1iMjVhLTQ5NDBmMWY3NjhhMSIsImxvY2FsZSI6InJvIiwiY3VzdG9tOmxhc3RfdXNlcm5hbWVfdHlwZSI6ImVtYWlsIiwib3JpZ2luX2p0aSI6IjU0ZmQwODY1LWZjMWMtNDc3Zi05ZjcwLWU1OTY0NDdkYTMzMiIsImF1ZCI6IjdnYW50amRzdjcyMzN2bmlxNGR0aGhtMmhoIiwiZXZlbnRfaWQiOiI4MTA4MGRjNy1mODJjLTQ1MTEtYjI4OS1jNWM5ZjBhZTA0ZjciLCJ0b2tlbl91c2UiOiJpZCIsImF1dGhfdGltZSI6MTcxOTc2NjQxNCwiZXhwIjoxNzE5NzY3MzE0LCJpYXQiOjE3MTk3NjY0MTQsImp0aSI6ImRiYzRiZWNmLTJlZjAtNDc4MC1iNGEwLTBmYjc1MmQ3N2M5ZSIsImVtYWlsIjoic2FlZWRodXphaWZhNjc4QGdtYWlsLmNvbSJ9.NWD3bT7mHNAyidD32N6psMCpKjK2yiUXyCT75xtonr6vI1jZbfla-N7qEd0qP-_nIgoMWaHPoSzWfQdOYI0Ug9Z98joEk_7UEtDY8o74v1fWdAKR2cXZnVKsNhTaNoVEZsKjTs8x7KLyL4oCbS5Qu33yWSY9FdwdcfYeEYC6IQjrrk70URXmj4tip7PtTB6juJFGVdNNbqFafVpWKEybnZ1uL5svdgcsaGDGIf29YApDya1goXcZqvktL1mNa-mCMRq77GLO6n_JCz6xvXhOo-T9jz3HXXfJ9pRBvhjEPsesZWk4EPYqa-wASkfRB2RGkH1wwlWXdaKkfR5TdEmhhg",
#     #"Friction-Token": "eyJhbGciOiJSUzI1NiIsImtpZCI6ImRiM2I1ZTRiLTllM2ItNDU5YS05MjBhLTIwMjgwNWVhYzI1YiIsInR5cCI6IkpXVCJ9.eyJhdWQiOiJhdXRoIiwiYWN0aW9uIjoibG9naW4iLCJhY3RvciI6eyJ1c2VybmFtZSI6InNhZWVkaHV6YWlmYTY3OEBnbWFpbC5jb20iLCJkZXNpcmVkX2VtYWlsIjoiIiwiZGVzaXJlZF9waG9uZSI6IiIsImlwIjoiMzkuNjIuMTYzLjU1IiwiaXBfY291bnRyeSI6IlBLIn0sInNjZW5lIjp7InNpdGVjb2RlIjoib2x4cm8ifSwiaXNzIjoiaHR0cHM6Ly9mcmljdGlvbi5vbHhncm91cC5jb20iLCJpYXQiOjE3MTk3NTE1MTYsImV4cCI6MTcxOTc1MTUzMX0.mweKuFNWcBAaqPlvBklT5yK_JAACZjjlw8W-nLp6e-SVZ40MiV_KYXBtxH3HCgZ2qLEdx8a6JUsv8ffCRIHF32wr0FUMfULiVnBOZpeHblzK7YciMmWkxA9osQ6u2uEHGN-B3RIhnT_zQOw6oAJLitIr0tXpY5hkP0DY29rXZL9WqK1NmEK00EC97M6VVTHk_ZlT8toses5X4WaDHTmWAdzMgHFzjUU4m4uDjJNhNuDmsFDNXgr8wGmJ5zPjde_pUgJcUY4NwPFEEf-s3EecoQKc7fMe_jXUqlKctG1BB9AssNzW0e5vk7KZRrmf7zIaQ7tKFwI50OyXXVtu_ujHYw",
#     "Origin": "https://login.olx.ro",
#     "Priority": "u=1, i",
#     "Sec-Ch-Ua": "\"Not/A)Brand\";v=\"8\", \"Chromium\";v=\"126\", \"Google Chrome\";v=\"126\"",
#     "Sec-Ch-Ua-Mobile": "?0",
#     "Sec-Ch-Ua-Platform": "\"Windows\"",
#     "Sec-Fetch-Dest": "empty",
#     "Sec-Fetch-Mode": "cors",
#     "Sec-Fetch-Site": "same-origin",
#     "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
# }
# url = "https://www.olx.ro/api/open/oauth/token/"
# url1="https://ro.login.olx.com/oauth2/token"
# payload1={
#     "client_id": "7gantjdsv7233vniq4dthhm2hh",
#     "code_verifier": "wg4rquoC0uaUUTV6GvVJMSu1SUwcnhaJvXTm0ASsuhs",
#     "grant_type": "authorization_code",
#     "code": "6eddf55f-c4e2-4ffb-992b-e4e1ba875cad",
#     "redirect_uri": "https://www.olx.ro/d/callback/"    
# }
# payload = {
    
#     "grant_type": "device",
#     "client_id": "7gantjdsv7233vniq4dthhm2hh",
#     "client_secret": "hu7610Wue78XZRbhhuVJwmJmlAdn0Lts3ZI4Vdk31gXkRn0",
#     "device_id": "02f8e52c-879b-4e85-9cb2-81fc644ae26e",
#     "device_token": "eyJpZCI6IjAyZjhlNTJjLTg3OWItNGU4NS05Y2IyLTgxZmM2NDRhZTI2ZSJ9.d0e1cd62410728548c969546e59d40dd2faa1c83",
#     "scope": "i2 read write v2"
# }

# response = requests.post(url, data=payload)
# print(response.text)
# print(response.status_code)

# # URL and parameters
# # url = "https://login.olx.ro/api/initiate-auth"
# # params = {
# #     "client_id": "7gantjdsv7233vniq4dthhm2hh",
# #     "redirect_uri": "https://www.olx.ro/d/callback/",
# #     "code_challenge": "P3-CLX6yRss2L8DesCI6Ca8llGIPHGFPEHbDqarKFu0",
# #     "code_challenge_method": "S256",
# #     "state": "RldvYzBUaElMREE3RzY0cnNzZFBQaVFOTlhuRUszaH40en5nTzhMcktoVg==",
# #     "st": "eyJzbCI6IjE5MDY5Mjg0YjI0eDM0Zjg0Y2VkIiwicyI6IjE5MDY5Mjg0YjI0eDM0Zjg0Y2VkIn0="
# # }

# # # Headers
# # headers = {
# #     "Accept": "*/*",
# #     "Accept-Encoding": "gzip, deflate, br, zstd",
# #     "Accept-Language": "en-US,en;q=0.9",
# #     "Content-Length": "1078",
# #     "Content-Type": "application/json",
# #     # Place for cookies
# #     "Cookie": "evid_0046=cx:2rn4x98v168px3ryhkad73u3qc:229modx55iegi; __rtbh.lid=%7B%22eventType%22%3A%22lid%22%2C%22id%22%3A%22jZX0ILa3vuC5bRtmyIFB%22%7D; AuthState=unlogged; lqstatus=1719752056|19068c5661fx44449529|aut-2979||; mobile_default=desktop; PHPSESSID=olip4qf3snknqm5bh15bdir029; deviceGUID=9de550e5-1eea-4d89-8df7-cfac5bf9f509; a_access_token=f54dae3463afe167b5aa1116f21af03335ebf9c9; a_refresh_token=4953bc39689d8c41124b40bfdf055e5f7cd841e5; a_grant_type=device; observed_aui=8bc777612d5743d3aa86b478bef22393; __user_id_P&S=1068545853; eupubconsent-v2=CQBA4DgQBA4DgAcABBENA7E8AP_gAAAAAAYgJ9NV_G_fbXlj8Xp0aftkeY1f99h7rsQxBhfJk-4FyLuW_JwX32EzNA16pqYKmRIEu3bBIQFlHIDUDUCgaogVrTDMakWMgTNKJ6BEiFMRe2dYCF5vmQFD-QKY5tptd3d52Re9_dv83dzyz4Vnn3Kp_2e1WJCdA5cgAAAAAAAAAAAAAAAQAAAAAAAAAQAIAAAAAAAAAAAAAAAAAAAAF_cAAAMAAABQSCAAAgABcAFAAVAA4AB4AEEALwA1AB4AEQAJgAVQA3gB6AD8AISAQwBEgCOAEsAJoAYAAw4BlAGWANkAc8A7gDvgHsAfEA-wD9gH-AgABFICLgIwARoAksBPwFBgKgAq4BcwC9AGKANEAbQA3ABxIEegSIAnYBQ4CjwFIgLYAXIAu8BeYDBgGGwMjAyQBk4DLgGZgM5gauBrIDYwG3gN1AcEA5MBy4QAsAA4AEgARwCDgEcAJoAX0BKwCbQFIAK5AWEAsQBeQDEAGLAMhAaMA1MBtADbgG6DgFQACIAHAAeABcAEgAPwAjgBQADQAI4AcgBAICDgIQAREAjgBNACoAHSAQgAlYBMQCZQE2gKTgVyBXYCxAFqALoAYIAxABiwDIQGTANGAamA14BtADbAG3AN0AceA5aBzoHPjoJQAC4AKAAqABwAEEALgA1AB4AEQAJgAVYAuAC6AGIAN4AegA_QCGAIkASwAmgBRgDAAGGAMoAaIA2QBzwDuAO8Ae0A-wD9AH_ARQBGICOgJLAT8BQYCogKuAWIAucBeQF6AMUAbQA3ABxADqAH2ARfAj0CRAEyAJ2AUPAo8CkAFNAKsAWKAtgBboC4AFyALtAXeAvMBfQDBgGGgMegZGBkgDJwGVQMsAy4BmYDOQGmwNXA1gBt4DdQHFgOTAcuQAKgAIAAeAGgAcgBHACxAF9ATaApMBXICxAF5AMEAZ4A0YBqYDbAG3AN0AcsA58hAhAAWABQAFwANQAmABVAC4AGIAN4AegBHADAAHPAO4A7wB_gEUAJSAUGAqICrgFzAMUAbQA6gCPQFNAKsAWKAtEBcAC5AGRgMnAZySgQgAIAAWABQADgAPAAiABMACqAFwAMUAhgCJAEcAKMAYAA2QB3gD8gKiAq4BcwDFAHUARMAi-BHoEiAKPAWKAtgBecDIwMkAZOAzkBrADbyQBEAC4ARwB3AEAAIOARwAqACVgExAJtAUmAxYBlgDPAG5AN0AcsUgcgALgAoACoAHAAQQA0ADUAHgARAAmABVADEAH6AQwBEgCjAGAAMoAaIA2QBzgDvgH4AfoBFgCMQEdASUAoMBUQFXALmAXkAxQBtADcAHUAPaAfYBEwCL4EegSIAnYBQ4CkAFWALFAWwAuABcgC7QF5gL6AYbAyMDJAGTwMsAy4BnMDWANZAbeA3UBwQDkygB8AC4AJAAXAAyACOAI4AcgA7gB9gEAAIOAWIAuoBrwDtgH_ATEAm0BUgCuwF0ALyAYIAxYBkwDPAGjANTAa8A3QBywA.f_wAAAAAAAAA; OTAdditionalConsentString=1~89.320.1421.1423.1659.1985.1987.2008.2072.2135.2322.2465.2501.2958.2999.3028.3225.3226.3231.3234.3235.3236.3237.3238.3240.3244.3245.3250.3251.3253.3257.3260.3270.3272.3281.3288.3290.3292.3293.3296.3299.3300.3306.3307.3309.3314.3315.3316.3318.3324.3328.3330.3331.3531.3731.3831.3931.4131.4531.4631.4731.4831.5231.6931.7235.7831.7931.8931.9731.10231.10631.10831.11031.11531.12831.13632.13731.14237.14332.15731.16831.16931.21233.23031.24431.25731.25931.26031.26831.27731.27831.28031.28731.28831.29631.31631; _pctx=%7Bu%7DN4IgrgzgpgThIC4B2YA2qA05owMoBcBDfSREQpAeyRCwgEt8oBJAEzIEYOBmAVg4AMAJgEA2IQE5RAgBwCA7PP4gAvkA; _pcid=%7B%22browserId%22%3A%22ly1jfwsmucg1ph96%22%7D; cX_P=ly1jfwsmucg1ph96; cto_bundle=obU34l9ra3dJV1ZBMGNaVXJlUDhpSGdQY0dZdTN0a2Z1TFdMS2tDREo0enF5Y013TU16WkRMT1RXZHR2aSUyRloxVGlHayUyRnNkR3QwUUY4ZXBqdzNVazhiSEJyaHpTYnRtbFBmcSUyQkRLOHMzbFR5RSUyQlJOeFpWZ0syckt1TjlNcDJpR1Byd29TRmJaUGpwRFF4VnJIcTUlMkZweE5wWFVnQWxGUiUyRkszZGVQV1hPaFVKR1g3cTclMkJzeUpJJTJGWU5ReHkyaERleFNJYksw; __gads=ID=e1ae50309c6678df:T=1719751167:RT=1719751167:S=ALNI_MbV_c7sEqnY6OlaWDS-suoDAVdPIg; __gpi=UID=00000e6afc63dc05:T=1719751167:RT=1719751167:S=ALNI_MaZuLyBg9t4pAKHzEIsCxHyN7lmBw; __eoi=ID=037dc689cf840d35:T=1719751167:RT=1719751167:S=AA-AfjazR-jIgyP-xxj3JvhV1eyD; _gid=GA1.2.1329818946.1719751169; ab.storage.userId.674798dd-1b17-48b5-8ecb-a2cbcb42cb5d=%7B%22g%22%3A%223a34190d-808f-45bf-9f14-ce0b30e707a3%22%2C%22c%22%3A1719731010247%2C%22l%22%3A1719750524968%7D; ab.storage.deviceId.674798dd-1b17-48b5-8ecb-a2cbcb42cb5d=%7B%22g%22%3A%220b129669-1ac5-40d1-5c85-bc9a01203c8e%22%2C%22c%22%3A1719730673463%2C%22l%22%3A1719750524968%7D; ab.storage.sessionId.674798dd-1b17-48b5-8ecb-a2cbcb42cb5d=%7B%22g%22%3A%223393d3c0-ee7e-a2b8-6b7c-9b6d11b94729%22%2C%22e%22%3A1719752324967%2C%22c%22%3A1719750524967%2C%22l%22%3A1719750524967%7D; _gcl_au=1.1.1754872700.1719751169; _hjSessionUser_2218929=eyJpZCI6IjdjOWM2NjQ2LWQxMDAtNWFiYi05OWVjLWM0ZTIyMTIyMDQ3YiIsImNyZWF0ZWQiOjE3MTk3NTExNjk4NzMsImV4aXN0aW5nIjpmYWxzZX0=; _hjSession_2218929=eyJpZCI6IjEwNWY0YTU2LWM1ZDktNDY3MS1iOGE5LWY0YmUyMGY2MGM3YyIsImMiOjE3MTk3NTExNjk4NzUsInMiOjAsInIiOjAsInNiIjowLCJzciI6MCwic2UiOjAsImZzIjoxLCJzcCI6MX0=; ldctx=eyJrZXkiOiJjZGM2NGE2YS05NTQyLTQ4ZTYtOTU4NC03OTlhODZmOGYzZTUifQ==; ldff=AUT-2453#AUT-2591#enable-friction-ready-state#enable-overlay#enable-sst-custom-message#enable_eprivacy_integration#store-url-params; thememode=light; adptset_0046=1; OptanonAlertBoxClosed=2024-06-30T12:42:01.583Z; OptanonConsent=isGpcEnabled=0&datestamp=Sun+Jun+30+2024+17%3A42%3A01+GMT%2B0500+(Pakistan+Standard+Time)&version=202401.2.0&browserGpcFlag=0&isIABGlobal=false&hosts=&genVendors=&consentId=21fe6b0b-0980-4a30-a725-c3376c1ff01d&interactionCount=3&landingPath=NotLandingPage&groups=C0001%3A1%2CC0002%3A1%2CC0003%3A1%2CC0004%3A1%2Cgad%3A1&AwaitingReconsent=false&geolocation=PK%3BKP; _ga_NK3K3T1FT5=GS1.1.1719751169.1.1.1719751324.0.0.0; _ga=GA1.1.1149314032.1719751168; _ga_Q0GQ41R48F=GS1.1.1719751170.1.1.1719751324.0.0.0; _ga_1XTP46N9VR=GS1.1.1719751170.1.1.1719751426.0.0.0; aws-waf-token=88e7f5fa-618f-47ec-a829-185edead0bfb:DQoAhHNYEmJjAAAA:XNNOBx9/RxMMhgYNKxpS9J7HRZbN7xo6VB5gKOmEXFSkHMA+FhnG9CF30/5AYUn6gkKZMVSiiFzBiBW50WwuEkGQrow945pJouOfk+Mfw+CZYf8+sN9qqy8f3oFjXtYjI8+0UoBi/php7kHoJ3mJiK3an6WneN/FRkC0yvZlU6UncdgQslo+HnItiLMMUTscMCRYYy1MXSdRWoKQwUMfGQ3hD4pcXGDdHQVxkyXaoPJy5v1Unvw=; onap=19069284b24x34f84ced-1-19069284b24x34f84ced-14-1719753317",
# #     "Friction-Token": "eyJhbGciOiJSUzI1NiIsImtpZCI6ImRiM2I1ZTRiLTllM2ItNDU5YS05MjBhLTIwMjgwNWVhYzI1YiIsInR5cCI6IkpXVCJ9.eyJhdWQiOiJhdXRoIiwiYWN0aW9uIjoibG9naW4iLCJhY3RvciI6eyJ1c2VybmFtZSI6InNhZWVkaHV6YWlmYTY3OEBnbWFpbC5jb20iLCJkZXNpcmVkX2VtYWlsIjoiIiwiZGVzaXJlZF9waG9uZSI6IiIsImlwIjoiMzkuNjIuMTYzLjU1IiwiaXBfY291bnRyeSI6IlBLIn0sInNjZW5lIjp7InNpdGVjb2RlIjoib2x4cm8ifSwiaXNzIjoiaHR0cHM6Ly9mcmljdGlvbi5vbHhncm91cC5jb20iLCJpYXQiOjE3MTk3NTE1MTYsImV4cCI6MTcxOTc1MTUzMX0.mweKuFNWcBAaqPlvBklT5yK_JAACZjjlw8W-nLp6e-SVZ40MiV_KYXBtxH3HCgZ2qLEdx8a6JUsv8ffCRIHF32wr0FUMfULiVnBOZpeHblzK7YciMmWkxA9osQ6u2uEHGN-B3RIhnT_zQOw6oAJLitIr0tXpY5hkP0DY29rXZL9WqK1NmEK00EC97M6VVTHk_ZlT8toses5X4WaDHTmWAdzMgHFzjUU4m4uDjJNhNuDmsFDNXgr8wGmJ5zPjde_pUgJcUY4NwPFEEf-s3EecoQKc7fMe_jXUqlKctG1BB9AssNzW0e5vk7KZRrmf7zIaQ7tKFwI50OyXXVtu_ujHYw",
# #     "Origin": "https://login.olx.ro",
# #     "Priority": "u=1, i",
# #     "Sec-Ch-Ua": "\"Not/A)Brand\";v=\"8\", \"Chromium\";v=\"126\", \"Google Chrome\";v=\"126\"",
# #     "Sec-Ch-Ua-Mobile": "?0",
# #     "Sec-Ch-Ua-Platform": "\"Windows\"",
# #     "Sec-Fetch-Dest": "empty",
# #     "Sec-Fetch-Mode": "cors",
# #     "Sec-Fetch-Site": "same-origin",
# #     "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
# # }

# # # Payload
# # payload = {
# #     "auth_parameters": {
# #         "login": "saeedhuzaifa678@gmail.com",
# #         "password": "Saeed@47864"
# #     },
# #     "user_context_data": {
# #         "encoded_data": "eyJwYXlsb2FkIjoie1wiY29udGV4dERhdGFcIjp7XCJVc2VyQWdlbnRcIjpcIk1vemlsbGEvNS4wIChXaW5kb3dzIE5UIDEwLjA7IFdpbjY0OyB4NjQpIEFwcGxlV2ViS2l0LzUzNy4zNiAoS0hUTUwsIGxpa2UgR2Vja28pIENocm9tZS8xMjYuMC4wLjAgU2FmYXJpLzUzNy4zNlwiLFwiRGV2aWNlSWRcIjpcIjdvd3QyaWJobHdrYTA0eDB2dnFwOjE3MTk3MzA3Mjg5NzJcIixcIkRldmljZUxhbmd1YWdlXCI6XCJlbi1VU1wiLFwiRGV2aWNlRmluZ2VycHJpbnRcIjpcIk1vemlsbGEvNS4wIChXaW5kb3dzIE5UIDEwLjA7IFdpbjY0OyB4NjQpIEFwcGxlV2ViS2l0LzUzNy4zNiAoS0hUTUwsIGxpa2UgR2Vja28pIENocm9tZS8xMjYuMC4wLjAgU2FmYXJpLzUzNy4zNlBERiBWaWV3ZXI6Q2hyb21lIFBERiBWaWV3ZXI6Q2hyb21pdW0gUERGIFZpZXdlcjpNaWNyb3NvZnQgRWRnZSBQREYgVmlld2VyOldlYktpdCBidWlsdC1pbiBQREY6ZW4tVVNcIixcIkRldmljZVBsYXRmb3JtXCI6XCJXaW4zMlwiLFwiQ2xpZW50VGltZXpvbmVcIjpcIjA1OjAwXCJ9LFwidXNlcm5hbWVcIjpcInNhZWVkaHV6YWlmYTY3OEBnbWFpbC5jb21cIixcInVzZXJQb29sSWRcIjpcIlwiLFwidGltZXN0YW1wXCI6XCIxNzE5NzUxNTE3MTExXCJ9Iiwic2lnbmF0dXJlIjoiY2hmUGhwb0NFQnc0Q1N5MEFnOFgvYVh1NER0SGpzWlk3N0tITnpUMEc4TT0iLCJ2ZXJzaW9uIjoiSlMyMDE3MTExNSJ9"
# #     }
# # }

# # # Make the POST request
# # response = requests.post(url, params=params, headers=headers, json=payload)

# # # Print the response
# # print(response.status_code)
# # print(response.text)









# # import requests
# # # Define the URL



# # url1 = "https://ro.login.olx.com/oauth2/token"

# # # Define the payload
# # payload1 = {
# #     "client_id": "7gantjdsv7233vniq4dthhm2hh",
# #     "code_verifier": "ht2g3KWozr6bijoCPY0H5GujXMWztzVVHUoPnJr-3~V",
# #     "grant_type": "authorization_code",
# #     "code": "a895e0c0-ea0c-49f2-b3c8-8534a2b5aca8",
# #     "redirect_uri": "https://www.olx.ro/d/callback/"
# # }
# # response = requests.post(url1, data=payload1)

# # if response.status_code == 200:
# #     # Parse the JSON response
# #     response_json = response.json()
    
# #     # Extract the access token
# #     access_token = response_json.get("access_token")
    
# #     if access_token:
# #         print(f"Access Token: {access_token}")
# #     else:
# #         print("Access token not found in the response.")
# # else:
# #     print(f"Failed to get access token. Status code: {response.status_code}")
# #     print(response.text)

# # url = "https://production-graphql.eu-sharedservices.olxcdn.com/graphql"
# # headers = {
# #     # ":authority": "production-graphql.eu-sharedservices.olxcdn.com",
# #     # ":method": "POST",
# #     # ":path": "/graphql",
# #     # ":scheme": "https",
# #     "Accept": "*/*",
# #     "Accept-Encoding": "gzip, deflate, br, zstd",
# #     "Accept-Language": "ro",
# #     "Authorization": "Bearer eyJraWQiOiJtZmw2TWJhd1Q0WVBSUUFpc3RPQnl3THlnRk5ZMmtuREhFcmRmYWpCYkxBPSIsImFsZyI6IlJTMjU2In0.eyJzdWIiOiIzYTM0MTkwZC04MDhmLTQ1YmYtOWYxNC1jZTBiMzBlNzA3YTMiLCJpc3MiOiJodHRwczpcL1wvY29nbml0by1pZHAuZXUtY2VudHJhbC0xLmFtYXpvbmF3cy5jb21cL2V1LWNlbnRyYWwtMV9nUzQwQnRUNHAiLCJjbGllbnRfaWQiOiI3Z2FudGpkc3Y3MjMzdm5pcTRkdGhobTJoaCIsIm9yaWdpbl9qdGkiOiI1YjY0MGI4Ny0xZGI1LTQ1MzQtOTViYS03YjEyYzU2MmUyOWYiLCJldmVudF9pZCI6ImQwZTg5ZTVhLTlhM2QtNGViYS1hZjUyLTdiOGFiZjEyMTRkNCIsInRva2VuX3VzZSI6ImFjY2VzcyIsInNjb3BlIjoiYXdzLmNvZ25pdG8uc2lnbmluLnVzZXIuYWRtaW4iLCJhdXRoX3RpbWUiOjE3MTk3MzEwMDIsImV4cCI6MTcxOTczMTkwMiwiaWF0IjoxNzE5NzMxMDAyLCJqdGkiOiJjNDc0ZmY0Ni1lZmI0LTQxZmYtYmY3NC0xY2IwN2JjYjFiMzQiLCJ1c2VybmFtZSI6Ijg1YzhhM2M4LTUzYjAtNGY5Ni1iMjVhLTQ5NDBmMWY3NjhhMSJ9.i26ZYS07ExvuahAJ6HhCtartazDa1y2FZjo6bPL_VwANSJnJF5k8G5avaM71S1vDdGhz2zYEpkBWDlvso9Z90DKAriK429nYERZ1HaKKj2SLzANNEACpeZA5RsvKgcGXCrhPNqcY_mtXLp5VNauKfYKgjSqsgEK13POuidCvsIWqy66c0qBeWvJU8g1BoKqvRmvyE3lQ5qPFwLH7n_pNlP5PeuY5u4xlFJyKY7pN9Zc4eXVpunWiEETq-edlwYeII5yOyUEVN2cc7SPZwzBhiBl0Nq-jHKkQJ5nj8SWT8YiCxDPXYOKRohhNIdgSq7-9yfsBaJzF3h1d4orCxC8Ejg,",
# #     "Content-Length": "116",
# #     "Content-Type": "application/json",
# #     "Origin": "https://www.olx.ro",
# #     "Priority": "u=1, i",
# #     "Referer": "https://www.olx.ro/",
# #     "Sec-Ch-Ua": '"Not/A)Brand";v="8", "Chromium";v="126", "Google Chrome";v="126"',
# #     "Sec-Ch-Ua-Mobile": "?0",
# #     "Sec-Ch-Ua-Platform": '"Windows"',
# #     "Sec-Fetch-Dest": "empty",
# #     "Sec-Fetch-Mode": "cors",
# #     "Sec-Fetch-Site": "cross-site",
# #     "Site": "olxro",
# #     "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
# #     "X-Client": "DESKTOP",
# #     "X-Fingerprint": "MTI1NzY4MzI5MTsxMjswOzA7MDsxOzA7MDswOzA7MDsxOzE7MTsxOzE7MTsxOzE7MTsxOzE7MTsxOzE7MDsxOzE7MTswOzA7MTsxOzE7MTsxOzE7MTsxOzE7MTsxOzE7MTswOzE7MTswOzE7MTsxOzA7MDswOzA7MDswOzE7MDsxOzE7MDswOzA7MTswOzA7MTsxOzA7MTsxOzE7MTswOzE7MDs0MTAwOTMzODI7MjsyOzI7MjswOzI7NTsyODQ4MDA2NDE4OzEzNTcwNDE3Mzg7MTsxOzE7MTswOzE7MTsxOzE7MTsxOzE7MTsxOzE7MTsxOzA7MDswOzQxMDAyMTk5OzM0NjkzMDY1NTE7MjQ3ODUxNDMzMTs3ODUyNDcwMjk7MTAwNTMwMTIwMzsxNTM2Ozg2NDsyNDsyNDszMDA7MzAwOzM2MDszMDA7MzYwOzMwMDszMDA7MzAwOzMwMDszMDA7MzAwOzMwMDszMDA7MzAwOzMwMDszMDA7MzAwOzMwMDszMDA7MzAwOzMwMDszMDA7MzAwOzA7MDsw"
# # }

# # payload = {
# #     "operationName": "UserAccess",
# #     "query": "query UserAccess {\n  myAds {\n    userAccessEnabled\n  }\n}",
# #     "variables": {}
# # }

# # response = requests.post(url, headers=headers, json=payload)
# # print(response.status_code)
# # print(response.json())
