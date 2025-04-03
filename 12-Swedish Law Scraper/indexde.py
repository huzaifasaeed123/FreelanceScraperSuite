import pandas as pd
from bs4 import BeautifulSoup
import re
import requests
from datetime import datetime
import locale
import traceback
def getpreface(soup):
    preface_div = soup.find('div', id='preface')
    surnumber="Not Available"
    first_paragraph_text = preface_div.find('p', class_='srnummer')
    if first_paragraph_text:
        surnumber=first_paragraph_text.text.strip()
    # erlasstitel_elements = soup.find_all(class_='erlasstitel', recursive=False)
    # h1_text = " ".join(element.get_text(separator=" ").strip() for element in erlasstitel_elements) if erlasstitel_elements else ""

    # # Extract text from all elements with the class 'erlasskurztitel'
    # erlasskurztitel_elements = soup.find_all(class_='erlasskurztitel', recursive=False)
    # h2_text = " ".join(element.get_text(separator=" ").strip() for element in erlasskurztitel_elements) if erlasskurztitel_elements else ""

    # # Combine h2 text with h1 text
    # h1_text = f"{h1_text} {h2_text}".strip()
    # erlasstitel_elements = preface_div.find_all(class_='erlasstitel', recursive=False)
    # h1_text = " ".join(element.get_text(separator=" ").strip() for element in erlasstitel_elements) if erlasstitel_elements else ""
    Abbreviation="Not Present"
    h1_element = preface_div.find(class_='erlasstitel',recursive=False)
    if h1_element:
        h1_text = h1_element.get_text()
    else:
        h1_text = ""

    h2_element = preface_div.find(class_='erlasskurztitel',recursive=False)
    if h2_element:
        h2_text = h2_element.get_text()
        Abbreviation=h2_text
        h1_text = f"{h1_text} {h2_text}"
    else:
        h2_text = ""
    # Set locale to French
    # locale.setlocale(locale.LC_TIME, 'fr_FR.UTF-8')
    last_paragraph_text = preface_div.find_all('p',recursive=False)[-1].text.strip()
    #r'\d{1,2}(?:er)?\s+\w+\s+\d{4}'
    dates = re.findall(r'\b(?:vom|Stand am)\s*(\d{1,2}\.\s+\w+\s+\d{4})\b', last_paragraph_text)
    print(dates)
    
    
    formatted_dates = dates

    # print("First paragraph text (srnummer):", first_paragraph_text)
    # print("H1 text (erlasstitel botschafttitel):", h1_text)
    # print("Last paragraph text:", last_paragraph_text)
    # print("Formatted Dates", formatted_dates)
    if(len(formatted_dates)==1):
        return [h1_text, surnumber, formatted_dates[0],"not found"]
    elif(len(formatted_dates)==0):
        return [h1_text, surnumber, "not found","not found"]
    else:
        return [h1_text, surnumber,Abbreviation, formatted_dates[0], formatted_dates[1]]
    

def getfirstSections(soup):
    main_element = soup.find('main', id='maintext')
    sections = main_element.find_all('section', recursive=False)
    return sections
def replace_br_with_space(soup):
    for br in soup.find_all("br"):
        br.replace_with(" ")
def removeSup(section):
    if section:
        sups_tag = section.find_all('sup')
        if sups_tag:
            for sup in sups_tag:
                sup.replace_with(' ')
def extract_and_replace_sup_tags(html_content):
    if html_content:
        sup_tags = html_content.find_all('sup')

        for sup in sup_tags:
            sup_text = sup.get_text(strip=True)
            
            # Check for non-numeric characters and extract them
            non_numeric_part = ''.join(re.findall(r'[^\d]', sup_text))
            numeric_part = ''.join(re.findall(r'\d', sup_text))

            if non_numeric_part and sup.parent:
                # Create a new <i> tag with the non-numeric text
                new_i_tag = soup.new_tag('i')
                new_i_tag.string = non_numeric_part
                
                # Insert the new <i> tag before the <sup> tag
                sup.insert_before(new_i_tag)
                
                # Update the <sup> tag to keep only the numeric part
                sup.string = numeric_part if numeric_part else ''

    return str(soup)
