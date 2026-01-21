"""
Insurance Comparison Service - Simplified
Aggregates results from all insurance scrapers
"""

import concurrent.futures
from typing import Dict, Any, List, Optional
import time
import json

from scrapers import SCRAPER_FUNCTIONS
from database.models import DatabaseManager


# Provider metadata
PROVIDER_INFO = {
    'axa': {
        'name': 'AXA Assurance',
        'color': '#00008F',
        'logo': 'https://upload.wikimedia.org/wikipedia/commons/thumb/9/90/Logo_of_AXA.svg/1280px-Logo_of_AXA.svg.png'
    },
    'sanlam': {
        'name': 'Sanlam Assurance',
        'color': '#0066B3',
        'logo': 'https://www.sanlam.ma/themes/custom/flavor/logo.svg'
    },
    'rma': {
        'name': 'RMA Assurance',
        'color': '#1E3A8A',
        'logo': 'https://direct.rmaassurance.com/assets/images/logo-rma.svg'
    },
    'mcma': {
        'name': 'MAMDA-MCMA',
        'color': '#2fd0a7',
        'logo': 'https://www.mamda-mcma.ma/themes/custom/mamda/logo.svg'
    }
}


def parse_sanlam_response(data):
    """Parse Sanlam API response to frontend format"""
    # Handle scraper returning {'annual': [...], 'semi_annual': [...]}
    if isinstance(data, dict) and 'annual' in data:
        annual_data = data.get('annual', [])
        semi_annual_data = data.get('semi_annual', [])
        
        if not annual_data or not isinstance(annual_data, list):
            return []
        
        colors = ['#0066B3', '#003366', '#004d99']  # Sanlam blues
        plans = []
        
        for idx, formula in enumerate(annual_data):
            if not formula:
                continue

            # Get semi-annual formula for the same plan index
            semi_formula = semi_annual_data[idx] if idx < len(semi_annual_data) else formula

            plan = {
                "plan_name": formula.get("name", f"Formule {idx + 1}"),
                "plan_code": f"sanlam_{idx}",
                "provider": "Sanlam Assurance",
                "provider_code": "sanlam",
                "color": colors[idx % len(colors)],
                "annual": {
                    "prime_net": formula.get("primeHT", 0),
                    "taxes": formula.get("priceTTC", 0) - formula.get("primeHT", 0),
                    "prime_total": formula.get("priceTTC", 0)
                },
                "semi_annual": {
                    "prime_net": semi_formula.get("primeHT", 0),
                    "taxes": semi_formula.get("priceTTC", 0) - semi_formula.get("primeHT", 0),
                    "prime_total": semi_formula.get("priceTTC", 0)
                },
                "guarantees": [
                    {
                        "name": cov.get("coverageName", ""),
                        "included": cov.get("checked", False)
                    } for cov in formula.get("coverages", [])
                ],
                "is_eligible": True,
                "order": idx
            }
            plans.append(plan)

        return plans
    elif not data or not isinstance(data, list):
        return []

    # Fallback for old format (list only)
    colors = ['#0066B3', '#003366', '#004d99']  # Sanlam blues
    plans = []
    for idx, formula in enumerate(data):
        if not formula:
            continue

        plan = {
            "plan_name": formula.get("name", f"Formule {idx + 1}"),
            "plan_code": f"sanlam_{idx}",
            "provider": "Sanlam Assurance",
            "provider_code": "sanlam",
            "color": colors[idx % len(colors)],
            "annual": {
                "prime_net": formula.get("primeHT", 0),
                "taxes": formula.get("priceTTC", 0) - formula.get("primeHT", 0),
                "prime_total": formula.get("priceTTC", 0)
            },
            "semi_annual": {
                "prime_net": round(formula.get("primeHT", 0) * 0.52, 2),
                "taxes": round((formula.get("priceTTC", 0) - formula.get("primeHT", 0)) * 0.52, 2),
                "prime_total": round(formula.get("priceTTC", 0) * 0.52, 2)
            },
            "guarantees": [
                {
                    "name": cov.get("coverageName", ""),
                    "included": cov.get("checked", False)
                } for cov in formula.get("coverages", [])
            ],
            "is_eligible": True,
            "order": idx
        }
        plans.append(plan)

    return plans


