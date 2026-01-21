import requests
import json
from pathlib import Path



# database.py 
# ---------------------------------------------------
# STEP 1: CREATE SUBSCRIPTION
# ---------------------------------------------------
def create_subscription():
    url = "https://bo-sel.mamda-mcma.ma/api/subscriptions"

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0"
    }

    # 🔹 Hardcoded but editable payload
    # payload = {
    #     "dateOfCirculation": "2023-02-15",
    #     "horsePower": 6,
    #     "fuel": "Diesel",
    #     "valueOfVehicle": 30000,
    #     "valueOfNewVehicle": 80000,
    #     "agreeToTerms": True
    # }
    payload = {
        "dateOfCirculation": "2023-01-01",
        "horsePower": 6,
        "fuel": "Essence",
        "valueOfVehicle": 300000,
        "valueOfNewVehicle": 400000,
        "agreeToTerms": True
    }

    response = requests.post(url, headers=headers, json=payload, timeout=30)
    print(response.text)
    response.raise_for_status()

    data = response.json()

    print("\n✅ STEP 1 RESPONSE:")
    print(json.dumps(data, indent=4))

    subscription_id = data["subscription"]["id"]
    token = data["token"]

    return subscription_id, token


# ---------------------------------------------------
# STEP 2: FETCH PACKS USING ID + TOKEN
# ---------------------------------------------------
def get_subscription_packs(subscription_id, token):
    url = f"https://bo-sel.mamda-mcma.ma/api/subscriptions/{subscription_id}/packs"

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0",
        "Origin": "https://souscription-en-ligne.mamda-mcma.ma",
        "Referer": "https://souscription-en-ligne.mamda-mcma.ma/",
        "Connection": "keep-alive"
    }

    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()

    data = response.json()

    # Save response
    file_path = f"mcma_subscription_{subscription_id}.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

    print("\n✅ STEP 2 RESPONSE:")
    print(json.dumps(data, indent=4))

    return data


# ---------------------------------------------------
# MAIN EXECUTION
# ---------------------------------------------------
if __name__ == "__main__":
    sub_id, auth_token = create_subscription()
    get_subscription_packs(sub_id, auth_token)