def handle_article(article, mainDatalist, levelList, csvList,date,row):
    try:
        # print(levelList, "Articles ka andr")
        newlevelList=levelList.copy()
        # print(article)
        heading6 = article.find(re.compile(r'^h[1-6]$'), recursive=False)
        # print("Aricle dfjdf")
        # extract_and_replace_sup_tags(article)
        # print(heading6)
        
        extract_and_replace_sup_tags(heading6)
        removeSup(heading6)
        ArtTag = ""
        ArtNo = ""
        heading_text=heading6.get_text()
        pattern = re.compile(r'(Art\.|\§)\s*(\d+[a-zA-Z]*(?:\s*[–-]\s*\d+[a-zA-Z]*|\s*und\s*\d+[a-zA-Z]*)?)\s*(.*)')
        match = pattern.match(heading_text)
        if match:
            ArtNo = match.group(1) + " " + match.group(2)
            ArtTag = match.group(3)
            print(f"Article No: {ArtNo}, Article Title: {ArtTag}")
        else:
            print("No match found")

        # print(ArtNo)
            # print(f"Article No: {article_no}, Article Title: {article_title}")
        # if heading6:
        #     a_tags = heading6.find_all('a')
        #     if a_tags:
        #         if len(a_tags) == 1 or (len(a_tags)>1 and (a_tags[1].get_text(strip=True)=="*" or a_tags[1].get_text(strip=True)=="")) :
        #             a_tag = a_tags[0]
        #             b_tags = a_tag.find_all('b')
        #             i_tags = a_tag.find_all('i')
        #             i_text=""
        #             if i_tags:
        #                 for i in i_tags:
        #                     i_text=i_text+i.get_text(strip=True)
        #                     i.decompose()
        #             ArtNo = " ".join([b.get_text(strip=True) for b in b_tags])
        #             ArtNo=ArtNo+i_text
        #             for b in b_tags:
        #                 b.decompose()
        #             ArtTag = a_tag.get_text(strip=True)
        #         elif len(a_tags) > 1:
        #             ArtNo = a_tags[0].get_text(strip=True)
        #             ArtTag = a_tags[1].get_text(strip=True)

        #         # print(f"Concatenated b tag texts: {ArtNo}")
        #         # print(f"Remaining a tag text: {ArtTag}")

        paragraphList = []
        subparagraphList = []
        footnotesList = []
        collapseable_div = article.find('div', class_='collapseable')
        if collapseable_div:
            # print("Found Collasable")
            # paragraphs = collapseable_div.find_all('p', class_='absatz', recursive=False)
            
            # for paragraph in paragraphs:
            #     paragraphList.append(paragraph.get_text(strip=True))
            
            # subparagraphs = collapseable_div.find_all('dd')
            
            # for subparagraph in subparagraphs:
            #     subparagraphList.append(subparagraph.get_text(strip=True))
            # paragraphList = []

    # Iterate over each paragraph and append the content of the next sibling <dl> element if it exists
            #paragraphs = collapseable_div.find_all('p', class_='absatz', recursive=False)
            
            refenceparagraphs = collapseable_div.find('p',class_="referenz",recursive=False)
            if refenceparagraphs:
                paragraphList.append(refenceparagraphs.get_text())
                refenceparagraphs.decompose()
            else:
                paragraphList.append(" ")
            #print(len(paragraphs))
            # print("dhfjsfjds")
            paragraphs = collapseable_div.find_all('p',recursive=False)
            for paragraph in paragraphs:
                sup=paragraph.find("sup")
                if sup and sup == paragraph.contents[0]:
                    sup_text=f"[{sup.get_text(strip=True)}]"
                    sup.decompose()
                    extract_and_replace_sup_tags(paragraph)
                    removeSup(paragraph)
                    paragraph_text = f"{sup_text} {paragraph.get_text()}"
                else:
                    extract_and_replace_sup_tags(paragraph)
                    removeSup(paragraph)
                    paragraph_text = f"{paragraph.get_text()}"
                next_sibling = paragraph.find_next_sibling()
                
                # Check if the next sibling is a <dl> element
                if next_sibling and next_sibling.name == 'dl':
                    removeSup(next_sibling)
                    extract_and_replace_sup_tags(next_sibling)
            # Combine consecutive <dt> and <dd> elements
                    combined_texts = []
                    dt_elements = next_sibling.find_all('dt')
                    dd_elements = next_sibling.find_all('dd')
                    
                    for dt, dd in zip(dt_elements, dd_elements):
                        dt_text = dt.get_text().replace('.', '')
                        dd_text = dd.get_text()
                        combined_texts.append(f"[{dt_text}] {dd_text}")
                    
                    dl_text = " ".join(combined_texts)
                    paragraph_text += " " + dl_text
                
                paragraphList.append(paragraph_text)
            footnotes_div = collapseable_div.find('div', class_='footnotes', recursive=False)
            
            if footnotes_div:
                footnotes_paragraphs = footnotes_div.find_all('p', recursive=False)
                for footnote in footnotes_paragraphs:
                    removeSup(footnote)
                    footnotesList.append(footnote.get_text(strip=True))
        #print(paragraphList)
        Abbre=row['Abbreviation']
        if Abbre =="Not Present":
            Abbre=mainDatalist[2]
        object1 = {
            "Website Url":row["URL"],"Abbreviation":Abbre,"Title Of Law": mainDatalist[0], "Law ID": mainDatalist[1], "Version as of": date, "Entry into force of the decree": row['InForce'], "Decision Date": row['Decision'],
            "Level": newlevelList, "Article No": ArtNo, "Article Title": ArtTag, "Paragraph": paragraphList, "SubPara": subparagraphList, "Footer": footnotesList
        }
        # print(object1, "before putting in list")
        csvList.append(object1)
    except Exception as e:
        print("Excetion in Article Function",e)
        traceback.print_exc()
