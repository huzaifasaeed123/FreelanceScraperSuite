import requests
import json
from datetime import datetime, timedelta


AXA_QUOTATION_URL = "https://axa.ma/bff/website/v1/quotation"


def fetch_axa_quotation():
    """
    Test function for AXA quotation API.
    Payload is hardcoded for now and can be replaced later with dynamic data.
    """

    # =========================
    # HARD-CODED PAYLOAD
    # =========================
    future_date = (datetime.now() + timedelta(days=1)).strftime("%d-%m-%Y")

    payload = {
        "contrat": {
            "codeIntermediaire": 474,
            "codeProduit": 115,
            "nombreFraction": 0,
            "typeFractionnement": "f",
            "typeAvenant": 1,
            "sousAvenant": 1,
            "dateEffet":  future_date,     #"08-01-2026",
            "typeContrat": "DF",
            "modePaiement": "12",
            "dateEcheance": "0",
            "dateExpiration": "0",
            "typePersonne": "P",
            "assureEstConducteur": "O",
            "identifiant": "a0",
            "dateNaissanceConducteur": "10-01-2001",
            "isFonctionnaire": "N",
            "codeConvention": 0,
            "newClient": "O",
            "nom": "Saeed",
            "prenom": "Muhammad",
            "dateNaissanceAssure": "10-01-2001",
            "tauxReduction": 0
        },
        "vehicule": {
            "codeUsage": "1B",
            "dateMisCirculation": "06-01-2026",
            "matricule": "123",
            "valeurNeuf": 65000,
            "valeurVenale": 49999,
            "valeurAmenagement": 0,
            "energie": "G",
            "puissanceFiscale": 12,
            "codeCarrosserie": "B1",
            "codeMarque": 16,
            "nombrePlace": 5,
            "dateMutation": "0"
        },
        "leadInfos": {
            "city": "CASABLANCA",
            "phoneNumber": "0661776677",
            "licenceDate": "20-01-2017",
            "brandName": "BMW",
            "intermediateName": "A.S ASSURANCES",
            "marketingConsent": True,
            "cguConsent": True
        }
    }

    # =========================
    # HEADERS
    # =========================
    headers = {
    "accept": "application/json, text/plain, */*",
    "accept-encoding": "gzip, deflate, br, zstd",
    "accept-language": "en-US,en;q=0.9",
    "connection": "keep-alive",
    "content-length": "931",
    "content-type": "application/json",
    "cookie": "CookieConsent=true; _ga=GA1.2.1989900129.1767825639; 12a0a4ca139f5b8bf143a61b393e5ee7=07dfa710261e4d351daa82043df25f29; TS01c59fe7=010f812848c47e74bf79cb705d43ca210562eac0a60cb2a0e37f1c7b5c4d30fe29ce3691dafb928d7e9b0a0e70cede42639bdc34ae; TS093f03aa027=080a269941ab2000a53db605f46ff4b315c6e5e89d5739ef1296d9d0747624ae8237f6c9fc4562bc0803da6134113000e6980f4654067122181a3263c1c8187d7bfb33427a1080eb58e7bff06f8c54d9ae572964b00079b6b332993a956d1be1",
    "host": "axa.ma",
    "origin": "https://axa.ma",
    "referer": "https://axa.ma/website-transactional/affaire-nouvelle",
    "sec-ch-ua": "\"Google Chrome\";v=\"143\", \"Chromium\";v=\"143\", \"Not A(Brand\";v=\"24\"",
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": "\"Windows\"",
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
}


    # =========================
    # API REQUEST
    # =========================
    response = requests.post(
        AXA_QUOTATION_URL,
        json=payload,
        headers=headers,
        timeout=30
    )
    print(response.text)
    response.raise_for_status()  # raises exception if request failed

    data = response.json()

    # =========================
    # SAVE RESPONSE LOCALLY
    # =========================
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_name = f"axa_quotation_response_{timestamp}.json"

    with open(file_name, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

    # =========================
    # PRINT RESPONSE
    # =========================
    print("AXA API Response:")
    print(json.dumps(data, indent=4, ensure_ascii=False))

    return data


if __name__ == "__main__":
    fetch_axa_quotation()
