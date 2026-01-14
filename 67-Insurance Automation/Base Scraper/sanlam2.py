# from datetime import date
# from datetime import date
# import time
# import requests
# import json
# import os
# def add_months(d: date, months: int) -> date:
#     year = d.year + (d.month - 1 + months) // 12
#     month = (d.month - 1 + months) % 12 + 1

#     # handle month-end overflow (e.g., Jan 31 + 1 month)
#     day = min(
#         d.day,
#         [31,
#          29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28,
#          31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1]
#     )

#     return date(year, month, day)


# def send_pricing_request(duration_months: int):
#     if duration_months not in (6, 12):
#         raise ValueError("duration_months must be 6 or 12")

#     sitekey = "6Lc7hCwhAAAAAEQUw-IQFycwsHhQKmRsUFD_xBgF"
#     pageurl = "https://souscription-en-ligne.sanlam.ma/assurance-auto-simulation"

#     recaptcha_token = ""

#     start = date.today()
#     end = add_months(start, duration_months)

#     payload = {
#         "driver": {
#             "licenseNumber": "1111111111",
#             "licenseDate": "2026-01-13",
#             "licenseCategory": "B",
#             "lastName": "Huzaifa",
#             "firstName": "Saeed",
#             "birthDate": "2004-02-10",
#             "CIN": "BJ1111111",
#             "sex": "M",
#             "nature": "1",
#             "adress": "sample addresse",
#             "city": "AKLIM",
#             "phoneNumber": "+212522435939",
#             "title": "0",
#             "profession": "12",
#             "isDriver": True
#         },
#         "subscriber": {
#             "isDriver": True,
#             "nature": "1",
#             "CIN": "BJ1111111",
#             "civility": "0",
#             "lastName": "Huzaifa",
#             "firstName": "Saeed",
#             "birthDate": "2004-02-10",
#             "adress": "sample addresse",
#             "city": "AKLIM",
#             "phoneNumber": "+212522435939",
#             "licenseNumber": "1111111111",
#             "licenseDate": "2026-01-13",
#             "licenseCategory": "B",
#             "profession": "12",
#             "postalCode": "20300",
#             "sex": "M"
#         },
#         "vehicle": {
#             "registrationNumber": "11111-A-7",
#             "brand": "10",
#             "horsePower": "4",
#             "model": "Autres",
#             "usageCode": "1",
#             "registrationFormat": "3",
#             "newValue": 850000,
#             "combustion": "E",
#             "circulationDate": "2022-02-08",
#             "marketValue": 398060,
#             "seatsNumber": 5
#         },
#         "policy": {
#             "startDate": start.isoformat(),
#             "endDate": end.isoformat(),
#             "maturityContractType": "2",
#             "duration": duration_months
#         },
#         "agent": {
#             "agentkey": "60593"
#         },
#         "recaptcha": recaptcha_token
#     }
#     print(f"Payload build for months : {duration_months} : {payload}")

#     headers = {
#         "Content-Type": "application/json",
#         "Accept": "application/json",
#         "User-Agent": "Mozilla/5.0"
#     }

#     PRICING_URL = "https://souscription-en-ligne.sanlam.ma/api/auto/recalculate-pricing"
#     r = requests.post(PRICING_URL, json=payload, headers=headers, timeout=60)
#     r.raise_for_status()

#     pricing_json = r.json()

#     os.makedirs("results1", exist_ok=True)
#     with open("results1/pricing.json", "w", encoding="utf-8") as f:
#         json.dump(pricing_json, f, ensure_ascii=False, indent=2)

#     formulas = pricing_json["data"]["formulas"]
#     policy_id = pricing_json["data"]["savedPolicy"]["id"]

#     FORMULA_URL = "https://souscription-en-ligne.sanlam.ma/api/auto/formula-pricing"

#     for idx, formula in enumerate(formulas, start=1):
#         formula_payload = {
#             "formula": formula,
#             "agent": {"agentkey": "60593"},
#             "id": policy_id
#         }

#         resp = requests.post(FORMULA_URL, json=formula_payload, headers=headers, timeout=60)
#         print(f"Formula {idx} status:", resp.status_code)