def parse_mcma_response(data):
    """Parse MCMA API response to frontend format"""
    if not data or not isinstance(data, dict):
        return []

    plans = []
    pack_order = ["essentielle", "confort", "optimale", "tout_risque"]
    colors = ['#2fd0a7', '#1ba88e', '#0d8f75', '#00765c']  # MCMA teals/greens

    for idx, pack_key in enumerate(pack_order):
        if pack_key not in data:
            continue

        pack = data[pack_key]
        if pack.get("disabled", False):
            continue

        annual_price = pack.get("annualBasePrice", 0)
        semi_annual_price = pack.get("semiAnnualBasePrice", 0)
        annual_taxes = round(annual_price * 0.165, 2)
        semi_annual_taxes = round(semi_annual_price * 0.165, 2)

        # Build selectable fields from option_prices if available
        selectable_fields = []
        option_prices = pack.get("option_prices", [])
        
        if option_prices and pack_key == "optimale":
            # For optimale: extract brokenGlassValue and damageAndCollision
            broken_glass_options = {}
            damage_collision_options = {}
            
            # Get unique values and their prices for broken glass
            for opt in option_prices:
                bg = opt.get("brokenGlassValue")
                if bg and bg not in broken_glass_options:
                    # Store with default damageAndCollision value
                    broken_glass_options[bg] = {
                        "value": bg,
                        "price": None  # Will be filled from any combination
                    }
            
            # Get unique values and their prices for damage and collision
            for opt in option_prices:
                dc = opt.get("damageAndCollision")
                if dc and dc not in damage_collision_options:
                    damage_collision_options[dc] = {
                        "value": dc,
                        "price": None  # Will be filled from any combination
                    }
            
            # Fill in any prices (from first found combination)
            for opt in option_prices:
                bg = opt.get("brokenGlassValue")
                dc = opt.get("damageAndCollision")
                if bg in broken_glass_options and broken_glass_options[bg]["price"] is None:
                    broken_glass_options[bg]["price"] = opt.get("annualPrice", 0)
                if dc in damage_collision_options and damage_collision_options[dc]["price"] is None:
                    damage_collision_options[dc]["price"] = opt.get("annualPrice", 0)
            
            if broken_glass_options:
                selectable_fields.append({
                    "title": "Bris de Glaces",
                    "options": list(broken_glass_options.values()),
                    "is_default": 7000
                })
            
            if damage_collision_options:
                selectable_fields.append({
                    "title": "Dommages-Collision",
                    "options": list(damage_collision_options.values()),
                    "is_default": 20000
                })
        
        elif option_prices and pack_key == "tout_risque":
            # For tout_risque: extract brokenGlassValue and franchise
            broken_glass_options = {}
            franchise_options = {}
            
            # Get unique values
            for opt in option_prices:
                bg = opt.get("brokenGlassValue")
                if bg and bg not in broken_glass_options:
                    broken_glass_options[bg] = {
                        "value": bg,
                        "price": None
                    }
            
            for opt in option_prices:
                fr = opt.get("franchise")
                if fr and fr not in franchise_options:
                    franchise_options[fr] = {
                        "value": fr,
                        "price": None
                    }
            
            # Fill in any prices
            for opt in option_prices:
                bg = opt.get("brokenGlassValue")
                fr = opt.get("franchise")
                if bg in broken_glass_options and broken_glass_options[bg]["price"] is None:
                    broken_glass_options[bg]["price"] = opt.get("annualPrice", 0)
                if fr in franchise_options and franchise_options[fr]["price"] is None:
                    franchise_options[fr]["price"] = opt.get("annualPrice", 0)
            
            if broken_glass_options:
                selectable_fields.append({
                    "title": "Bris de Glaces",
                    "options": list(broken_glass_options.values()),
                    "is_default": 7000
                })
            
            if franchise_options:
                selectable_fields.append({
                    "title": "Franchise",
                    "options": list(franchise_options.values()),
                    "is_default": 5
                })

        plan = {
            "plan_name": pack.get("title", pack_key.title()),
            "plan_code": pack.get("key", pack_key),
            "provider": "MAMDA-MCMA",
            "provider_code": "mcma",
            "color": colors[idx % len(colors)],
            "annual": {
                "prime_net": annual_price,
                "taxes": annual_taxes,
                "prime_total": round(annual_price + annual_taxes, 2)
            },
            "semi_annual": {
                "prime_net": semi_annual_price,
                "taxes": semi_annual_taxes,
                "prime_total": round(semi_annual_price + semi_annual_taxes, 2)
            },
            "guarantees": [
                {
                    "name": priv.get("title", ""),
                    "included": True
                } for priv in pack.get("privileges", [])
            ],
            "selectable_fields": selectable_fields,
            "is_eligible": not pack.get("disabled", False),
            "order": idx,
            "extra_info": {
                "option_combinations": option_prices  # Pass all combinations for frontend lookup
            }
        }
        plans.append(plan)

    return plans


