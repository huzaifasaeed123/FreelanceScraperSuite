"""
AXA Insurance Scraper - Simple Functional Style
Fetches quotations from AXA Morocco API
"""

import requests
from datetime import datetime, timedelta


def fetch_axa_quotation(payload):
    """
    Fetch insurance quotation from AXA API

    Args:
        payload: Dictionary containing contrat, vehicule, leadInfos data

    Returns:
        List of quotation offers or empty list on error
    """
    url = "https://axa.ma/bff/website/v1/quotation"

    headers = {
        "accept": "application/json, text/plain, */*",
        "accept-encoding": "gzip, deflate, br, zstd",
        "accept-language": "en-US,en;q=0.9",
        "connection": "keep-alive",
        "content-type": "application/json",
        "host": "axa.ma",
        "origin": "https://axa.ma",
        "referer": "https://axa.ma/website-transactional/affaire-nouvelle",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
    }

    try:
        response = requests.post(
            url,
            json=payload,
            headers=headers,
            timeout=30
        )
        response.raise_for_status()

        data = response.json()
        return data

    except Exception as e:
        print(f"AXA API Error: {str(e)}")
        return []


def scrape_axa(params):
    """
    Main function to scrape AXA for both Annual and Semi-Annual plans
    """
    from .field_mapper import FieldMapper
    import copy

    # Base payload
    base_payload = FieldMapper.map_for_scraper(params, "axa")

    # --- Annual ---
    annual_payload = copy.deepcopy(base_payload)
    annual_payload["contrat"]["modePaiement"] = "12"
    annual_result = fetch_axa_quotation(annual_payload)

    # --- Semi-Annual ---
    semi_payload = copy.deepcopy(base_payload)
    semi_payload["contrat"]["modePaiement"] = "06"
    semi_result = fetch_axa_quotation(semi_payload)


    return {
        "annual": annual_result,
        "semi_annual": semi_result
        }

# # ===== FOR LOCAL TESTING =====
# if __name__ == "__main__":
#     # Hardcoded payload for testing
#     future_date = (datetime.now() + timedelta(days=1)).strftime("%d-%m-%Y")

#     test_payload = {
#         "contrat": {
#             "codeIntermediaire": 474,
#             "codeProduit": 115,
#             "nombreFraction": 0,
#             "typeFractionnement": "f",
#             "typeAvenant": 1,
#             "sousAvenant": 1,
#             "dateEffet": future_date,
#             "typeContrat": "DF",
#             "modePaiement": "12",
#             "dateEcheance": "0",
#             "dateExpiration": "0",
#             "typePersonne": "P",
#             "assureEstConducteur": "O",
#             "identifiant": "a0",
#             "dateNaissanceConducteur": "10-01-2001",
#             "isFonctionnaire": "N",
#             "codeConvention": 0,
#             "newClient": "O",
#             "nom": "Saeed",
#             "prenom": "Muhammad",
#             "dateNaissanceAssure": "10-01-2001",
#             "tauxReduction": 0
#         },
#         "vehicule": {
#             "codeUsage": "1B",
#             "dateMisCirculation": "06-01-2026",
#             "matricule": "123",
#             "valeurNeuf": 65000,
#             "valeurVenale": 49999,
#             "valeurAmenagement": 0,
#             "energie": "G",
#             "puissanceFiscale": 12,
#             "codeCarrosserie": "B1",
#             "codeMarque": 16,
#             "nombrePlace": 5,
#             "dateMutation": "0"
#         },
#         "leadInfos": {
#             "city": "CASABLANCA",
#             "phoneNumber": "0661776677",
#             "licenceDate": "20-01-2017",
#             "brandName": "BMW",
#             "intermediateName": "A.S ASSURANCES",
#             "marketingConsent": True,
#             "cguConsent": True
#         }
#     }

#     # Test the scraper
#     print("Testing AXA Scraper...")
#     result = fetch_axa_quotation(test_payload)

#     if result:
#         print(f"Success! Got {len(result)} quotations")
#         import json
#         print(json.dumps(result, indent=2))
#     else:
#         print("Failed to fetch quotations")
