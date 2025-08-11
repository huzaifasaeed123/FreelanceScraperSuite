import dataset
import pandas as pd
import os
import sqlite3
import re

def remove_duplicate_phones(row):
    if row['Telefon 1'] == row['Telefonnummer']:
        row['Telefon 1'] = None
    if row['Telefonnummer'] == row['Mobiltelefon 1']:
        row['Telefonnummer'] = None
    if row['Telefonnummer'] == row['Mobiltelefon 2']:
        row['Telefonnummer'] = None
    return row


def sort_phones(row):
    row['landline_number_1'] = None
    row['landline_number_2'] = None
    row['landline_number_3'] = None
    # row['landline_number_4'] = None
    # row['landline_number_5'] = None
    row['mobile_number_1'] = None
    row['mobile_number_2'] = None
    row['mobile_number_3'] = None
    # row['mobile_number_4'] = None
    # row['mobile_number_5'] = None

    all_phones = []
    for number in ['Telefonnummer', 'Telefon 1', 'Telefon 2', 'Mobiltelefon 1', 'Mobiltelefon 2']:
        if row[number] is not None:
            all_phones.append(row[number])
    all_phones = [x for x in list(set(all_phones)) if x != '']

    mobile_phones = []
    landline_phones = []
    for phone in all_phones:
        if phone.startswith('+4176'):
            mobile_phones.append(phone)
        elif phone.startswith('+4177'):
            mobile_phones.append(phone)
        elif phone.startswith('+4178'):
            mobile_phones.append(phone)
        elif phone.startswith('+4179'):
            mobile_phones.append(phone)
        else:
            landline_phones.append(phone)

    for i, phone in enumerate(mobile_phones, 1):
        row[f'mobile_number_{i}'] = phone

    for i, phone in enumerate(landline_phones, 1):
        row[f'landline_number_{i}'] = phone

    for number in ['Telefonnummer', 'Telefon 1', 'Telefon 2', 'Mobiltelefon 1', 'Mobiltelefon 2']:
        try:
            del row[number]
        except Exception:
            pass
    return row


def clean_emails(row):
    if row['Email'] == row['Emailadresse']:
        row['Email'] = None
    elif (row['Emailadresse'] is None or row['Emailadresse'] == '') and (row['Email'] is not None and row['Email'] != ''):
        row['Emailadresse'] = row['Email']
        row['Email'] = None
    return row


def move_website_to_webseite(row):
    if row['Webseite'] is None and row['Website'] is not None:
        row['Webseite'] = row['Website']
        row['Website'] = None

    if row['Webseite'] is not None and row['Website'] is not None:
        if row['Webseite'].strip() == row['Website'].strip():
            row['Website'] = None
    return row


def normalize_phones(r):
    if r is None:
        return None
    r = r.replace("'", '').strip()
    if r.startswith('0'):
        return '+41' + r[1:]
    return r

