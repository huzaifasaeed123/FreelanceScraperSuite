"""
AXA Insurance Scraper - Simple Functional Style
Fetches quotations from AXA Morocco API
"""

import requests
from datetime import datetime, timedelta


# ==========================================
# AXA OPTIONS CONFIGURATION
# ==========================================

AXA_OPTIONS = {
    # Defense: 4 Options
    "defense": [
        {"label": "5 000 DH", "value": 1},
        {"label": "7 500 DH", "value": 2},
        {"label": "10 000 DH", "value": 3},
        {"label": "15 000 DH", "value": 4}
    ],

    # PFCP: Full Range 0 to 9
    "pfcp": [
        {"label": "F0 : 5000/ 5000/ 1000", "value": 1},
        {"label": "F1 : 10000/ 10000/ 3000", "value": 2},
        {"label": "F2 : 20000/ 20000/ 4000", "value": 3},
        {"label": "F3 : 30000/ 30000/ 5000", "value": 4},
        {"label": "F4 : 40000/ 40000/ 6000", "value": 5},
        {"label": "F5 : 50000/ 50000/ 8000", "value": 6},
        {"label": "F6 : 60000/ 60000/ 9000", "value": 7},
        {"label": "F7 : 70000/ 70000/ 10000", "value": 8},
        {"label": "F8 : 100000/100000/10000", "value": 9},
        {"label": "F9 : 120000/120000/12000", "value": 10}
    ],

    # Fixed Options
    "incendie": [{"label": "SANS", "value": 1}],
    "vol": [{"label": "5 %", "value": 1}],

    # Bris de Glaces: Expanded List
    "glass": [
        {"label": "5000 Min. 300 DH", "value": 1},
        {"label": "10000 Min. 300 DH", "value": 2},
        {"label": "15000 Min. 300 DH", "value": 3},
        {"label": "20000 Min. 300 DH", "value": 4},
        {"label": "25000 Min. 300 DH", "value": 5},
        {"label": "30000 Min. 300 DH", "value": 6},
        {"label": "40000 Min.300 DH", "value": 7},
        {"label": "50000 Min.300 DH", "value": 8},
        {"label": "60000 Min.300 DH", "value": 9},
        {"label": "75000 Min.300 DH", "value": 10},
        {"label": "100000 Min.300 DH", "value": 11}
    ],

    # Dommages Collision: 4 Options
    "collision": [
        {"label": "Dép. 5% Min 1 000 DH", "value": 2},
        {"label": "10 000 DH & 5% Min. 1 000 DH", "value": 7},
        {"label": "20 000 DH & 5% Min. 1 000 DH", "value": 9},
        {"label": "30 000 DH & 5% Min. 1 000 DH", "value": 10}
    ],

    # Dommages Tous Accidents: Expanded List
    "all_risk": [
        {"label": "3% & Min. 2500 DH", "value": 1},
        {"label": "5% & 2500 DH", "value": 2},
        {"label": "10% & 3500 DH", "value": 4},
        {"label": "10% & 2500 DH", "value": 5},
        {"label": "20% & 3500 DH", "value": 8},
        {"label": "20% & 2500 DH", "value": 9},
        {"label": "Cap. Réduit 3% & Min. 2500 DH", "value": 10},
        {"label": "Cap. Réduit 5% & Min. 2500 DH", "value": 11},
        {"label": "Cap. Réduit 10% & Min. 3500 DH", "value": 13},
        {"label": "Cap. Réduit 10% & Min. 2500 DH", "value": 14},
        {"label": "Cap. Réduit 20% & Min. 3500 DH", "value": 17},
        {"label": "Cap. Réduit 20% & Min. 2500 DH", "value": 18}
    ]
}

# Pack configuration: which guarantees appear in which pack
AXA_PACK_CONFIG = {
    # Basique (Pack 2)
    2: {
        "guarantees": [
            {"code": "1", "type": "fixed", "formule": 0, "title": "RESPONSABILITÉ CIVILE"},
            {"code": "150", "type": "fixed", "formule": 0, "title": "ÉVÈNEMENTS CATASTROPHIQUES"},
            {"code": "20", "type": "select", "options_key": "defense", "default": 1, "title": "Défense et Recours"},
            {"code": "500", "type": "select", "options_key": "pfcp", "default": 1, "title": "P.F.C.P"}
        ]
    },
    # Basique+ (Pack 3)
    3: {
        "guarantees": [
            {"code": "1", "type": "fixed", "formule": 0, "title": "RESPONSABILITÉ CIVILE"},
            {"code": "150", "type": "fixed", "formule": 0, "title": "ÉVÈNEMENTS CATASTROPHIQUES"},
            {"code": "20", "type": "fixed", "formule": 0, "title": "DÉFENSE ET RECOURS"},
            {"code": "3", "type": "select", "options_key": "incendie", "default": 1, "title": "Incendie"},
            {"code": "4", "type": "select", "options_key": "vol", "default": 1, "title": "Vol"},
            {"code": "500", "type": "select", "options_key": "pfcp", "default": 1, "title": "P.F.C.P"}
        ]
    },
    # Optimale (Pack 4) - All defaults set to first option value to match initial API prices
    4: {
        "guarantees": [
            {"code": "1", "type": "fixed", "formule": 0, "title": "RESPONSABILITÉ CIVILE"},
            {"code": "150", "type": "fixed", "formule": 0, "title": "ÉVÈNEMENTS CATASTROPHIQUES"},
            {"code": "3", "type": "select", "options_key": "incendie", "default": 1, "title": "Incendie"},
            {"code": "4", "type": "select", "options_key": "vol", "default": 1, "title": "Vol"},
            {"code": "5", "type": "select", "options_key": "glass", "default": 1, "title": "Bris de Glaces"},
            {"code": "20", "type": "select", "options_key": "defense", "default": 1, "title": "Défense et Recours"},
            {"code": "500", "type": "select", "options_key": "pfcp", "default": 1, "title": "P.F.C.P"},
            {"code": "35", "type": "select", "options_key": "collision", "default": 2, "title": "Dommages Collision"}
        ]
    },
    # Premium (Pack 5) - All defaults set to first option value to match initial API prices
    5: {
        "guarantees": [
            {"code": "1", "type": "fixed", "formule": 0, "title": "RESPONSABILITÉ CIVILE"},
            {"code": "150", "type": "fixed", "formule": 0, "title": "ÉVÈNEMENTS CATASTROPHIQUES"},
            {"code": "3", "type": "select", "options_key": "incendie", "default": 1, "title": "Incendie"},
            {"code": "4", "type": "select", "options_key": "vol", "default": 1, "title": "Vol"},
            {"code": "5", "type": "select", "options_key": "glass", "default": 1, "title": "Bris de Glaces"},
            {"code": "20", "type": "select", "options_key": "defense", "default": 1, "title": "Défense et Recours"},
            {"code": "500", "type": "select", "options_key": "pfcp", "default": 1, "title": "P.F.C.P"},
            {"code": "2", "type": "select", "options_key": "all_risk", "default": 1, "title": "Dommages Tous Accidents"}
        ]
    }
}


