#File_Name="parsedatabase.py"
#The Following Code fetch The stored html content in database And Parse the html content and saved all information
#The Following Code is too much slow and not usedful in this project,so we will use multiprocessing technique

import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import dataset
proxy = "http://adf1f9b7b95b8a8e4bcc__cr.sg:eb36@gw.dataimpulse.com:823"

proxies = {
    "http": proxy,
    "https": proxy
}
def checktext(tag):
    if tag:
        return tag.getText().strip()
    else:
        return "N/A"
def extract_ul_list(ul_element):
    """Extracts all list items from a <ul> element and returns them as a formatted list."""
    if not ul_element:
        return "N/A"
    
    items = ul_element.find_all("li")
    return "\n".join([f"• {item.text.strip()}" for item in items])
def concatenate_div_text(main_div):
    """Concatenates text from all child <div> elements in a main <div>, each on a new line with numbering."""
    if not main_div:
        return "No content found."
    
    divs = main_div.find_all("div",recursive=False)
    return "\n".join([f"{i+1}. {div.get_text(separator=' ', strip=True)}" for i, div in enumerate(divs) if div.text.strip()])

def get_records_in_batches(table, batch_size=1000):
    """Fetch records in batches to optimize memory usage."""
    offset = 0
    while True:
        records = list(table.find(_limit=batch_size, _offset=offset))
        if not records:
            break
        yield records
        offset += batch_size

