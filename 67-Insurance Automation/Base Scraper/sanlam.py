import time
import requests
import json
import os

from twocaptcha import TwoCaptcha

solver = TwoCaptcha('8b5ac125222ae8ebd4fd6b3535f69787')



def get_recaptcha_token(sitekey: str, pageurl: str) -> str:
    """
    This function is intentionally abstract.

    In a real implementation, this is where you would:
    1. Send a task to your captcha provider with (sitekey, pageurl)
    2. Poll until the task is solved
    3. Return the solved token string

    Replace the body of this function with your own logic.
    """
    # ---- PLACEHOLDER ----
    # Simulate waiting for a solver

    result = solver.recaptcha(sitekey=sitekey,
    url=pageurl)
    print(result)

    # Return a dummy token so the rest of the pipeline works
    return result["code"]


def send_pricing_request():
    sitekey = "6Lc7hCwhAAAAAEQUw-IQFycwsHhQKmRsUFD_xBgF"
    pageurl = "https://souscription-en-ligne.sanlam.ma/assurance-auto-simulation"

    # recaptcha_token = get_recaptcha_token(sitekey, pageurl)   #no need to use this fuction,captcha empty hardcoded token will be enough
    recaptcha_token = ""
    payload = {
        "driver": {
            "licenseNumber": "1111111111",
            "licenseDate": "2026-01-13",
            "licenseCategory": "B",
            "lastName": "Huzaifa",
            "firstName": "Saeed",
            "birthDate": "2004-02-10",
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
            "birthDate": "2004-02-10",
            "adress": "sample addresse",
            "city": "AKLIM",
            "phoneNumber": "+212522435939",
            "licenseNumber": "1111111111",
            "licenseDate": "2026-01-13",
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
            "startDate": "2026-01-14",
            "endDate": "2027-01-13",
            "maturityContractType": "2",
            "duration": 12
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
    os.makedirs("results1", exist_ok=True)
    with open("results1/pricing.json", "w", encoding="utf-8") as f:
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

        filename = f"results1/formula_{idx}_{formula['name'].replace(' ', '_')}.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(result_json, f, ensure_ascii=False, indent=2)

        time.sleep(1)  # small delay between hits
if __name__ == "__main__":
    send_pricing_request()



