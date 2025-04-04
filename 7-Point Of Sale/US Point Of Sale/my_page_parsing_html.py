from bs4 import BeautifulSoup
import pprint
import dataset
import pandas as pd
import re
main_list=[]
# Read the HTML file from the local directory
for i in range(1,4):
    if i==2:
        continue
    with open(f'html_files/index{i}.html', 'r', encoding='utf-8') as file:
        html_content = file.read()

# 
    # html_content=single_company["html"]
    # Parse the HTML content with BeautifulSoup
    soup = BeautifulSoup(html_content, 'html.parser')
    # print(soup.text)
    # Find all div elements with class 'review-card'
    review_cards = soup.find_all('div', {'data-test-id':'review-card'})
    print(len(review_cards))
    vendor="Vagaro"
    def check_existence(item):
        if item:
            return item.text.strip()
        else:
            return ""
    # Iterate through each div and print its content or process further
    for card in review_cards:
        ease_of_use=customer_services=value_for_money=features=likelihood=overall_rating=""
        date=review_source=source=review_name=review_role=country=used_software=employess=industry=""
        main_div=card.find("div",recursive=False)
        sub_div=main_div.find_all("div",recursive=False)
        user_info_div=sub_div[0]
        review_div=main_div.find('div',{"data-testid":"review-content"})

        review_name_div=user_info_div.find("div",{"data-testid":"reviewer-full-name"})
        # print(review_name_div)
        if review_name_div:
            dialog_div=review_name_div.find('div',{"role":"dialog"})
            # print(dialog_div)
            if dialog_div:
                dialog_div.decompose()
            review_name=review_name_div.text.strip()
        # review_name=check_existence()
        # review_name=check_existence(user_info_div.find("div",{"data-testid":"reviewer-full-name"}))

        review_role=check_existence(user_info_div.find("div",{"data-testid":"reviewer-job-title"}))

        

        industry=check_existence(user_info_div.find("span",{"data-testid":"reviewer-industry"}))
        employess=check_existence(user_info_div.find("span",{"data-testid":"reviewer-company-size"}))

        used_software=check_existence(user_info_div.find("div",{"data-testid":"reviewer-time-used-product"})).replace("Used the software for:","").strip()
        
        ease_of_use=check_existence(user_info_div.find("div",{"data-testid":"Ease of Use-rating"}))
        overall_rating=check_existence(user_info_div.find("div",{"data-testid":"Overall Rating-rating"}))
        customer_services=check_existence(user_info_div.find("div",{"data-testid":"Customer Service-rating"}))
        features=check_existence(user_info_div.find("div",{"data-testid":"Features-rating"}))
        value_for_money=check_existence(user_info_div.find("div",{"data-testid":"Value for Money-rating"}))

        #Detail For likelihood
        likelihood_div=user_info_div.find("div",{"data-testid":"Likelihood to Recommend-rating"})
        if likelihood_div:
            progress=likelihood_div.find("progress")
            max=progress.get("max")
            value=progress.get("value")
            likelihood=f"{value}"

        #detail For Review Source
        review_source_div=user_info_div.find("div",{"data-testid":"reviewer-source"})
        if review_source_div:
            review_source=check_existence(review_source_div.find("div",{"role":"dialog"}))
        
        source=check_existence(user_info_div.find("div",{"data-testid":"source-site"})).replace("Source:","").strip()
        date=check_existence(user_info_div.find("div",{"data-testid":"review-written-on"}))

        # Now Scrape Review Content
        review_title=pros=cons=comments=alternative_considered=reason_for_choosing=reason_for_switiching=switch_from=""

        review_title=check_existence(review_div.find("div",class_="mt-2xl text-lg font-bold md:mt-0")).replace('"', '')
        # print(review_title)
        comments=check_existence(review_div.find("div",{"data-testid":"overall-content"})).replace("Overall:","").strip()
        pros=check_existence(review_div.find("div",{"data-testid":"pros-content"})).replace("Pros:","").strip()
        cons=check_existence(review_div.find("div",{"data-testid":"cons-content"})).replace("Cons:","").strip()
        switch_from=check_existence(review_div.find("div",{"data-testid":"switched-products"})).replace("Switched From:","").strip()
        alternative_considered=check_existence(review_div.find("div",{"data-testid":"alternatives-considered"})).replace("Alternatives Considered:","").strip()
        # alternative_considered=check_existence(review_div.find("div",{"data-testid":"alternatives-considered"})).replace("Alternatives Considered:","").strip()

        # Scraped Reason for switching
        reason_for_switiching_div=review_div.find("div",{"data-testid":"reasons-for-switching-content"})
        if reason_for_switiching_div:
            reason_for_switiching_div.find("strong").decompose()
            reason_for_switiching=reason_for_switiching_div.text.strip()
        

        reason_for_choosing_div=review_div.find("div",{"data-testid":"reasons-for-choosing-content"})
        if reason_for_choosing_div:
            reason_for_choosing_div.find("strong").decompose()
            reason_for_choosing=reason_for_choosing_div.text.strip()
        # reason_for_switiching=check_existence(review_div.find("div",{"data-testid":"reasons-for-switching-content"})).replace("Reasons for Switching to","").strip()

        obj={
                    "Vendor":vendor,
                    "Review Date": date,
                    "Review Source":review_source,
                    "Source":source,
                    "Reviewer Name":review_name,
                    "Review Role":review_role,
                    "Industry":industry,
                    "Number of Employees":employess,
                    "Used Software For":used_software,
                    "Reviewer Company":"",
                    "Country":country,
                    "Review Title":review_title,
                    "Overall Feedback":comments,
                    "Pros":pros,
                    "Cons":cons,
                    "Alternative Considered": alternative_considered,
                    "Reasons for Choosing Vendor": reason_for_choosing,
                    "Switched From (Previos Vendor)":switch_from,
                    "Reasons for Switching to Vendor":reason_for_switiching,
                    "Overall Rating (Out of 5)":overall_rating,
                    "Ease of Use Rating (Out of 5)":ease_of_use,
                    "Customer Support Rating (Out of 5)":customer_services,
                    "Value for Money Rating (Out of 5)":value_for_money,
                    "Features Rating (Out of 5)": features,
                    "Liklihood to Recommend (Out of 10)":likelihood,    
                }
        # pprint.pprint(obj)
        main_list.append(obj)
        # break


    # print(f"Review Card {index}:")
    # print(card.prettify())  # You can change this to process the div's content as needed
    # print('-' * 50)  # Separator for better readability
def remove_illegal_characters(value):
    if isinstance(value, str):
        # Remove control characters with ASCII code < 32, except for \t, \n, and \r
        return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", value)
    return value
df=pd.DataFrame(main_list)
# Assuming `df` is your DataFrame
df_cleaned = df.applymap(remove_illegal_characters)

df.to_csv("VagaroTesting3.csv")