# import requests
# import json

# url = "https://hk.centanet.com/findproperty/api/Transaction/Search"

# headers = {
#     "Accept": "application/json, text/plain, */*",
#     "Accept-Encoding": "gzip, deflate, br, zstd",
#     "Accept-Language": "en-US,en;q=0.9",
#     "Authorization": "Bearer eyJhbGciOiJSUzI1NiIsImtpZCI6IkY3MkYxRDVFMThEMjRDMDc4QzUyREVFMEEzRTZEQjI3NzE2RDE0Q0RSUzI1NiIsInR5cCI6ImF0K2p3dCIsIng1dCI6Ijl5OGRYaGpTVEFlTVV0N2dvLWJiSjNGdEZNMCJ9.eyJuYmYiOjE3MTk1ODUyODYsImV4cCI6MTcyNzM2MTI4NiwiaXNzIjoiaHR0cHM6Ly9tcy5jZW50YW5ldC5jb20vbWVtYmVyIiwiYXVkIjpbImNlbnRhbmV0YXBpIiwiaHR0cHM6Ly9tcy5jZW50YW5ldC5jb20vbWVtYmVyL3Jlc291cmNlcyJdLCJjbGllbnRfaWQiOiJudXh0X2N1c3RvbV9vaWRjIiwic3ViIjoiYTcyZTRhZjgtMTgxMS00MDkyLWE3YWMtZmIyZmVkNzczZDZhIiwiYXV0aF90aW1lIjoxNzE5NTg1Mjg2LCJpZHAiOiJsb2NhbCIsImxvZ2luX3R5cGUiOiJBbm9ueW1vdXMiLCJqdGkiOiI0NzA0QUIwMTJBQUJFNUY1Njg2MUZBNTA0RDY3NjhFRSIsImlhdCI6MTcxOTU4NTI4Niwic2NvcGUiOlsiY2VudGFuZXRhcGkiXX0.vyzRZncodv5P77QgQ_WAhLSggPisilZ57uHqyGj-6HQdM8lu9FA2vG7gyzYiOowM4HCfcgfodrzLR8AwFFIGsUj5B4P8vCJeqHPFB0TzJzrRWjk3n5L-BpweuxM2vKCVZNBZxdTfjZjC2QC-5dzdz2Vl1Uk0P5Iq15Jtc2WPuS7pW45aeQT6N4nVixpsN1zDeYI3kkPZ-b7LlbjID0Y9_jHGzvlpJa60dGVvdxOz6BqqkjiixTAZOPCN9XMQXIoIdlgl-M6EO2z0iSlnYUi3Ar8J9rXGQv7Ebf0wCp-oHKv893VnUxws6zifsw5sovRTJaCrRY09fCczkhsF4tyR8w",
#     "Connection": "keep-alive",
#     "Content-Length": "213",
#     "Content-Type": "application/json",
#     "Cookie": "ANONYMOUS_ID_COOKIE=a72e4af8-1811-4092-a7ac-fb2fed773d6a; ANONYMOUS_TOKEN_COOKIE=eyJhbGciOiJSUzI1NiIsImtpZCI6IkY3MkYxRDVFMThEMjRDMDc4QzUyREVFMEEzRTZEQjI3NzE2RDE0Q0RSUzI1NiIsInR5cCI6ImF0K2p3dCIsIng1dCI6Ijl5OGRYaGpTVEFlTVV0N2dvLWJiSjNGdEZNMCJ9.eyJuYmYiOjE3MTk1ODUyODYsImV4cCI6MTcyNzM2MTI4NiwiaXNzIjoiaHR0cHM6Ly9tcy5jZW50YW5ldC5jb20vbWVtYmVyIiwiYXVkIjpbImNlbnRhbmV0YXBpIiwiaHR0cHM6Ly9tcy5jZW50YW5ldC5jb20vbWVtYmVyL3Jlc291cmNlcyJdLCJjbGllbnRfaWQiOiJudXh0X2N1c3RvbV9vaWRjIiwic3ViIjoiYTcyZTRhZjgtMTgxMS00MDkyLWE3YWMtZmIyZmVkNzczZDZhIiwiYXV0aF90aW1lIjoxNzE5NTg1Mjg2LCJpZHAiOiJsb2NhbCIsImxvZ2luX3R5cGUiOiJBbm9ueW1vdXMiLCJqdGkiOiI0NzA0QUIwMTJBQUJFNUY1Njg2MUZBNTA0RDY3NjhFRSIsImlhdCI6MTcxOTU4NTI4Niwic2NvcGUiOlsiY2VudGFuZXRhcGkiXX0.vyzRZncodv5P77QgQ_WAhLSggPisilZ57uHqyGj-6HQdM8lu9FA2vG7gyzYiOowM4HCfcgfodrzLR8AwFFIGsUj5B4P8vCJeqHPFB0TzJzrRWjk3n5L-BpweuxM2vKCVZNBZxdTfjZjC2QC-5dzdz2Vl1Uk0P5Iq15Jtc2WPuS7pW45aeQT6N4nVixpsN1zDeYI3kkPZ-b7LlbjID0Y9_jHGzvlpJa60dGVvdxOz6BqqkjiixTAZOPCN9XMQXIoIdlgl-M6EO2z0iSlnYUi3Ar8J9rXGQv7Ebf0wCp-oHKv893VnUxws6zifsw5sovRTJaCrRY09fCczkhsF4tyR8w; ga4_user_id=a72e4af8-1811-4092-a7ac-fb2fed773d6a; ga4_anoymous=true; gr_user_id=162cb7f5-58fb-4daa-aea6-1ebd6ad4c261; 986e0ca578ece71a_gr_session_id=285e0789-e965-44ed-84d5-36143fce731d; 986e0ca578ece71a_gr_session_id_sent_vst=285e0789-e965-44ed-84d5-36143fce731d; _fbp=fb.1.1719585353637.79378700917324936; 986e0ca578ece71a_gr_last_sent_sid_with_cs1=285e0789-e965-44ed-84d5-36143fce731d; 986e0ca578ece71a_gr_last_sent_cs1=a72e4af8-1811-4092-a7ac-fb2fed773d6a; _gcl_au=1.1.47658845.1719585356; _gid=GA1.2.324556034.1719585356; __rtbh.lid=%7B%22eventType%22%3A%22lid%22%2C%22id%22%3A%22ZbhLmyiBcA0UvgnTXqcp%22%7D; _ga=GA1.3.1090243156.1719585354; _gid=GA1.3.324556034.1719585356; ROUTE_COOKIE=%2Fen%2Flist%2Ftransaction%2FTsuen-Wan-Mid-levels_19-HMA101%3Fq%3D33e7b9d1c9; _ga=GA1.2.1090243156.1719585354; _ga_G8G5RGTSSC=GS1.1.1719585354.1.1.1719586964.60.0.0; _ga_MLE5MEFTW0=GS1.1.1719585355.1.1.1719586964.60.0.0; 986e0ca578ece71a_gr_cs1=a72e4af8-1811-4092-a7ac-fb2fed773d6a",
#     "Host": "hk.centanet.com",
#     "Lang": "en",
#     "Origin": "https://hk.centanet.com",
#     "Referer": "https://hk.centanet.com/findproperty/en/list/transaction/Tsuen-Wan-Mid-levels_19-HMA101?q=33e763ddaf",
#     "Sec-Ch-Ua": "\"Not/A)Brand\";v=\"8\", \"Chromium\";v=\"126\", \"Google Chrome\";v=\"126\"",
#     "Sec-Ch-Ua-Mobile": "?0",
#     "Sec-Ch-Ua-Platform": "\"Windows\"",
#     "Sec-Fetch-Dest": "empty",
#     "Sec-Fetch-Mode": "cors",
#     "Sec-Fetch-Site": "same-origin",
#     "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
# }