def handle_nested_sections(section, mainDatalist, levelList, csvList,date,row):
    # try:
        articlechecker = section.find('article')
        if True: #re.compile(r'^h[1-6]$')
            heading = section.find(class_="heading", recursive=False)
            print("Inside Section For Heading ",heading.get_text())
            if heading:
                removeSup(heading)
                levelList.append(heading.get_text())
            
            collapseable_div = section.find('div', class_='collapseable', recursive=False)
            if collapseable_div:
                # print("Huzaifad")
                nested_sections = collapseable_div.find_all('section', recursive=False)
                special_sections = collapseable_div.find_all('section',id=re.compile(r'lvl'), recursive=False)
                articles = collapseable_div.find_all('article', recursive=False)
                # print(special_sections,nested_sections)
                if articles:
                    for article in articles:
                        handle_article(article, mainDatalist, levelList, csvList,date,row)
                    if nested_sections:
                        for nested_section in nested_sections:
                            collapseable_div2 = nested_section.find('div', class_='collapseable', recursive=False)
                            if collapseable_div2:
                                # print("Simple Check")
                                para2=collapseable_div2.find_all('p',class_='absatz', recursive=False)
                                if para2:
                                    print("Special Check")
                                    handle_article(nested_section, mainDatalist, levelList, csvList,date,row)
                                else:
                                    handle_nested_sections(nested_section, mainDatalist, levelList, csvList,date,row)
                                    print(len(levelList))
                                    if (len(levelList)>0):
                                        # print("Poping")
                                        levelList.pop()
                elif nested_sections:
                    print("Inside Nested For Heading ",heading.get_text())
                    for nested_section in nested_sections:
                        collapseable_div2 = nested_section.find('div', class_='collapseable', recursive=False)
                        if collapseable_div2:
                            # print("Simple Check")
                            para2=collapseable_div2.find_all('p',class_='absatz', recursive=False)
                            if para2:
                                print("Special Check")
                                handle_article(nested_section, mainDatalist, levelList, csvList,date,row)
                            else:
                                handle_nested_sections(nested_section, mainDatalist, levelList, csvList,date,row)
                                print(len(levelList))
                                if (len(levelList)>0):
                                    # print("Poping")
                                    levelList.pop()
                  
        else:
            print("Articles not found In Section")
            return
    # except Exception as e:
    #     print("Excetion in Section Function",e)
def extract_date_from_url(url):
    date_pattern = re.compile(r'/(\d{8})/de/html/fedlex-data-admin-ch-eli-cc-\d+-[^-]+-\d{8}-de-html(-\d+)?\.html$')
    match = date_pattern.search(url)
    if match:
        date_str = match.group(1)
        date_obj = datetime.strptime(date_str, '%Y%m%d')
        formatted_date = date_obj.strftime('%Y-%m-%d')
        return formatted_date
    return None