def parse_rma_response(data):
    """Parse RMA API response to frontend format"""
    if not data or not isinstance(data, list):
        return []

    plans = []
    for idx, offer in enumerate(data):
        if not offer:
            continue

        prime_net = offer.get("primeAnnuelleHT", 0) or 0
        taxes = (offer.get("taxes", 0) or 0) + (offer.get("taxeParafiscal", 0) or 0)
        prime_total = offer.get("primeAnnuelleTTC", 0) or 0

        plan = {
            "plan_name": offer.get("libelle", f"Plan {idx + 1}"),
            "plan_code": str(offer.get("id", idx)),
            "provider": "RMA Assurance",
            "provider_code": "rma",
            "annual": {
                "prime_net": prime_net,
                "taxes": taxes,
                "prime_total": prime_total
            },
            "semi_annual": {
                "prime_net": round(prime_net * 0.52, 2),
                "taxes": round(taxes * 0.52, 2),
                "prime_total": round(prime_total * 0.52, 2)
            },
            "guarantees": [
                {
                    "name": g.get("libelle", ""),
                    "included": g.get("included", False)
                } for g in offer.get("garanties", []) if g.get("included", False)
            ],
            "is_eligible": offer.get("eligible", True),
            "order": idx
        }
        plans.append(plan)

    return plans