# payload = {
#     "postType": "Both",
#     "day": "Day1095",
#     "sort": "InsOrRegDate",
#     "hmas": ["HMA101"],
#     "markets": [],
#     "mtrs": [],
#     "offset": 0,
#     "order": "Descending",
#     "pageSource": "search",
#     "primarySchoolNets": [],
#     "size": 24,
#     "typeCodes": ["19-HMA101"]
# }

# for i in range(1,9):
#     payload["offset"] =  i * 24
#     response = requests.post(url, data=json.dumps(payload))
#     print(f"Iteration {i+1}, Status Code: {response.status_code}")
#     print(response.json())
#     break
# import urllib3
# import json

# url = "https://hk.centanet.com/findproperty/api/Transaction/Search"
# headers = {
#     "Accept": "application/json, text/plain, */*",
#     "Accept-Encoding": "gzip, deflate, br, zstd",
#     "Accept-Language": "en-US,en;q=0.9",
#     "Authorization": "Bearer eyJhbGciOiJSUzI1NiIsImtpZCI6IkY3MkYxRDVFMThEMjRDMDc4QzUyREVFMEEzRTZEQjI3NzE2RDE0Q0RSUzI1NiIsInR5cCI6ImF0K2p3dCIsIng1dCI6Ijl5OGRYaGpTVEFlTVV0N2dvLWJiSjNGdEZNMCJ9.eyJuYmYiOjE3MTk1ODUyODYsImV4cCI6MTcyNzM2MTI4NiwiaXNzIjoiaHR0cHM6Ly9tcy5jZW50YW5ldC5jb20vbWVtYmVyIiwiYXVkIjpbImNlbnRhbmV0YXBpIiwiaHR0cHM6Ly9tcy5jZW50YW5ldC5jb20vbWVtYmVyL3Jlc291cmNlcyJdLCJjbGllbnRfaWQiOiJudXh0X2N1c3RvbV9vaWRjIiwic3ViIjoiYTcyZTRhZjgtMTgxMS00MDkyLWE3YWMtZmIyZmVkNzczZDZhIiwiYXV0aF90aW1lIjoxNzE5NTg1Mjg2LCJpZHAiOiJsb2NhbCIsImxvZ2luX3R5cGUiOiJBbm9ueW1vdXMiLCJqdGkiOiI0NzA0QUIwMTJBQUJFNUY1Njg2MUZBNTA0RDY3NjhFRSIsImlhdCI6MTcxOTU4NTI4Niwic2NvcGUiOlsiY2VudGFuZXRhcGkiXX0.vyzRZncodv5P77QgQ_WAhLSggPisilZ57uHqyGj-6HQdM8lu9FA2vG7gyzYiOowM4HCfcgfodrzLR8AwFFIGsUj5B4P8vCJeqHPFB0TzJzrRWjk3n5L-BpweuxM2vKCVZNBZxdTfjZjC2QC-5dzdz2Vl1Uk0P5Iq15Jtc2WPuS7pW45aeQT6N4nVixpsN1zDeYI3kkPZ-b7LlbjID0Y9_jHGzvlpJa60dGVvdxOz6BqqkjiixTAZOPCN9XMQXIoIdlgl-M6EO2z0iSlnYUi3Ar8J9rXGQv7Ebf0wCp-oHKv893VnUxws6zifsw5sovRTJaCrRY09fCczkhsF4tyR8w",
#     "Connection": "keep-alive",
#     "Content-Length": "213",
#     "Content-Type": "application/json",
#     "Cookie": "ANONYMOUS_ID_COOKIE=a72e4af8-1811-4092-a7ac-fb2fed773d6a; ANONYMOUS_TOKEN_COOKIE=eyJhbGciOiJSUzI1NiIsImtpZCI6IkY3MkYxRDVFMThEMjRDMDc4QzUyREVFMEEzRTZEQjI3NzE2RDE0Q0RSUzI1NiIsInR5cCI6ImF0K2p3dCIsIng1dCI6Ijl5OGRYaGpTVEFlTVV0N2dvLWJiSjNGdEZNMCJ9.eyJuYmYiOjE3MTk1ODUyODYsImV4cCI6MTcyNzM2MTI4NiwiaXNzIjoiaHR0cHM6Ly9tcy5jZW50YW5ldC5jb20vbWVtYmVyIiwiYXVkIjpbImNlbnRhbmV0YXBpIiwiaHR0cHM6Ly9tcy5jZW50YW5ldC5jb20vbWVtYmVyL3Jlc291cmNlcyJdLCJjbGllbnRfaWQiOiJudXh0X2N1c3RvbV9vaWRjIiwic3ViIjoiYTcyZTRhZjgtMTgxMS00MDkyLWE3YWMtZmIyZmVkNzczZDZhIiwiYXV0aF90aW1lIjoxNzE5NTg1Mjg2LCJpZHAiOiJsb2NhbCIsImxvZ2luX3R5cGUiOiJBbm9ueW1vdXMiLCJqdGkiOiI0NzA0QUIwMTJBQUJFNUY1Njg2MUZBNTA0RDY3NjhFRSIsImlhdCI6MTcxOTU4NTI4Niwic2NvcGUiOlsiY2VudGFuZXRhcGkiXX0.vyzRZncodv5P77QgQ_WAhLSggPisilZ57uHqyGj-6HQdM8lu9FA2vG7gyzYiOowM4HCfcgfodrzLR8AwFFIGsUj5B4P8vCJeqHPFB0TzJzrRWjk3n5L-BpweuxM2vKCVZNBZxdTfjZjC2QC-5dzdz2Vl1Uk0P5Iq15Jtc2WPuS7pW45aeQT6N4nVixpsN1zDeYI3kkPZ-b7LlbjID0Y9_jHGzvlpJa60dGVvdxOz6BqqkjiixTAZOPCN9XMQXIoIdlgl-M6EO2z0iSlnYUi3Ar8J9rXGQv7Ebf0wCp-oHKv893VnUxws6zifsw5sovRTJaCrRY09fCczkhsF4tyR8w"
# }