def createCSVFile(data, path):
    max_level = max(len(row["Level"]) for row in data)
    max_paragraph = max(len(row["Paragraph"]) for row in data)
    max_subpara = max(len(row["SubPara"]) for row in data)
    max_footer = max(len(row["Footer"]) for row in data)

    rows = []
    for row in data:
        fixed_data = [
            row["Website Url"],row["Abbreviation"],row["Title Of Law"], row["Law ID"], row["Version as of"], 
            row["Entry into force of the decree"], row["Decision Date"], 
            row["Article No"], row["Article Title"]
        ]
        
        level_data = row["Level"] + ["" for _ in range(max_level - len(row["Level"]))]
        paragraph_data = row["Paragraph"] + ["" for _ in range(max_paragraph - len(row["Paragraph"]))]
        subpara_data = row["SubPara"] + ["" for _ in range(max_subpara - len(row["SubPara"]))]
        footer_data = row["Footer"] + ["" for _ in range(max_footer - len(row["Footer"]))]
        
        rows.append(fixed_data + level_data + paragraph_data + subpara_data + footer_data)

    fixed_columns = ["Website Url","Abbreviation","Title Of Law", "Law ID", "Version as of", "Entry into force of the decree", "Decision Date", "Article No", "Article Title"]
    level_columns = [f"Level_{i+1}" for i in range(max_level)]
    paragraph_columns = [f"Paragraph_{i}" for i in range(max_paragraph)]
    subpara_columns = [f"SubPara_{i+1}" for i in range(max_subpara)]
    footer_columns = [f"Footer_{i+1}" for i in range(max_footer)]

    columns = fixed_columns + level_columns + paragraph_columns + subpara_columns + footer_columns

    df = pd.DataFrame(rows, columns=columns)

    df.to_csv(path, index=False,encoding='utf-8')

    print(f"CSV file has been created at {path}")

csvList = []

missed_data=[]

df = pd.read_csv('extracteddataDe.csv')
start_range=0
end_range=500
# Iterate over the rows in the DataFrame
for index, row in df.iterrows():
    if index>=start_range and index<=end_range:
        url = row['Special Request URL']
        try:
            date = extract_date_from_url(url)
            print(f"{index}--Processing URL: {url} ")
            # url = "https://www.fedlex.admin.ch/filestore/fedlex.data.admin.ch/eli/cc/54/757_781_799/20240701/en/html/fedlex-data-admin-ch-eli-cc-54-757_781_799-20240701-en-html-2.html"
            # url="https://www.fedlex.admin.ch/filestore/fedlex.data.admin.ch/eli/cc/2007/151/20240101/en/html/fedlex-data-admin-ch-eli-cc-2007-151-20240101-en-html.html"
            # url="https://www.fedlex.admin.ch/filestore/fedlex.data.admin.ch/eli/cc/54/757_781_799/20240701/de/html/fedlex-data-admin-ch-eli-cc-54-757_781_799-20240701-de-html-15.html"
            response = requests.get(url,timeout=120)
            print("Index No Is the",index)
            # if index==10:
            #     break
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                replace_br_with_space(soup)
                main_element = soup.find('main', id='maintext')
                articles = main_element.find_all('article', recursive=False)
                if not articles:
                    sections = getfirstSections(soup)
                    # print(sections)
                    mainDatalist = getpreface(soup)
                    # continue
                    # index = 0
                    for section in sections:
                        levelList = []
                        # index = index + 1
                        # extract_and_replace_sup_tags(section)
                        handle_nested_sections(section, mainDatalist, levelList, csvList,date,row)
                    # break  
                else:
                    mainDatalist=getpreface(soup)
                    for article in articles:
                        levelList=[]
                        handle_article(article, mainDatalist, levelList, csvList,date,row)     
            else:
                print(f"Failed to retrieve the URL. Status code: {response.status_code}")
            # break
        except Exception as e:
            print("Exception has been occur",e) 
            missed_data.append(row)
            traceback.print_exc()
            # break  
# Output
print("Completed processing all URLs and dates.")

# createCSVFile(csvList, f"Fr({start_range}-{end_range}).csv")
createCSVFile(csvList, f"De({start_range}-{end_range}).csv")

df = pd.DataFrame(missed_data)

# Write the DataFrame to a CSV file
df.to_csv(f"MissingDe({start_range}-{end_range}).csv", index=False)