def parse_axa_response(data):
    """Parse AXA API response to frontend format"""
    # Handle scraper returning {'annual': [...], 'semi_annual': [...]}
    if isinstance(data, dict) and 'annual' in data:
        annual_data = data.get('annual', [])
        semi_annual_data = data.get('semi_annual', [])
        
        if not annual_data or not isinstance(annual_data, list):
            return []
        
        plan_names = ["Basique", "Basique+", "Optimale", "Premium"]
        colors = ['#1a472a', '#00008F', '#003d7a', '#0066FF']  # AXA blues
        plans = []

        for idx, quote in enumerate(annual_data):
            if not quote:
                continue

            # Get semi-annual quote for the same plan index
            semi_quote = semi_annual_data[idx] if idx < len(semi_annual_data) else quote

            plan = {
                "plan_name": plan_names[idx] if idx < len(plan_names) else f"Plan {idx + 1}",
                "plan_code": f"axa_{idx}",
                "provider": "AXA Assurance",
                "provider_code": "axa",
                "color": colors[idx % len(colors)],
                "annual": {
                    "prime_net": quote.get("primeNetComptant", 0),
                    "taxes": quote.get("taxesComptant", 0),
                    "prime_total": quote.get("primeTotaleComptant", 0)
                },
                "semi_annual": {
                    "prime_net": semi_quote.get("primeNetComptant", 0),
                    "taxes": semi_quote.get("taxesComptant", 0),
                    "prime_total": semi_quote.get("primeTotaleComptant", 0)
                },
                "guarantees": [],
                "is_eligible": True,
                "order": idx
            }
            plans.append(plan)

        return plans
    elif not data or not isinstance(data, list):
        return []

    # Fallback for old format
    plan_names = ["Basique", "Basique+", "Optimale", "Premium"]
    colors = ['#1a472a', '#00008F', '#003d7a', '#0066FF']
    plans = []

    for idx, quote in enumerate(data):
        if not quote:
            continue

        plan = {
            "plan_name": plan_names[idx] if idx < len(plan_names) else f"Plan {idx + 1}",
            "plan_code": f"axa_{idx}",
            "provider": "AXA Assurance",
            "provider_code": "axa",
            "color": colors[idx % len(colors)],
            "annual": {
                "prime_net": quote.get("primeNetComptant", 0),
                "taxes": quote.get("taxesComptant", 0),
                "prime_total": quote.get("primeTotaleComptant", 0)
            },
            "semi_annual": {
                "prime_net": quote.get("primeNetComptant", 0) * 0.52,
                "taxes": quote.get("taxesComptant", 0) * 0.52,
                "prime_total": quote.get("primeTotaleComptant", 0) * 0.52
            },
            "guarantees": [],
            "is_eligible": True,
            "order": idx
        }
        plans.append(plan)

    return plans


