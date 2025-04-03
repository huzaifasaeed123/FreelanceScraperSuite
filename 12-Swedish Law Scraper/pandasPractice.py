import pandas as pd

# Extended sample data with more elements in the groups
data = [
    {
        "Title Of Law": "A1", "Law ID": "B1", "Version as of": "C1", "Entry into force of the decree": "D1", "Decision Date": "E1",
        "Level": ["G1_1", "G1_2"], "Article No": "123", "Article Title": "Swis Etc", "Paragraph": ["H1_1", "H1_2", "H1_3"], "SubPara": [], "Footer": []
    },
    {
        "Title Of Law": "A2", "Law ID": "B2", "Version as of": "C2", "Entry into force of the decree": "D2", "Decision Date": "E2",
        "Level": ["G2_1", "G2_2", "G2_3", "G2_4"], "Article No": "456", "Article Title": "Swiss Law", "Paragraph": ["H2_1", "H2_2"], "SubPara": ["SubPara2_1"], "Footer": ["Footer2_1"]
    },
    {
        "Title Of Law": "A3", "Law ID": "B3", "Version as of": "C3", "Entry into force of the decree": "D3", "Decision Date": "E3",
        "Level": ["G3_1", "G3_2", "G3_3", "G3_4", "G3_5"], "Article No": "789", "Article Title": "Another Law", "Paragraph": ["H3_1"], "SubPara": ["SubPara3_1", "SubPara3_2", "SubPara3_3"], "Footer": []
    },
    {
        "Title Of Law": "A4", "Law ID": "B4", "Version as of": "C4", "Entry into force of the decree": "D4", "Decision Date": "E4",
        "Level": ["G4_1"], "Article No": "101112", "Article Title": "Law Title 4", "Paragraph": ["H4_1", "H4_2", "H4_3", "H4_4"], "SubPara": ["SubPara4_1"], "Footer": ["Footer4_1", "Footer4_2"]
    }
]

# Identify maximum lengths of varying column groups
max_level = max(len(row["Level"]) for row in data)
max_paragraph = max(len(row["Paragraph"]) for row in data)
max_subpara = max(len(row["SubPara"]) for row in data)
max_footer = max(len(row["Footer"]) for row in data)

# Create a DataFrame
rows = []
for row in data:
    fixed_data = [
        row["Title Of Law"], row["Law ID"], row["Version as of"], 
        row["Entry into force of the decree"], row["Decision Date"], 
        row["Article No"], row["Article Title"]
    ]
    
    level_data = row["Level"] + ["" for _ in range(max_level - len(row["Level"]))]
    paragraph_data = row["Paragraph"] + ["" for _ in range(max_paragraph - len(row["Paragraph"]))]
    subpara_data = row["SubPara"] + ["" for _ in range(max_subpara - len(row["SubPara"]))]
    footer_data = row["Footer"] + ["" for _ in range(max_footer - len(row["Footer"]))]
    
    rows.append(fixed_data + level_data + paragraph_data + subpara_data + footer_data)

# Create column names
fixed_columns = ["Title Of Law", "Law ID", "Version as of", "Entry into force of the decree", "Decision Date", "Article No", "Article Title"]
level_columns = [f"Level_{i+1}" for i in range(max_level)]
paragraph_columns = [f"Paragraph_{i+1}" for i in range(max_paragraph)]
subpara_columns = [f"SubPara_{i+1}" for i in range(max_subpara)]
footer_columns = [f"Footer_{i+1}" for i in range(max_footer)]

columns = fixed_columns + level_columns + paragraph_columns + subpara_columns + footer_columns

df = pd.DataFrame(rows, columns=columns)

# Save to CSV
csv_file_path = "output.csv"
df.to_csv(csv_file_path, index=False)

print(f"CSV file has been created at {csv_file_path}")