def run_matching(database):
    def extract_postal_code(url):
        match = re.search(r"/(\d{4})/", url)
        return match.group(1) if match else None

    conn = sqlite3.connect(f"{database}.db")
    cursor = conn.cursor()

    # Create matched table if not exists
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS matched (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        local_id INTEGER,
        money_id INTEGER
    )
    """)
    conn.commit()

    # Fetch MoneyHouse data
    cursor.execute("SELECT id, Name, PLZ FROM MoneyHouse")
    money_data = cursor.fetchall()

    # Build dictionary: name -> list of (money_id, plz)
    money_dict = {}
    for mid, mname, plz in money_data:
        if mname and plz:
            key = mname.strip().lower()
            money_dict.setdefault(key, []).append((mid, str(plz)))

    # Fetch Local data
    cursor.execute("SELECT id, Name, Url FROM Local")
    local_data = cursor.fetchall()

    matches = []
    seen_pairs = set()

    for lid, lname, url in local_data:
        if not (lname and url):
            continue
        key = lname.strip().lower()
        local_plz = extract_postal_code(url)

        if key in money_dict:
            for mid, money_plz in money_dict[key]:
                if local_plz and local_plz == money_plz:
                    pair = (mid, local_plz)
                    if pair not in seen_pairs:
                        matches.append((lid, mid))
                        seen_pairs.add(pair)
                    break  # Stop after first valid match

    # Insert matches
    if matches:
        cursor.executemany("INSERT INTO matched (local_id, money_id) VALUES (?,?)", matches)
        conn.commit()

    conn.close()
    print(f"✅ Inserted {len(matches)} matches into 'matched' table.")

def OutPutFormatting():
    database="Final_Combined"
    # run_matching(database)
    db = dataset.connect(f'sqlite:///{database}.db')

    grouped_q = """select 
        Kanton,
        MoneyHouse.Name as Firma,
        Geschäftsleitung,
        "neuste Zeichnungsberechtigte",
        "neuste Verwaltungsräte",
        "Präsident",
        "Leiter der Zweigniederlassungen",
        "LinkedIn Link",
        Telefonnummer,
        "Mobiltelefon 1",
        Webseite,
        Emailadresse,
        Rechtsform,
        Adresse,
        PLZ,
        ORT,
        "Alter",
        Branche,
        Firmenzweck as Details,
        Mitarbeiter,
        Umsatz,
        "UID Number",
        L.Url as LocalUrl,
        MoneyHouse.Url as MoneyHouseUrl,
        L.Name as LocalName,
        Address,
        Email,
        Website,
        "Telefon 1",
        "Telefon 2",
        "Mobiltelefon 2",
        "WhatsApp 1",
        "WhatsApp 2"
    from MoneyHouse
        left join matched on matched.money_id = MoneyHouse.id
        left join main.Local L on matched.local_id = L.id;"""

    raw_grouped_df = pd.DataFrame([x for x in db.query(grouped_q)])

    grouped_df = raw_grouped_df.copy()
    for column in ['Telefonnummer', 'Telefon 1', 'Telefon 2', 'Mobiltelefon 1', 'Mobiltelefon 2', 'WhatsApp 1', 'WhatsApp 2']:
        grouped_df[column] = grouped_df[column].apply(normalize_phones)

    grouped_df = grouped_df.apply(sort_phones, axis=1)
    grouped_df = grouped_df.apply(clean_emails, axis=1)
    grouped_df = grouped_df.apply(move_website_to_webseite, axis=1)
    grouped_df['PLZ'] = grouped_df['PLZ'].apply(lambda x: str(x).replace('.0', ''))

    small_columns = [
        'Kanton', 'Firma', 'Geschäftsleitung', "neuste Zeichnungsberechtigte", "neuste Verwaltungsräte",
        'Präsident', 'Leiter der Zweigniederlassungen', 'LinkedIn Link',
        'landline_number_1', "mobile_number_1", 'Webseite', 'Emailadresse',
        'Rechtsform', 'Adresse', 'PLZ', 'ORT', "Alter", 'Branche', 'Details',
        'Mitarbeiter'
    ]
    all_columns = small_columns + [col for col in grouped_df.columns if col not in small_columns]

    # Ensure output directories exist
    output_dir_l = 'branche_spreadsheets_L'
    os.makedirs(output_dir_l, exist_ok=True)
    output_dir_s = 'branche_spreadsheets_S'
    os.makedirs(output_dir_s, exist_ok=True)

    # Prepare combined DataFrames
    combined_large_df = pd.DataFrame(columns=all_columns)
    combined_small_df = pd.DataFrame(columns=small_columns)

    # Iterate over Branche values
    for branche in grouped_df['Branche'].unique():
        print(branche)
        if branche is None:
            continue

        branche_df = grouped_df[grouped_df['Branche'] == branche].sort_values(by=['Kanton', 'PLZ', 'ORT'])

        # File paths
        file_path_large = os.path.join(output_dir_l, f"format_L_{branche.replace(' ', '_').replace('/', '_')}.xlsx")
        file_path_small = os.path.join(output_dir_s, f"format_s_{branche.replace(' ', '_').replace('/', '_')}.xlsx")

        # Save individual branche files
        branche_df[all_columns].to_excel(file_path_large, index=False)
        branche_df[small_columns].to_excel(file_path_small, index=False)

        # Append to combined
        combined_large_df = pd.concat([combined_large_df, branche_df[all_columns]], ignore_index=True)
        combined_small_df = pd.concat([combined_small_df, branche_df[small_columns]], ignore_index=True)

    # Sort and save combined files
    combined_large_df = combined_large_df.sort_values(by=['Kanton', 'PLZ', 'ORT'])
    combined_small_df = combined_small_df.sort_values(by=['Kanton', 'PLZ', 'ORT'])

    combined_large_df.to_excel("combined_large.xlsx", index=False)
    combined_small_df.to_excel("combined_small.xlsx", index=False)

OutPutFormatting()
