#You need to update Authorization in headers after every 1 hr as it got expires
#The Following Code use Recursive approach in which it go down to child while maintaing its level as we do in depth First Search
import requests
import pandas as pd
url = "https://id.who.int/icd/release/11/2025-01/mms"

headers = {
    "api-version": "v2",
    "authorization": "Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJuYmYiOjE3NDMwNDg5NzAsImV4cCI6MTc0MzA1MjU3MCwiaXNzIjoiaHR0cHM6Ly9pY2RhY2Nlc3NtYW5hZ2VtZW50Lndoby5pbnQiLCJhdWQiOlsiaHR0cHM6Ly9pY2RhY2Nlc3NtYW5hZ2VtZW50Lndoby5pbnQvcmVzb3VyY2VzIiwiaWNkYXBpIl0sImNsaWVudF9pZCI6IjFiYzhkODRkLTliYTYtNDc5OC04OTYyLWY1NjBhODM0N2Y5YV9iMWU0NTAwYi0yOGM2LTQ5NmMtOWU1Zi1jZjIxMTViMTdkMzMiLCJzY29wZSI6WyJpY2RhcGlfYWNjZXNzIl19.aQm4kU_KBZSEcyeJnoRlkn5mDoE34bnzmITiuwvy_4r_L6CzfQmc1TMtXMmwD_jD9IiVxd_IW31ve5ko2zJA1mpkEs6mhjLMyTaRkvlFugfn46fDhc4EZxlBJXoZBIhFTAj7jGCbwrNl_OU6xKKktkxqB2SA1lOuza7Njj_jvUKkTosxo8GVvlU6QYPvShmZrnYSK0sT_1aRls5q4L9an6k_eUSnAMtmtBNrn21btj3ei-f0tKxy2SYCWwQtaW5F9w1m3O2O_93X4cKWe7Wj-7X3TGEbaEADHbSVjSNkV1eDAKMzrbWuNFagqVHvIUTuCYgr66xW2qJoHws-vKyjQw",
    "referer": "https://icd.who.int/",
    "accept-language":"en",
    "sec-ch-ua": '"Chromium";v="134", "Not:A-Brand";v="24", "Google Chrome";v="134"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"
}
def format_labels_as_bullets(data_list):
    if not data_list:  # Check if list is empty
        return ""  # Return a default string if empty
    bullet_points = [f"• {item['label']['@value']}" for item in data_list if 'label' in item and '@value' in item['label']]
    return "\n".join(bullet_points)
# Adjust CSV formatting
def create_csv(data, path):
    max_level = max(len(row["Heading"]) for row in data)
    print(f"Max Heading Level: {max_level}")  # Add debug print for max_level

    rows = []
    for row in data:
        # Check if Heading field is correct before proceeding
        if not row["Heading"]:
            print(f"Warning: Missing Heading in data for title: {row['title']}")
        fixed_data = [
            row["title"], row["code"], row["classKind"], row["blockId"],
            row["codeRange"], row["browserUrl"], row["definition"],
            row["exclusion"], row["indexTerm"], row["inclusion"], row["codedelsewhere"]
        ]
        
        # Normalize Heading hierarchy depth
        level_data = row["Heading"] + [""] * (max_level - len(row["Heading"]))
        rows.append(fixed_data + level_data)

    fixed_columns = ["Title", "Code", "ClassKind", "Block ID", "Code Range", "Browser URL", "Definition",
                     "Exclusion", "Index Term", "Inclusion", "Coded Elsewhere"]
    
    level_columns = [f"Level_{i+1}" for i in range(max_level)]
    columns = fixed_columns + level_columns

    df = pd.DataFrame(rows, columns=columns)
    df.to_excel(path, index=False)
    print(f"CSV file created at {path}")

def process_each_link(child,heading_list,main_data,check):
    response1 = requests.get(child, headers=headers)
        
    if response1.status_code == 200:
        data = response1.json()
        exclusion=format_labels_as_bullets(data.get("exclusion", []))
        indexTerm=format_labels_as_bullets(data.get("indexTerm", []))
        inclusion=format_labels_as_bullets(data.get("inclusion", []))
        codedelsewhere=format_labels_as_bullets(data.get("foundationChildElsewhere", []))
        title = data.get("title", {}).get("@value") or ""
        definition = data.get("definition", {}).get("@value") or ""
        code= data.get("code", "")
        classKind= data.get("classKind", "")
        blockId= data.get("blockId", "")
        codeRange= data.get("codeRange", "")
        browserUrl=data.get("browserUrl","") 
        heading_list.append(title)
        obj1={
            "title": title,
            "code": code,
            "classKind": classKind,
            "blockId": blockId,
            "codeRange": codeRange,
            "browserUrl": browserUrl,
            "definition": definition,
            "exclusion": exclusion,
            "indexTerm": indexTerm,
            "inclusion": inclusion,
            "codedelsewhere": codedelsewhere,
            "Heading": heading_list.copy(),
        }
        print(obj1)
        main_data.append(obj1)
        new_children = data.get("child", [])
        # if check==0:
        #     check=1
        if new_children:  # Check if there  re new children
            for child in new_children:
                process_each_link(child,heading_list,main_data,check)
        heading_list.pop()

    else:
        print(f"Error occurred while fetching: {child} and error details is {response1.text}")
    print()

response = requests.get(url, headers=headers)
check=0
childlist=[]
main_data=[]
if response.status_code == 200:
    childlist = response.json().get("child", [])  # Use .get() to avoid KeyError
    for index, child in enumerate(childlist):
        if index>=10 and index<=30:
            heading_list=[]
            process_each_link(child,heading_list,main_data,check)
        # break
else:
    print(f"Error in the Main Url: {response.status_code}, {response.text}")

create_csv(main_data, "ICD_dataFinal8.xlsx")



#The Following Code is specific if specific data is missing
# response = requests.get(url, headers=headers)
# check=0
# childlist=[]
# main_data=[]
# if response.status_code == 200:
#     numbers = [
#     "56475710",
#     "437215757",
#     "1991139272",
#     "555078855",
#     "687250607",
#     "411368752"
# ]
#     base_url = "https://id.who.int/icd/release/11/2025-01/mms/"

# # Generating links
#     childlist = [f"{base_url}{num}" for num in numbers]
#     for child in childlist:
#         heading_list=[]
#         process_each_link(child,heading_list,main_data,check)
#         # break
# else:
#     print(f"Error in the Main Url: {response.status_code}, {response.text}")

# create_csv(main_data, "ICD_dataFinal1.xlsx")