def fetch_from_provider(provider_code, params, user_id=None, form_submission_id=None):
    """
    Fetch quotes from a single provider

    Args:
        provider_code: Provider code (axa, sanlam, rma, mcma)
        params: Request parameters
        user_id: Optional user ID for database logging
        form_submission_id: Optional form submission ID for database logging

    Returns:
        Dictionary with provider results
    """
    start_time = time.time()
    scraper_func = SCRAPER_FUNCTIONS.get(provider_code)
    provider_meta = PROVIDER_INFO.get(provider_code, {})

    if not scraper_func:
        return {
            'provider_name': provider_meta.get('name', provider_code),
            'provider_code': provider_code,
            'provider_color': provider_meta.get('color', '#000000'),
            'provider_logo': provider_meta.get('logo', ''),
            'plans': [],
            'error': 'Scraper not found',
            'fetch_time': 0
        }

    try:
        # Call the scraper function
        raw_data = scraper_func(params)
        fetch_time = time.time() - start_time

        # Parse response based on provider
        if provider_code == 'sanlam':
            plans = parse_sanlam_response(raw_data)
        elif provider_code == 'mcma':
            plans = parse_mcma_response(raw_data)
        elif provider_code == 'rma':
            plans = parse_rma_response(raw_data)
        elif provider_code == 'axa':
            plans = parse_axa_response(raw_data)
        else:
            plans = []

        # Save scraper result to database if user_id and form_submission_id are provided
        if user_id and form_submission_id:
            try:
                DatabaseManager.save_scraper_result(
                    form_submission_id=form_submission_id,
                    user_id=user_id,
                    provider_code=provider_code,
                    provider_name=provider_meta.get('name', provider_code),
                    raw_response=raw_data,
                    plan_count=len(plans),
                    fetch_time=fetch_time,
                    status='success',
                    error_message=None if plans else 'No plans returned'
                )
            except Exception as db_error:
                print(f"⚠️  Failed to save scraper result to database: {db_error}")

        return {
            'provider_name': provider_meta.get('name', provider_code),
            'provider_code': provider_code,
            'provider_color': provider_meta.get('color', '#000000'),
            'provider_logo': provider_meta.get('logo', ''),
            'raw_data': raw_data,  # Keep raw data for debugging
            'plans': plans,
            'error': None if plans else 'No plans returned',
            'fetch_time': round(fetch_time, 2)
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        fetch_time = time.time() - start_time

        # Save error result to database if user_id and form_submission_id are provided
        if user_id and form_submission_id:
            try:
                DatabaseManager.save_scraper_result(
                    form_submission_id=form_submission_id,
                    user_id=user_id,
                    provider_code=provider_code,
                    provider_name=provider_meta.get('name', provider_code),
                    raw_response=None,
                    plan_count=0,
                    fetch_time=fetch_time,
                    status='error',
                    error_message=str(e)
                )
            except Exception as db_error:
                print(f"⚠️  Failed to save error result to database: {db_error}")

        return {
            'provider_name': provider_meta.get('name', provider_code),
            'provider_code': provider_code,
            'provider_color': provider_meta.get('color', '#000000'),
            'provider_logo': provider_meta.get('logo', ''),
            'plans': [],
            'raw_data': None,
            'error': str(e),
            'fetch_time': round(fetch_time, 2)
        }


def get_all_quotes(params, user_id=None, form_submission_id=None):
    """
    Fetch quotes from all providers in parallel

    Args:
        params: Dictionary with request parameters
        user_id: Optional user ID for database logging
        form_submission_id: Optional form submission ID for database logging

    Returns:
        Dictionary with all provider results
    """
    total_start = time.time()
    results = []

    # Fetch from all providers in parallel
    provider_codes = list(SCRAPER_FUNCTIONS.keys())

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(provider_codes)) as executor:
        future_to_provider = {
            executor.submit(fetch_from_provider, code, params, user_id, form_submission_id): code
            for code in provider_codes
        }

        for future in concurrent.futures.as_completed(future_to_provider):
            result = future.result()
            results.append(result)

    total_time = time.time() - total_start

    # Build response
    providers = []
    errors = []

    for result in results:
        provider_data = {
            "name": result['provider_name'],
            "code": result['provider_code'],
            "color": result['provider_color'],
            "logo": result['provider_logo'],
            "plans": result.get('plans', []),
            "plan_count": len(result.get('plans', [])),
            "fetch_time": result['fetch_time']
        }

        if result.get('error'):
            provider_data["error"] = result['error']
            errors.append(f"{result['provider_name']}: {result['error']}")

        providers.append(provider_data)

    return {
        "success": len(errors) < len(provider_codes),
        "params": params,
        "providers": providers,
        "summary": {
            "total_providers": len(results),
            "providers_with_results": sum(1 for r in results if r.get('plans')),
            "total_fetch_time": round(total_time, 2),
        },
        "errors": errors if errors else None
    }


def compare_insurance(valeur_neuf: float, valeur_venale: float) -> Dict[str, Any]:
    """
    Convenience function to compare insurance quotes

    Args:
        valeur_neuf: New vehicle value in MAD
        valeur_venale: Current vehicle value in MAD

    Returns:
        Comparison results from all providers
    """
    return get_all_quotes({
        "valeur_neuf": valeur_neuf,
        "valeur_venale": valeur_venale
    })


# Main execution for testing
if __name__ == "__main__":
    print("Testing Insurance Comparison Service...")
    print("="*60)

    test_params = {
        "valeur_neuf": 650000,
        "valeur_venale": 650000
    }

    result = get_all_quotes(test_params)

    print(f"\nFetched from {result['summary']['providers_with_results']} providers")
    print(f"Total time: {result['summary']['total_fetch_time']}s\n")

    for provider in result['providers']:
        print(f"{provider['name']}: ", end="")
        if provider.get('error'):
            print(f"ERROR - {provider['error']}")
        else:
            print(f"SUCCESS - {provider['plan_count']} plans ({provider['fetch_time']}s)")

    if result.get('errors'):
        print(f"\nErrors: {result['errors']}")

    # Save to file for inspection
    with open('comparison_test_result.json', 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print("\nFull results saved to comparison_test_result.json")