# http = urllib3.PoolManager(cert_reqs='CERT_NONE')

# for i in range(1,8):
#     payload = {
#         "postType": "Both",
#         "day": "Day1095",
#         "sort": "InsOrRegDate",
#         "hmas": ["HMA101"],
#         "markets": [],
#         "mtrs": [],
#         "offset": i * 24,
#         "order": "Descending",
#         "pageSource": "search",
#         "primarySchoolNets": [],
#         "size": 24,
#         "typeCodes": ["19-HMA101"]
#     }

#     encoded_data = json.dumps(payload).encode('utf-8')
#     response = http.request('POST', url, headers=headers, body=encoded_data)
#     print(json.loads(response.data.decode('utf-8')))
#     break
import requests
import certifi
import json

url = "https://hk.centanet.com/findproperty/api/Transaction/Search"
headers = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Accept-Language": "en-US,en;q=0.9",
    "Authorization": "Bearer eyJhbGciOiJSUzI1NiIsImtpZCI6IkY3MkYxRDVFMThEMjRDMDc4QzUyREVFMEEzRTZEQjI3NzE2RDE0Q0RSUzI1NiIsInR5cCI6ImF0K2p3dCIsIng1dCI6Ijl5OGRYaGpTVEFlTVV0N2dvLWJiSjNGdEZNMCJ9.eyJuYmYiOjE3MTk1ODUyODYsImV4cCI6MTcyNzM2MTI4NiwiaXNzIjoiaHR0cHM6Ly9tcy5jZW50YW5ldC5jb20vbWVtYmVyIiwiYXVkIjpbImNlbnRhbmV0YXBpIiwiaHR0cHM6Ly9tcy5jZW50YW5ldC5jb20vbWVtYmVyL3Jlc291cmNlcyJdLCJjbGllbnRfaWQiOiJudXh0X2N1c3RvbV9vaWRjIiwic3ViIjoiYTcyZTRhZjgtMTgxMS00MDkyLWE3YWMtZmIyZmVkNzczZDZhIiwiYXV0aF90aW1lIjoxNzE5NTg1Mjg2LCJpZHAiOiJsb2NhbCIsImxvZ2luX3R5cGUiOiJBbm9ueW1vdXMiLCJqdGkiOiI0NzA0QUIwMTJBQUJFNUY1Njg2MUZBNTA0RDY3NjhFRSIsImlhdCI6MTcxOTU4NTI4Niwic2NvcGUiOlsiY2VudGFuZXRhcGkiXX0.vyzRZncodv5P77QgQ_WAhLSggPisilZ57uHqyGj-6HQdM8lu9FA2vG7gyzYiOowM4HCfcgfodrzLR8AwFFIGsUj5B4P8vCJeqHPFB0TzJzrRWjk3n5L-BpweuxM2vKCVZNBZxdTfjZjC2QC-5dzdz2Vl1Uk0P5Iq15Jtc2WPuS7pW45aeQT6N4nVixpsN1zDeYI3kkPZ-b7LlbjID0Y9_jHGzvlpJa60dGVvdxOz6BqqkjiixTAZOPCN9XMQXIoIdlgl-M6EO2z0iSlnYUi3Ar8J9rXGQv7Ebf0wCp-oHKv893VnUxws6zifsw5sovRTJaCrRY09fCczkhsF4tyR8w",
    "Connection": "keep-alive",
    "Content-Length": "213",
    "Content-Type": "application/json",
    "Cookie": "ANONYMOUS_ID_COOKIE=a72e4af8-1811-4092-a7ac-fb2fed773d6a; ANONYMOUS_TOKEN_COOKIE=eyJhbGciOiJSUzI1NiIsImtpZCI6IkY3MkYxRDVFMThEMjRDMDc4QzUyREVFMEEzRTZEQjI3NzE2RDE0Q0RSUzI1NiIsInR5cCI6ImF0K2p3dCIsIng1dCI6Ijl5OGRYaGpTVEFlTVV0N2dvLWJiSjNGdEZNMCJ9.eyJuYmYiOjE3MTk1ODUyODYsImV4cCI6MTcyNzM2MTI4NiwiaXNzIjoiaHR0cHM6Ly9tcy5jZW50YW5ldC5jb20vbWVtYmVyIiwiYXVkIjpbImNlbnRhbmV0YXBpIiwiaHR0cHM6Ly9tcy5jZW50YW5ldC5jb20vbWVtYmVyL3Jlc291cmNlcyJdLCJjbGllbnRfaWQiOiJudXh0X2N1c3RvbV9vaWRjIiwic3ViIjoiYTcyZTRhZjgtMTgxMS00MDkyLWE3YWMtZmIyZmVkNzczZDZhIiwiYXV0aF90aW1lIjoxNzE5NTg1Mjg2LCJpZHAiOiJsb2NhbCIsImxvZ2luX3R5cGUiOiJBbm9ueW1vdXMiLCJqdGkiOiI0NzA0QUIwMTJBQUJFNUY1Njg2MUZBNTA0RDY3NjhFRSIsImlhdCI6MTcxOTU4NTI4Niwic2NvcGUiOlsiY2VudGFuZXRhcGkiXX0.vyzRZncodv5P77QgQ_WAhLSggPisilZ57uHqyGj-6HQdM8lu9FA2vG7gyzYiOowM4HCfcgfodrzLR8AwFFIGsUj5B4P8vCJeqHPFB0TzJzrRWjk3n5L-BpweuxM2vKCVZNBZxdTfjZjC2QC-5dzdz2Vl1Uk0P5Iq15Jtc2WPuS7pW45aeQT6N4nVixpsN1zDeYI3kkPZ-b7LlbjID0Y9_jHGzvlpJa60dGVvdxOz6BqqkjiixTAZOPCN9XMQXIoIdlgl-M6EO2z0iSlnYUi3Ar8J9rXGQv7Ebf0wCp-oHKv893VnUxws6zifsw5sovRTJaCrRY09fCczkhsF4tyR8w"
}

for i in range(1,8):
    payload = {
        "postType": "Both",
        "day": "Day1095",
        "sort": "InsOrRegDate",
        "hmas": ["HMA101"],
        "markets": [],
        "mtrs": [],     
        "offset": i * 24,
        "order": "Descending",
        "pageSource": "search",
        "primarySchoolNets": [],
        "size": 24,
        "typeCodes": ["19-HMA101"]
    }

    response = requests.post(url, headers=headers, data=json.dumps(payload), verify=certifi.where())
    print(response.json())
    break
