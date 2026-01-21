"""
Sanlam Insurance Scraper - Simple Functional Style
Fetches quotations from Sanlam Morocco API
Supports both 6-month and 12-month pricing
"""

import requests
import time
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta


def calculate_end_date(start_date, duration_months):
    """Calculate end date exactly N months minus 1 day"""
    end_date = start_date + relativedelta(months=duration_months) - timedelta(days=1)
    return end_date.strftime("%Y-%m-%d")


def fetch_sanlam_pricing(payload, duration_months=12):
    """
    Fetch pricing from Sanlam API

    Args:
        payload: Dictionary with driver, subscriber, vehicle, policy, agent data
        duration_months: 6 or 12 for semi-annual or annual

    Returns:
        Pricing data or None on error
    """
    url = "https://souscription-en-ligne.sanlam.ma/api/auto/recalculate-pricing"

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0"
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=60)
        response.raise_for_status()

        data = response.json()

        if data.get("status") != 200:
            print(f"Sanlam API returned status: {data.get('status')} for {duration_months}m")
            return None

        return data.get("data", {})

    except Exception as e:
        print(f"Sanlam Pricing Error ({duration_months}m): {str(e)}")
        return None


def fetch_formula_pricing(formula, policy_id, agent_key):
    """
    Fetch detailed pricing for a specific formula

    Args:
        formula: Formula object from initial pricing response
        policy_id: Policy ID from initial pricing response
        agent_key: Agent key

    Returns:
        Formula pricing data or None on error
    """
    url = "https://souscription-en-ligne.sanlam.ma/api/auto/formula-pricing"

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0"
    }

    formula_payload = {
        "formula": formula,
        "agent": {"agentkey": agent_key},
        "id": policy_id
    }

    try:
        response = requests.post(url, json=formula_payload, headers=headers, timeout=60)
        response.raise_for_status()

        result = response.json()

        if result.get("status") == 200:
            return result.get("data", {}).get("pricing", {})
        else:
            print(f"Formula {formula.get('name')} returned status: {result.get('status')}")
            return None

    except Exception as e:
        print(f"Error fetching formula {formula.get('name', 'unknown')}: {e}")
        return None


def fetch_all_formulas(payload, duration_months=12):
    """
    Fetch pricing and all formula details

    Args:
        payload: Complete request payload
        duration_months: 6 or 12

    Returns:
        List of formula pricing details
    """
    # Get initial pricing with formulas list
    pricing_data = fetch_sanlam_pricing(payload, duration_months)

    if not pricing_data:
        return []

    formulas = pricing_data.get("formulas", [])
    policy_id = pricing_data.get("savedPolicy", {}).get("id")
    agent_key = payload.get("agent", {}).get("agentkey", "68103")

    if not policy_id or not formulas:
        print(f"No policy ID or formulas returned for {duration_months}m")
        return []

    # Fetch detailed pricing for each formula
    formula_details = []

    for formula in formulas:
        detail = fetch_formula_pricing(formula, policy_id, agent_key)
        if detail:
            formula_details.append(detail)
        time.sleep(1)  # Small delay between requests

    return formula_details


def scrape_sanlam(params):
    """
    Main function to scrape Sanlam - Can be called from website

    Args:
        params: Dictionary with keys like valeur_neuf, valeur_venale, etc.

    Returns:
        Dictionary with 'annual' and 'semi_annual' formula data
    """
    # Import FieldMapper to use mapped payload
    from .field_mapper import FieldMapper

    # Get mapped payload for Sanlam
    base_payload = FieldMapper.map_for_scraper(params, "sanlam")

    # Calculate dates for 12-month
    start_date = datetime.now() #+ timedelta(days=1)
    start_date_str = start_date.strftime("%Y-%m-%d")
    end_date_12m = calculate_end_date(start_date, 12)
    end_date_6m = calculate_end_date(start_date, 6)

    # Fetch 12-month pricing
    payload_12m = base_payload.copy()
    
    payload_12m["policy"] = {
        "startDate":  start_date_str,
        "endDate": end_date_12m,
        "maturityContractType": "2",
        "duration": 12
    }
    print(payload_12m)
    annual_formulas = fetch_all_formulas(payload_12m, 12)

    # Fetch 6-month pricing
    payload_6m = base_payload.copy()
    payload_6m["policy"] = {
        "startDate": start_date_str,
        "endDate": end_date_6m,
        "duration": 6,
        "maturityContractType": "2"
    }
    semi_annual_formulas = fetch_all_formulas(payload_6m, 6)

    return {
        "annual": annual_formulas,
        "semi_annual": semi_annual_formulas
    }


# ===== FOR LOCAL TESTING =====
if __name__ == "__main__":
    # Hardcoded payload for testing
    start_date = datetime.now() + timedelta(days=1)
    start_date_str = start_date.strftime("%Y-%m-%d")
    end_date_str = calculate_end_date(start_date, 12)

    test_payload = {
        "driver": {
            "licenseNumber": "1111111111",
            "licenseDate": "2026-01-13",
            "licenseCategory": "B",
            "lastName": "Client",
            "firstName": "Test",
            "birthDate": "2005-02-08",
            "CIN": "BJ1111111",
            "sex": "M",
            "nature": "1",
            "adress": "sample addresse",
            "city": "AIN AICHA",
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
            "lastName": "Client",
            "firstName": "Test",
            "birthDate": "2005-02-08",
            "adress": "sample addresse",
            "city": "AIN AICHA",
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
            "brand": "2078",
            "horsePower": "6",
            "model": "Autres",
            "usageCode": "1",
            "registrationFormat": "3",
            "newValue": 650000,
            "combustion": "L",
            "circulationDate": "2026-01-05",
            "marketValue": 650000,
            "seatsNumber": 5
        },
        "policy": {
            "startDate": start_date_str,
            "endDate": end_date_str,
            "maturityContractType": "2",
            "duration": 12
        },
        "agent": {
            "agentkey": "68103"
        },
        "recaptcha": ""
    }

    # Test the scraper
    print("Testing Sanlam Scraper...")
    print("Fetching 12-month pricing...")
    formulas_12m = fetch_all_formulas(test_payload, 12)

    if formulas_12m:
        print(f"Success! Got {len(formulas_12m)} formulas for 12 months")
        import json
        print(json.dumps(formulas_12m, indent=2))
    else:
        print("Failed to fetch formulas")
