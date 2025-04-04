import requests
import json
import pandas as pd
import re
from bs4 import BeautifulSoup
from datetime import datetime
import time

# Input file
input_data_dict = {}
input_data = pd.read_csv("results.csv")
addresses = input_data["Adresse postale"].to_list()
names_list = input_data["Nom"].to_list()

# Organize input data by postal code
for address in addresses:
    add = address.split(" ")
    postal_code = add[-2] + add[-1]
    if postal_code not in input_data_dict.keys():
        input_data_dict[postal_code] = []

for i in range(len(names_list)):
    add = addresses[i].split(" ")
    postal_code = add[-2] + add[-1]
    input_data_dict[postal_code].append(names_list[i])

# Process each postal code and scrape data
keys = input_data_dict.keys()
for key in keys:
    try:
        temp_names_list = input_data_dict[key]
        print(temp_names_list)

        url = f"http://mobile.canada411.ca/search/?stype=pc&pc={key}"
        page_res = requests.get(url)
        soup = BeautifulSoup(page_res.content, 'lxml')
        contact_divs = soup.find_all("div", class_="c411Listing jsResultsList")

        for div in contact_divs:
            print(div)
            name = div.find("h2", class_="c411ListedName").text.upper()
            last_name = name.split(" ")[-1]
            phone_no = div.find("span", class_="c411Phone").text

            for temp_name in temp_names_list:
                first_name = temp_name.split(" ")[0]
                if first_name == last_name:
                    print(name)
                    print(phone_no)
                    print("")

    except Exception as e:
        print(e)