#         result_json = resp.json()
#         filename = f"results1/formula_{idx}_{formula['name'].replace(' ', '_')}.json"
#         with open(filename, "w", encoding="utf-8") as f:
#             json.dump(result_json, f, ensure_ascii=False, indent=2)

#         time.sleep(1)
# if __name__ == "__main__":
#     send_pricing_request(6)   # 6 months
#     # send_pricing_request(12)  # 12 months


import time
import requests
import json
import os
from datetime import datetime
from dateutil.relativedelta import relativedelta
def send_pricing_request(duration_months=6):
    # --- Dynamic date calculation ---
    today = datetime.today().date()
    start_date = today
    # Subtract 1 day to get server-accepted end date
    end_date = start_date + relativedelta(months=duration_months) - relativedelta(days=1)

    start_date_str = start_date.strftime("%Y-%m-%d")
    end_date_str = end_date.strftime("%Y-%m-%d")

    # Hardcoded driver and subscriber dates (you can also make them dynamic if needed)
    license_date = "2026-01-13" #(today - relativedelta(years=2)).strftime("%Y-%m-%d")  # example license date 2 yrs ago
    birth_date = "2004-02-10"  # example, you can make dynamic if required

    recaptcha_token = ""

    payload = {
        "driver": {
            "licenseNumber": "1111111111",
            "licenseDate": license_date,
            "licenseCategory": "B",
            "lastName": "Huzaifa",
            "firstName": "Saeed",
            "birthDate": birth_date,
            "CIN": "BJ1111111",
            "sex": "M",
            "nature": "1",
            "adress": "sample addresse",
            "city": "AKLIM",
            "phoneNumber": "+212522435939",
            "title": "0",
            "profession": "12",
            "isDriver": True
        },
        "subscriber": {
            "isDriver": True,
            "nature": "1",
            "CIN": "BJ1111111",
            "civility": "0",
            "lastName": "Huzaifa",
            "firstName": "Saeed",
            "birthDate": birth_date,
            "adress": "sample addresse",
            "city": "AKLIM",
            "phoneNumber": "+212522435939",
            "licenseNumber": "1111111111",
            "licenseDate": license_date,
            "licenseCategory": "B",
            "profession": "12",
            "postalCode": "20300",
            "sex": "M"
        },
        "vehicle": {
            "registrationNumber": "11111-A-7",
            "brand": "10",
            "horsePower": "4",
            "model": "Autres",
            "usageCode": "1",
            "registrationFormat": "3",
            "newValue": 850000,
            "combustion": "E",
            "circulationDate": "2022-02-08",
            "marketValue": 398060,
            "seatsNumber": 5
        },
        "policy": {
            "startDate": start_date_str,
            "endDate": end_date_str,
            "maturityContractType": "2",
            "duration": duration_months
        },
        "agent": {
            "agentkey": "60593"
        },
        "recaptcha": recaptcha_token
    }

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0"
    }

    PRICING_URL = "https://souscription-en-ligne.sanlam.ma/api/auto/recalculate-pricing"
    r = requests.post(PRICING_URL, json=payload, headers=headers, timeout=60)
    r.raise_for_status()

    pricing_json = r.json()

    # Save original pricing response
    os.makedirs("results_dynamic", exist_ok=True)
    with open("results_dynamic/pricing.json", "w", encoding="utf-8") as f:
        json.dump(pricing_json, f, ensure_ascii=False, indent=2)

    formulas = pricing_json["data"]["formulas"]
    policy_id = pricing_json["data"]["savedPolicy"]["id"]

    FORMULA_URL = "https://souscription-en-ligne.sanlam.ma/api/auto/formula-pricing"

    for idx, formula in enumerate(formulas, start=1):
        formula_payload = {
            "formula": formula,
            "agent": {"agentkey": "60593"},
            "id": policy_id
        }

        resp = requests.post(FORMULA_URL, json=formula_payload, headers=headers, timeout=60)
        print(f"Formula {idx} status:", resp.status_code)

        result_json = resp.json()

        filename = f"results_dynamic/formula_{idx}_{formula['name'].replace(' ', '_')}.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(result_json, f, ensure_ascii=False, indent=2)

        time.sleep(1)  # small delay between hits

if __name__ == "__main__":
    send_pricing_request(duration_months=12)  # You can change to 12 for 12 months

