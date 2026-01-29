"""
RMA Insurance Scraper - Browser-Based Functional Style
Fetches quotations from RMA Direct website using browser automation
Integrates with main website form data
"""

import time
import random
import json
import logging
from datetime import datetime
from typing import Dict, Any
from camoufox.sync_api import Camoufox

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============ FUEL TYPE MAPPING ============
# Maps website form fuel values to RMA form selections
FUEL_TYPE_MAPPING = {
    "essence": "ESSENCE",
    "diesel": "DIESEL",
    "hybrid-e": "HYBRIDE ESSENCE",
    "hybrid-d": "HYBRIDE DIESEL",
    "electrique": "ELECTRIQUE"
}

# Maps RMA form selections to API payload values
RMA_FUEL_PAYLOAD_MAPPING = {
    "essence": "1",        # RMA position 1
    "diesel": "2",         # RMA position 2
    "hybrid-e": "4",       # RMA position 4
    "hybrid-d": "5",       # RMA position 5
    "electrique": "3"      # RMA position 3 (electric)
}

# Plate type mapping
RMA_PLATE_TYPE_MAPPING = {
    "standard": "Plaque standard",
    "ww": "WW"
}

# Store responses for analysis
captured_responses = []


def random_sleep(min_ms=500, max_ms=1500):
    """Add human-like random delay"""
    time.sleep(random.uniform(min_ms, max_ms) / 1000)


def fill_text_input(page, input_selector, value, label="", index=None):
    """Fill a text input field
    
    Args:
        page: Playwright page object
        input_selector: CSS selector for input
        value: Value to fill
        label: Label for logging
        index: If multiple elements match, use this index (nth)
    """
    if not value:
        return
    
    try:
        input_field = page.locator(input_selector)
        
        # If index is specified (for multiple matching elements like date fields)
        if index is not None:
            input_field = input_field.nth(index)
        
        input_field.wait_for(state="visible", timeout=5000)
        input_field.fill(str(value))
        logger.info(f"Filled {label or input_selector}: {value}")
    except Exception as e:
        logger.warning(f"Could not fill {label or input_selector}: {e}")


def fill_mui_dropdown(page, label_text, value, debug_label=""):
    """
    Handles MUI dropdowns by clicking the input via its label and selecting an option.
    """
    if not value:
        return
    
    print(f"Selecting {debug_label or label_text}: {value}...")
    try:
        # Use fuzzy text matching for the label
        dropdown_input = page.locator(f"div.direct-MuiAutocomplete-root:has(label:has-text('{label_text}')) input")
        dropdown_input.wait_for(state="visible", timeout=10000)
        
        dropdown_input.click()
        random_sleep(300, 600)
        dropdown_input.fill(value)
        
        # Wait for the listbox to appear
        page.wait_for_selector("ul[role='listbox']", timeout=5000)
        random_sleep(500, 800)
        
        # Find the exact matching option in the listbox
        listbox_options = page.locator("ul[role='listbox'] li[role='option']")
        option_count = listbox_options.count()
        
        # Try to find the exact matching option
        found = False
        for i in range(option_count):
            option_text = listbox_options.nth(i).inner_text().strip()
            if value.upper() in option_text.upper():
                print(f"Found matching option: {option_text}")
                listbox_options.nth(i).click()
                found = True
                break
        
        if not found:
            # Fallback: select first option if exact match not found
            print(f"Exact match not found for '{value}', selecting first option")
            page.keyboard.press("ArrowDown")
            page.keyboard.press("Enter")
        
        random_sleep(800, 1200)
        logger.info(f"Dropdown {debug_label or label_text} selected: {value}")
    except Exception as e:
        logger.warning(f"Could not select {debug_label or label_text}: {e}")