def scrape_1mg_data(url):
    # url = "https://www.1mg.com/drugs/cordef-6mg-tablet-807854"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
    }
    db = dataset.connect("sqlite:///MedicineMain2.db")  # Change this for other DBs
    table = db["Scraped"]
    # records=list(table.find())
    result=[]
    index=0
    # print(len(list(records)))
    for batch in get_records_in_batches(table, 50):
        for databaserow in batch: 
            # index=index+1
            # if index==10:
            #     break           
            # soup = BeautifulSoup(response.text, "html.parser")
            print(databaserow["index"])
            soup = BeautifulSoup(databaserow["Html_Content"], "lxml")
            data = {
                "Drup Name": "",
                "Marketer": "",
                "Salt Composition": "",
                "Storage": "",
                "Product Introduction": "",
                "Uses": "",
                "Benefits": "",
                "How to Use": "",
                "How Drug Work": "",
                "Side Effects": "",
                "If You Forget To Take": "",
                "Common Side Effect": "",
                "Quick Tips": "",
                "Interaction with drugs": "",
                "FAQs": "",
                "Saftey Advise(Alcohol)": "",
                "Saftey Advise(Pregnancy)": "",
                "Saftey Advise(Breast feeding)": "",
                "Saftey Advise(Driving)": "",
                "Saftey Advise(Kidney)": "",
                "Saftey Advise(Liver)": "",
                "Fact Box(Chemical Class)": "",
                "Fact Box(Habit Forming)": "",
                "Fact Box(Therapeutic Class)": "",
                "Fact Box(Action Class)": ""
            }
            
            # Extracting drug name
            name_tag = soup.find("h1", class_="DrugHeader__title-content___2ZaPo")
            data["Drup Name"] = checktext(name_tag)
            
            # Extracting price
            marketer = soup.find("div", class_="DrugHeader__meta-value___vqYM0")
            data["Marketer"] = checktext(marketer)

            titilerow = soup.find_all("div", class_="DrugHeader__meta-title___22zXC")
            for row in titilerow:
                next_sibling=row.find_next_sibling()
                if "SALT COMPOSITION" in row.text.strip():
                    data["Salt Composition"]=checktext(next_sibling)
                elif "Storage" in row.text.strip():
                    data["Storage"] = checktext(next_sibling)
            
            
            drugviewrow = soup.find_all("h2", class_="DrugOverview__title___1OwgG")
            for row in drugviewrow:
                next_sibling=row.find_next_sibling()
                if "Product introduction" in row.text.strip():
                    data["Product Introduction"] =checktext(next_sibling)
                elif "Uses of" in row.text.strip():
                    ul_list=next_sibling.find("ul")
                    if ul_list:
                        data["Uses"]=extract_ul_list(ul_list)
                    else:
                        data["Uses"] = checktext(next_sibling)
                elif "Benefits" in row.text.strip():
                    data["Benefits"]=checktext(next_sibling)
                elif "How to use" in row.text.strip():
                    data["How to Use"]=checktext(next_sibling)
                elif "works" in row.text.strip():
                    data["How Drug Work"]=checktext(next_sibling)
                elif "Side effects" in row.text.strip():
                    data["Side Effects"]=checktext(next_sibling)
                elif "forget" in row.text.strip():
                    data["If You Forget To Take"]=checktext(next_sibling)
            

            divsideeffect = soup.find("div", class_="DrugOverview__list-container___2eAr6")
            if divsideeffect:
                ul_side=divsideeffect.find("ul")
                data["Common Side Effect"]=extract_ul_list(ul_side)


            divquick_tips=soup.find("div", class_="ExpertAdviceItem__content___1Djk2")
            if divquick_tips:
                ul_quick=divquick_tips.find("ul")
                data["Quick Tips"]=extract_ul_list(ul_quick)


            divinteraction=soup.find("div", class_="DrugInteraction__content___1gXvf")
            if divinteraction:
                maindiv=divinteraction.find("div",recursive=False)
                data["Interaction with drugs"]= concatenate_div_text(maindiv)  #maindiv.get_text(separator='\n', strip=True)   #


            divfaqs=soup.find("div", class_="Faqs__tile___1B58W")
            if divfaqs:
                # maindiv=divinteraction.find("div",recursive=False)
                data["FAQs"]= divfaqs.get_text(separator='\n', strip=True)  #concatenate_div_text(divfaqs)


            safteywrow = soup.find_all("div", class_="DrugOverview__warning-top___UD3xX")
            for row in safteywrow:
                next_sibling=row.find_next_sibling()
                if "Alcohol" in row.text.strip():
                    data["Saftey Advise(Alcohol)"] =checktext(next_sibling)
                elif "Pregnancy" in row.text.strip():
                    data["Saftey Advise(Pregnancy)"] =checktext(next_sibling)
                elif "Breast feeding" in row.text.strip():
                    data["Saftey Advise(Breast feeding)"]=checktext(next_sibling)
                elif "Driving" in row.text.strip():
                    data["Saftey Advise(Driving)"]=checktext(next_sibling)
                elif "Kidney" in row.text.strip():
                    data["Saftey Advise(Kidney)"]=checktext(next_sibling)
                elif "Liver" in row.text.strip():
                    data["Saftey Advise(Liver)"]=checktext(next_sibling)


            factrow = soup.find_all("div", class_="DrugFactBox__flex___1bp8c")
            for row in factrow:
                next_sibling=row.find_next_sibling()
                if "Chemical Class" in row.text.strip():
                    data["Fact Box(Chemical Class)"] =checktext(row).replace("Chemical Class","").strip()
                elif "Habit Forming" in row.text.strip():
                    data["Fact Box(Habit Forming)"] =checktext(row).replace("Habit Forming","").strip()
                elif "Therapeutic Class" in row.text.strip():
                    data["Fact Box(Therapeutic Class)"] =checktext(row).replace("Therapeutic Class","").strip()
                elif "Action Class" in row.text.strip():
                    data["Fact Box(Action Class)"] =checktext(row).replace("Action Class","").strip()
            
            # data.update(row)
                # print(row["index"])
            combined_dict = {**databaserow, **data}  # Merging both dicts
            result.append(combined_dict)    
            
            # Extracting manufacturer
            # manufacturer_tag = soup.find("div", class_="DrugHeader__meta-value___vqYM0")
            # data["manufacturer"] = manufacturer_tag.text.strip() if manufacturer_tag else "N/A"
            
            # # Extracting description
            # description_tag = soup.find("div", class_="MedicineOverview__content___2eEou")
            # data["description"] = description_tag.text.strip() if description_tag else "N/A"
            
    return result
    
if __name__ == "__main__":
    scraped_data = scrape_1mg_data("")
    df=pd.DataFrame(scraped_data)
    df.to_excel("test4.xlsx",index=False)
    # print(scraped_data)