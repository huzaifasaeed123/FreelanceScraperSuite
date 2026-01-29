"""
MCMA Insurance Scraper - Simple Functional Style
Fetches quotations from MAMDA-MCMA API
"""

import requests


def create_mcma_subscription(payload):
    """
    Create subscription and get auth token

    Args:
        payload: Dictionary with dateOfCirculation, horsePower, fuel, valueOfVehicle, etc.

    Returns:
        Tuple of (subscription_id, token) or (None, None) on error
    """
    url = "https://bo-sel.mamda-mcma.ma/api/subscriptions"

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0"
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()

        data = response.json()
        subscription_id = data["subscription"]["id"]
        token = data["token"]

        print(subscription_id, token)
        return subscription_id, token

    except Exception as e:
        print(f"MCMA Subscription Error: {str(e)}")
        return None, None


def get_mcma_packs(subscription_id, token):
    """
    Fetch available packs using subscription ID and token

    Args:
        subscription_id: Subscription ID from create_mcma_subscription
        token: Auth token from create_mcma_subscription

    Returns:
        Packs data dictionary or None on error
    """
    url = f"https://bo-sel.mamda-mcma.ma/api/subscriptions/{subscription_id}/packs"

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0",
        "Origin": "https://souscription-en-ligne.mamda-mcma.ma",
        "Referer": "https://souscription-en-ligne.mamda-mcma.ma/",
        "Connection": "keep-alive"
    }

    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()

        data = response.json()
        # print(data)
        return data

    except Exception as e:
        print(f"MCMA Packs Error: {str(e)}")
        return None


def get_mcma_pack_with_options(subscription_id, token, pack_name, broken_glass_value, second_option_value):
    """
    Fetch pack details with specific option values

    Args:
        subscription_id: Subscription ID from create_mcma_subscription
        token: Auth token from create_mcma_subscription
        pack_name: 'optimale' or 'tout_risque'
        broken_glass_value: Value for brokenGlassValue (7000, 10000, 15000)
        second_option_value: For optimale: damageAndCollision (20000, 30000, 50000)
                            For tout_risque: franchise (3, 5, 10)

    Returns:
        Pack details with pricing or None on error
    """
    # Build URL based on pack type
    if pack_name == "optimale":
        url = f"https://bo-sel.mamda-mcma.ma/api/subscriptions/{subscription_id}/packs/optimale?brokenGlassValue={broken_glass_value}&damageAndCollision={second_option_value}&franchise=5"
    elif pack_name == "tout_risque":
        url = f"https://bo-sel.mamda-mcma.ma/api/subscriptions/{subscription_id}/packs/tout_risque?brokenGlassValue={broken_glass_value}&damageAndCollision=20000&franchise={second_option_value}"
    else:
        return None

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0",
        "Origin": "https://souscription-en-ligne.mamda-mcma.ma",
        "Referer": "https://souscription-en-ligne.mamda-mcma.ma/",
        "Connection": "keep-alive"
    }

    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"MCMA Pack Options Error ({pack_name}): {str(e)}")
        return None


def update_mcma_quote(subscription_id, token, pack_name, broken_glass_value, second_option_value):
    """
    Update MCMA quote with specific option values.
    Called when user selects different options in the frontend.

    Args:
        subscription_id: Subscription ID from initial scrape
        token: Auth token from initial scrape
        pack_name: 'optimale' or 'tout_risque'
        broken_glass_value: Value for brokenGlassValue (7000, 10000, 15000)
        second_option_value: For optimale: damageAndCollision (20000, 30000, 50000)
                            For tout_risque: franchise (3, 5, 10)

    Returns:
        Dictionary with updated pricing or error
    """
    pack_data = get_mcma_pack_with_options(subscription_id, token, pack_name, broken_glass_value, second_option_value)

    if pack_data:
        return {
            "success": True,
            "pack_name": pack_name,
            "broken_glass_value": broken_glass_value,
            "second_option_value": second_option_value,
            "annual_price": pack_data.get("annualBasePrice"),
            "semi_annual_price": pack_data.get("semiAnnualBasePrice"),
            "raw_data": pack_data
        }
    else:
        return {
            "success": False,
            "error": f"Failed to fetch {pack_name} options"
        }