def get_axa_headers():
    """Return common headers for AXA API requests"""
    return {
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


def fetch_axa_quotation(payload):
    """
    Fetch insurance quotation from AXA API

    Args:
        payload: Dictionary containing contrat, vehicule, leadInfos data

    Returns:
        List of quotation offers or empty list on error
    """
    url = "https://axa.ma/bff/website/v1/quotation"

    try:
        response = requests.post(
            url,
            json=payload,
            headers=get_axa_headers(),
            timeout=30
        )
        response.raise_for_status()

        data = response.json()
        return data

    except Exception as e:
        print(f"AXA API Error: {str(e)} for payload: {payload}")
        return []


def update_axa_quotation(quotation_id, payload):
    """
    Update AXA quotation with selected options (PUT request)

    Args:
        quotation_id: The quotation ID to update
        payload: Full payload including contrat, vehicule, leadInfos, garanties, etc.

    Returns:
        Updated quotation data or None on error
    """
    url = f"https://axa.ma/bff/website/v1/quotation/{quotation_id}"

    try:
        response = requests.put(
            url,
            json=payload,
            headers=get_axa_headers(),
            timeout=30
        )
        response.raise_for_status()

        data = response.json()
        return data

    except Exception as e:
        print(f"AXA Update API Error: {str(e)} for quotation_id: {quotation_id}")
        return None


def build_garanties_payload(pack_id, user_selections=None):
    """
    Build garanties array for AXA API payload based on pack and user selections

    Args:
        pack_id: Pack ID (2=Basique, 3=Basique+, 4=Optimale, 5=Premium)
        user_selections: Dict mapping guarantee code to selected value (optional)

    Returns:
        List of garanties for the API payload
    """
    if user_selections is None:
        user_selections = {}

    config = AXA_PACK_CONFIG.get(pack_id)
    if not config:
        return []

    garanties = []
    for g in config["guarantees"]:
        code = g["code"]

        if g["type"] == "fixed":
            formule = g["formule"]
        else:
            # For select type, use user selection or default
            formule = user_selections.get(code, g["default"])

        garanties.append({
            "codeGarantie": code,
            "formule": formule,
            "typeVehcile": 1
        })

    return garanties


def get_pack_selectable_fields(pack_id):
    """
    Get selectable fields configuration for a pack to send to frontend

    Args:
        pack_id: Pack ID (2=Basique, 3=Basique+, 4=Optimale, 5=Premium)

    Returns:
        List of selectable field configurations for frontend
    """
    config = AXA_PACK_CONFIG.get(pack_id)
    if not config:
        return []

    selectable_fields = []
    for g in config["guarantees"]:
        if g["type"] == "select":
            options_key = g.get("options_key")
            options = AXA_OPTIONS.get(options_key, [])

            selectable_fields.append({
                "code": g["code"],
                "title": g["title"],
                "options": options,
                "default": g["default"]
            })

    return selectable_fields


def get_pack_fixed_guarantees(pack_id):
    """
    Get fixed guarantees for a pack to display on frontend

    Args:
        pack_id: Pack ID (2=Basique, 3=Basique+, 4=Optimale, 5=Premium)

    Returns:
        List of fixed guarantee configurations
    """
    config = AXA_PACK_CONFIG.get(pack_id)
    if not config:
        return []

    fixed_guarantees = []
    for g in config["guarantees"]:
        if g["type"] == "fixed":
            fixed_guarantees.append({
                "code": g["code"],
                "title": g["title"],
                "included": True
            })

    return fixed_guarantees


def scrape_axa(params):
    """
    Main function to scrape AXA for both Annual and Semi-Annual plans
    Returns quotations along with base_payload for subsequent update requests
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

    # Extract idQuotation and idLead from results (they should be same for all plans)
    id_quotation = None
    id_lead = None
    if annual_result and len(annual_result) > 0:
        id_quotation = annual_result[0].get("idQuotation")
        id_lead = annual_result[0].get("idLead")

    result = {
        "annual": annual_result,
        "semi_annual": semi_result,
        # Include base_payload for subsequent update requests
        "base_payload": base_payload,
        "id_quotation": id_quotation,
        "id_lead": id_lead
    }

    return result

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