def scrape_rma(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main RMA scraper function - Called from website
    
    Args:
        params: Form parameters from website
            - nom: Last name
            - prenom: First name
            - carburant: Fuel type (essence, diesel, hybrid-e, hybrid-d, electrique)
            - puissance_fiscale: Fiscal power
            - date_mec: Vehicle circulation date (YYYY-MM-DD)
            - type_plaque: Plate type (standard, ww)
            - immatriculation: Registration number (will use dummy if not provided)
            - valeur_neuf: New vehicle value
            - valeur_actuelle: Current market value
            - nombre_places: Number of seats
            - date_naissance: Birth date (YYYY-MM-DD)
            - telephone: Phone number
            - ville: City name
    
    Returns:
        Dictionary with quotation data or error message
    """
    
    # Validate required parameters
    required_fields = ['nom', 'prenom', 'carburant', 'puissance_fiscale', 'date_mec',
                      'type_plaque', 'valeur_neuf', 'valeur_actuelle', 'nombre_places',
                      'date_naissance', 'telephone']
    
    missing_fields = [f for f in required_fields if f not in params or not params[f]]
    if missing_fields:
        return {
            "success": False,
            "error": f"Missing required fields: {', '.join(missing_fields)}",
            "provider": "rma"
        }
    
    # Map fuel type to RMA form display text
    fuel_code = params.get('carburant', 'diesel').lower()
    fuel_display = FUEL_TYPE_MAPPING.get(fuel_code, 'DIESEL')
    
    # Map plate type
    plate_type = params.get('type_plaque', 'standard').lower()
    plate_display = RMA_PLATE_TYPE_MAPPING.get(plate_type, 'Plaque standard')
    
    # Use provided immatriculation or generate dummy
    immatriculation = params.get('immatriculation', '')
    if not immatriculation:
        # Generate dummy plate: 5 digits - F/A - 2 digits
        five_digits = "".join(random.choices('0123456789', k=5))
        letter = random.choice(['F', 'A'])
        two_digits = "".join(random.choices('0123456789', k=2))
        immatriculation = f"{five_digits}-{letter}-{two_digits}"
    
    browser_config = {
        "headless": True,
        "humanize": True,
        "os": "windows",
        "geoip": True
    }
    
    try:
        logger.info(f"Starting RMA scraper for {params.get('nom')} {params.get('prenom')}")
        
        # Store both requests and responses for analysis
        captured_responses = []
        
        def capture_response(response):
            """Capture API responses"""
            try:
                if "/offer/api/offers" in response.url and response.status == 200:
                    try:
                        response_json = response.json()
                        captured_responses.append(response_json)
                        logger.info(f"Captured API response - Total: {len(captured_responses)}")
                    except:
                        pass
            except Exception as e:
                logger.debug(f"Error capturing response: {e}")
        
        with Camoufox(**browser_config) as browser:
            page = browser.new_page()
            page.on("response", capture_response)

            try:
                # Navigate to RMA Direct
                logger.info("Navigating to RMA Assurance...")
                page.goto("https://direct.rmaassurance.com/souscrire", timeout=60000)
                random_sleep(1000, 2000)

                # Step 1: Click 'Suivant' to reach the main form
                logger.info("Clicking first 'Suivant'...")
                page.locator("button:has-text('Suivant')").first.click()
                random_sleep(1000, 2000)
                
                # Wait for form to load
                name_input = page.locator('input[name="subscriber.lastName"]')
                name_input.wait_for(state="visible", timeout=20000)
                random_sleep(1000, 2000)

                # --- Step 2: Fill Personal Information ---
                logger.info("Filling personal information...")
                
                fill_text_input(page, 'input[name="subscriber.lastName"]', params['nom'], "Last Name")
                fill_text_input(page, 'input[name="subscriber.firstName"]', params['prenom'], "First Name")
                fill_mui_dropdown(page, "Ville", params.get('ville', 'CASABLANCA'), "City")
                fill_text_input(page, 'input[name="subscriber.phone"]', params['telephone'], "Phone")

                # Dates: Convert YYYY-MM-DD to JJ/MM/AAAA
                birth_date = params.get('date_naissance', '')
                if birth_date and len(birth_date) == 10:  # YYYY-MM-DD format
                    birth_date_formatted = f"{birth_date[8:10]}/{birth_date[5:7]}/{birth_date[0:4]}"
                else:
                    birth_date_formatted = birth_date

                # License date field (using placeholder matching with index)
                license_date = params.get('date_permis', '')
                if license_date and len(license_date) == 10:
                    license_date_formatted = f"{license_date[8:10]}/{license_date[5:7]}/{license_date[0:4]}"
                else:
                    license_date_formatted = license_date

                # Fill birth date (nth:0)
                fill_text_input(page, 'input[placeholder="JJ/MM/AAAA"]', birth_date_formatted, "Birth Date", index=0)
                # Fill license date (nth:1)
                fill_text_input(page, 'input[placeholder="JJ/MM/AAAA"]', license_date_formatted, "License Date", index=1)

                # --- Step 3: Scroll to Vehicle Section ---
                logger.info("Scrolling to vehicle information section...")
                page.mouse.wheel(0, 600)
                random_sleep(1000, 1500)

                # --- Step 4: Fill Vehicle Information ---
                logger.info("Filling vehicle information...")
                
                fill_mui_dropdown(page, "Type de plaque", plate_display, "Plate Type")
                fill_text_input(page, 'input[name="vehicleInformations.plateNumber"]', immatriculation, "Registration")
                
                fill_mui_dropdown(page, "Puissance fiscale", str(params['puissance_fiscale']), "Fiscal Power")
                fill_mui_dropdown(page, "Combustible", fuel_display, "Fuel Type")
                
                # Vehicle circulation date (nth:2)
                mec_date = params.get('date_mec', '')
                if mec_date and len(mec_date) == 10:
                    mec_date_formatted = f"{mec_date[8:10]}/{mec_date[5:7]}/{mec_date[0:4]}"
                else:
                    mec_date_formatted = mec_date
                
                fill_text_input(page, 'input[placeholder="JJ/MM/AAAA"]', mec_date_formatted, "Vehicle Date", index=2)
                
                # Prices and seats
                fill_text_input(page, 'input[name="vehicleInformations.newPrice"]', params['valeur_neuf'], "New Value")
                fill_text_input(page, 'input[name="vehicleInformations.marketPrice"]', params['valeur_actuelle'], "Market Value")
                fill_text_input(page, 'input[name="vehicleInformations.placesNumber"]', params['nombre_places'], "Number of Seats")

                # --- Step 5: Submit & Capture Response ---
                logger.info("Submitting form...")
                
                annual_response = None
                semi_annual_response = None
                
                # Wait for first response (12 months)
                with page.expect_response(lambda r: "/offer/api/offers" in r.url and r.status == 200, timeout=30000) as resp_promise:
                    page.locator("button:has-text('Suivant')").last.click()
                    random_sleep(2000, 3000)

                response = resp_promise.value
                annual_response = response.json()
                logger.info("Captured 12-month quotation")
                random_sleep(1000, 1500)

                # --- Step 6: Click 6 months radio button ---
                logger.info("Clicking 6 months option...")
                
                try:
                    # The radio input is hidden, so we click the label instead
                    six_months_label = page.locator("label[for='6 mois']")
                    six_months_label.wait_for(state="visible", timeout=20000)
                    logger.info("6 months label found and visible")
                    
                    # Set up response capture BEFORE clicking
                    with page.expect_response(
                        lambda r: "/offer/api/offers" in r.url and r.status == 200,
                        timeout=20000
                    ) as response_promise:
                        logger.info("Clicking 6 months label...")
                        six_months_label.click()
                        logger.info("6 months label clicked, waiting for response...")
                        random_sleep(2000, 2500)
                    
                    # Get the response
                    response_6m = response_promise.value
                    semi_annual_response = response_6m.json()
                    logger.info("Captured 6-month quotation from expect_response")
                    
                except Exception as e:
                    logger.warning(f"6-month quotation capture failed: {e}")
                    semi_annual_response = None

                # Log captured responses
                logger.info(f"Total API responses captured: {len(captured_responses)}")
                
                # Extract quotation data from responses
                try:
                    if captured_responses and len(captured_responses) > 0:
                        annual_data = captured_responses[0]
                        if isinstance(annual_data, dict) and "offers" in annual_data:
                            annual_response = annual_data["offers"]
                            logger.info(f"✓ Annual offers: {len(annual_response) if annual_response else 0} packages")
                except Exception as e:
                    logger.warning(f"Could not extract annual data: {e}")
                
                try:
                    if captured_responses and len(captured_responses) > 1:
                        semi_annual_data = captured_responses[1]
                        if isinstance(semi_annual_data, dict) and "offers" in semi_annual_data:
                            semi_annual_response = semi_annual_data["offers"]
                            logger.info(f"✓ Semi-annual offers: {len(semi_annual_response) if semi_annual_response else 0} packages")
                except Exception as e:
                    logger.warning(f"Could not extract semi-annual data: {e}")

                # Return simplified response with only essential data
                success = annual_response is not None
                logger.info(f"Scraping complete - Success: {success}")
                
                return {
                    "success": success,
                    "annual": annual_response or [],
                    "semi_annual": semi_annual_response or []
                }

            except Exception as e:
                logger.error(f"Error during scraping: {e}")
                try:
                    page.screenshot(path="rma_error_debug.png")
                except:
                    pass
                
                return {
                    "success": False,
                    "annual": [],
                    "semi_annual": []
                }
            finally:
                random_sleep(2000, 3000)

    except Exception as e:
        logger.error(f"Browser error: {e}")
        return {
            "success": False,
            "annual": [],
            "semi_annual": []
        }


def filter_rma_response(raw_response: Dict[str, Any]) -> Dict[str, Any]:
    """
    Filter RMA response to return only the needed fields for display:
    - libelle: package name
    - primeTotalTTC: main price value
    - points: list of guarantee labels (included guarantees only)

    Returns filtered data for both annual and semi_annual periods.
    """
    if not raw_response or not raw_response.get('success'):
        return raw_response

    def filter_packages(packages):
        if not packages or not isinstance(packages, list):
            return []

        filtered = []
        for pkg in packages:
            if not pkg:
                continue

            # Extract only included guarantee labels as points
            points = []
            for g in pkg.get('garanties', []):
                if g.get('included', False):
                    label = g.get('libelle', '')
                    if label:
                        points.append(label)

            filtered.append({
                'libelle': pkg.get('libelle', ''),
                'primeTotalTTC': pkg.get('primeTotalTTC', 0),
                'points': points
            })

        return filtered

    return {
        'success': True,
        'annual': filter_packages(raw_response.get('annual', [])),
        'semi_annual': filter_packages(raw_response.get('semi_annual', []))
    }


def test_rma_scraper():
    """
    Test function for direct testing without website
    Can be called directly: python -c "from rma_scraper import test_rma_scraper; test_rma_scraper()"
    """
    test_params = {
        "nom": "Huzaifa",
        "prenom": "Saeed",
        "carburant": "diesel",
        "puissance_fiscale": 6,
        "date_mec": "2023-01-01",
        "type_plaque": "standard",
        "immatriculation": "0000-F-00",  # Will use this or generate dummy
        "valeur_neuf": 400000,
        "valeur_actuelle": 300000,
        "nombre_places": 5,
        "date_naissance": "1991-01-01",
        "telephone": "0666666666",
        "date_permis": "2012-01-01",
        "ville": "CASABLANCA"
    }
    
    print("=" * 60)
    print("RMA SCRAPER TEST")
    print("=" * 60)
    print(f"Testing with parameters: {json.dumps(test_params, indent=2)}")
    print("-" * 60)
    
    result = scrape_rma(test_params)
    
    print("-" * 60)
    if result.get('success'):
        print("[PASS] Test PASSED - RMA quotations retrieved successfully")
        
        annual_data = result.get('annual')
        semi_annual_data = result.get('semi_annual')
        
        print(f"\n12-Month Quotation: {type(annual_data).__name__}")
        if isinstance(annual_data, list):
            print(f"  - Items: {len(annual_data)}")
        elif isinstance(annual_data, dict):
            print(f"  - Keys: {list(annual_data.keys())}")
        
        print(f"\n6-Month Quotation: {type(semi_annual_data).__name__}")
        if semi_annual_data:
            if isinstance(semi_annual_data, list):
                print(f"  - Items: {len(semi_annual_data)}")
            elif isinstance(semi_annual_data, dict):
                print(f"  - Keys: {list(semi_annual_data.keys())}")
        else:
            print("  - Not captured")
        
        # Save result to file
        with open("rma_test_result.json", "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print("\nFull result saved to: rma_test_result.json")
    else:
        print("[FAIL] Test FAILED")
        print(f"Error: {result.get('error')}")
    
    print("=" * 60)


if __name__ == "__main__":
    # Run test when executed directly
    test_rma_scraper()