def get_mcma_all_pack_options(subscription_id, token):
    """
    Fetch all option combinations for optimale and tout_risque packs

    Args:
        subscription_id: Subscription ID from create_mcma_subscription
        token: Auth token from create_mcma_subscription

    Returns:
        Dictionary with all option combinations and their prices
    """
    # Option values
    broken_glass_options = [7000, 10000, 15000]
    damage_collision_options = [20000, 30000, 50000]  # For optimale
    franchise_options = [3, 5, 10]  # For tout_risque

    result = {
        "optimale_options": [],
        "tout_risque_options": []
    }

    # Fetch all optimale combinations (broken_glass x damage_collision = 9 combinations)
    print("Fetching optimale pack options...")
    for bg in broken_glass_options:
        for dc in damage_collision_options:
            pack_data = get_mcma_pack_with_options(subscription_id, token, "optimale", bg, dc)
            if pack_data:
                result["optimale_options"].append({
                    "brokenGlassValue": bg,
                    "damageAndCollision": dc,
                    "annualPrice": pack_data.get("annualBasePrice"),
                    "semiAnnualPrice": pack_data.get("semiAnnualBasePrice")
                })

    # Fetch all tout_risque combinations (broken_glass x franchise = 9 combinations)
    print("Fetching tout_risque pack options...")
    for bg in broken_glass_options:
        for fr in franchise_options:
            pack_data = get_mcma_pack_with_options(subscription_id, token, "tout_risque", bg, fr)
            if pack_data:
                result["tout_risque_options"].append({
                    "brokenGlassValue": bg,
                    "franchise": fr,
                    "annualPrice": pack_data.get("annualBasePrice"),
                    "semiAnnualPrice": pack_data.get("semiAnnualBasePrice")
                })

    return result


def scrape_mcma(params):
    """
    Main function to scrape MCMA - Can be called from website
    Returns only base packs (no option variations) along with session data
    for subsequent update requests.

    Args:
        params: Dictionary with keys like valeur_neuf, valeur_venale, etc.

    Returns:
        Dictionary with base packs and session data (subscription_id, token)
    """
    # Import FieldMapper to use mapped payload
    from .field_mapper import FieldMapper

    # Get mapped payload for MCMA
    payload = FieldMapper.map_for_scraper(params, "mcma")

    # Step 1: Create subscription
    subscription_id, token = create_mcma_subscription(payload)

    if not subscription_id or not token:
        return None

    # Step 2: Get base packs only (no option fetching)
    base_packs = get_mcma_packs(subscription_id, token)

    if not base_packs:
        return None

    # Return packs with session data for subsequent update requests
    return {
        "packs": base_packs,
        "subscription_id": subscription_id,
        "token": token
    }


def scrape_mcma_with_options(params):
    """
    Scrape MCMA with all pack option combinations

    Args:
        params: Dictionary with keys like valeur_neuf, valeur_venale, etc.

    Returns:
        Dictionary with base packs and all option combinations for optimale/tout_risque
    """
    # Import FieldMapper to use mapped payload
    from .field_mapper import FieldMapper

    # Get mapped payload for MCMA
    payload = FieldMapper.map_for_scraper(params, "mcma")

    # Step 1: Create subscription
    subscription_id, token = create_mcma_subscription(payload)

    if not subscription_id or not token:
        return None

    # Step 2: Get base packs
    base_packs = get_mcma_packs(subscription_id, token)

    if not base_packs:
        return None

    # Step 3: Get all option combinations for optimale and tout_risque
    pack_options = get_mcma_all_pack_options(subscription_id, token)

    # Step 4: Combine results - embed options in the respective packs
    if "optimale" in base_packs and pack_options.get("optimale_options"):
        base_packs["optimale"]["option_prices"] = pack_options["optimale_options"]

    if "tout_risque" in base_packs and pack_options.get("tout_risque_options"):
        base_packs["tout_risque"]["option_prices"] = pack_options["tout_risque_options"]

    # with open("mcma_full_options.json", "w", encoding="utf-8") as f:
    #     import json
    #     json.dump(base_packs, f, indent=4, ensure_ascii=False)
    return base_packs


# ===== FOR LOCAL TESTING =====
# if __name__ == "__main__":
#     # Hardcoded payload for testing
#     test_payload = {
#         "dateOfCirculation": "2023-02-15",
#         "horsePower": 6,
#         "fuel": "Diesel",
#         "valueOfVehicle": 30000,
#         "valueOfNewVehicle": 80000,
#         "agreeToTerms": True
#     }

#     # Test the scraper
#     print("Testing MCMA Scraper...")
#     print("Step 1: Creating subscription...")
#     sub_id, auth_token = create_mcma_subscription(test_payload)

#     if sub_id and auth_token:
#         print(f"Success! Subscription ID: {sub_id}")
#         print("Step 2: Fetching packs...")
#         packs = get_mcma_packs(sub_id, auth_token)

#         if packs:
#             print("Success! Got packs")
#             import json
#             print(json.dumps(packs, indent=2))
#         else:
#             print("Failed to fetch packs")
#     else:
#         print("Failed to create subscription")
