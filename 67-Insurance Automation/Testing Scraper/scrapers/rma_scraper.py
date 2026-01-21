# # """
# # RMA Assurance Scraper - Simple Functional Style
# # Fetches quotations from RMA API
# # """

# # import requests
# # import time

# # # Global session and token storage
# # _session = None
# # _access_token = None
# # _token_expiry = 0


# # def get_session():
# #     """Get or create session"""
# #     global _session
# #     if _session is None:
# #         _session = requests.Session()
# #     return _session


# # def get_access_token():
# #     """Get JWT access token from RMA"""
# #     global _access_token, _token_expiry

# #     url = "https://direct.rmaassurance.com/canaldirect/auth/api/token"
# #     params = {"csrt": "10651071086600842364"}

# #     headers = {
# #         "User-Agent": "Mozilla/5.0",
# #         "Accept": "*/*",
# #         "X-Ts-Ajax-Request": "true",
# #         "X-Security-Csrf-Token": "08553bbd45ab28005d86670b015bbbef2fb54e2a9d8594b3b1d3723b8159ff014c78580f30e2b3b41d94d0813e29e1dc",
# #         "Referer": "https://direct.rmaassurance.com/souscrire",
# #     }

# #     try:
# #         session = get_session()
# #         response = session.get(url, headers=headers, params=params, timeout=30)
# #         response.raise_for_status()

# #         data = response.json()
# #         _access_token = data["accessToken"]
# #         _token_expiry = time.time() + data.get("expiresIn", 7200)

# #         return _access_token
# #     except Exception as e:
# #         print(f"RMA Token Error: {str(e)}")
# #         return None


# # def ensure_token():
# #     """Ensure we have a valid access token"""
# #     global _access_token, _token_expiry

# #     if not _access_token or time.time() >= _token_expiry - 60:
# #         return get_access_token()
# #     return _access_token


# # def fetch_rma_offers(payload):
# #     """
# #     Fetch insurance offers from RMA API

# #     Args:
# #         payload: Dictionary containing insurance request data

# #     Returns:
# #         List of offer dictionaries or empty list on error
# #     """
# #     # Ensure we have valid token
# #     token = ensure_token()
# #     if not token:
# #         return []

# #     url = "https://direct.rmaassurance.com/canaldirect/offer/api/offers"
# #     params = {"csrt": "1104538121806306204"}

# #     headers = {
# #         "Authorization": f"Bearer {token}",
# #         "Content-Type": "application/json",
# #         "Accept": "application/json",
# #         "Origin": "https://direct.rmaassurance.com",
# #         "Referer": "https://direct.rmaassurance.com/souscrire",
# #         "X-Requested-With": "XMLHttpRequest",
# #     "X-Security-Csrf-Token": "08553bbd45ab2800740a9b4e9ad9d5649f1d310a3d712677041148e8cbb0429de2f502a5f356328d4f4c38180374b234",
# #     "X-TS-Ajax-Request": "true",

# #     # These custom headers must be sent exactly as-is
# #     "xa4vrhyp3q-a": "3_RnoqXBJQr0L8gEJiRIvwuKMNdImkzfU2p5us1XETvDIb6TVY2Ib1d8=bi0tg=rl6z0KMTpeSSDv6K4mk0BQ4XnxA-IO1N7rrOy8NE3mVKPNPXo=...",
# #     "xa4vrhyp3q-b": "7p8hvt",
# #     "xa4vrhyp3q-c": "AKAcCtibAQAA6izjY9C9aADgLswCThP-w-GSJoJNjB-RvO-L4cmimTKxqjyL",
# #     "xa4vrhyp3q-d": "ABaAhIDBCKGFgQGAAYIQgISigaIAwBGAzvpCzi_33wfJopkysao8iwAAAABOA78XBnlVMMOxrTxuPSv8um18b8A",
# #     "xa4vrhyp3q-f": "A1V-DdibAQAAfM9XT3sAMnNd3U7zUUvigKdrIrAj68Z8qGo_VCn-5sthtpWTAZrA11GucmbRwH8AAEB3AAAAAA==",
# #     "xa4vrhyp3q-z": "q",

# #     # All cookies in ONE line exactly like browser
# #     "Cookie": (
# #         "TS01e69de6=01259e8ac6d9078ec8e1eaeca87ee3d7f1f31b157b6f6d42fa7b75530a6bda4a10015b5d309752f64e5901cad9eb502f02bc3cf3c9; "
# #         "TS01e69de6028=01d631d5719cbdcbdf3bee24a9e70e64498de44d4a5b9ccda3d806821d19f17b99ca1265885856c53f3481a3079f2467e7a2d7e411; "
# #         "_gcl_au=1.1.2128492167.1768856323; _ga=GA1.1.1387105109.1768856323; "
# #         "_fbp=fb.1.1768856323220.91126079335581366; "
# #         "__Host-next-auth.csrf-token=214be1483b96a1a80292c66534ec6c3c5a1dea426f632795a7b543b3cbbe8dbe%7C17cf9e97805b9a1fa2f65411e5ef91c493d5d6f04f6bb26fc1688bd631a8f5ac; "
# #         "__Secure-next-auth.callback-url=https%3A%2F%2Fdirect.rmaassurance.com; "
# #         "XSRF-TOKEN=70e63598-2283-41fe-b754-3fd8a13efe20"
# #     )
# # }

# #     try:
# #         session = get_session()
# #         response = session.post(
# #             url,
# #             headers=headers,
# #             params=params,
# #             json=payload,
# #             timeout=30
# #         )
# #         response.raise_for_status()
# #         print(response.text)
# #         data = response.json()
# #         return data

# #     except Exception as e:
# #         print(f"RMA API Error: {str(e)}")
# #         return []


# # def scrape_rma(params):
# #     """
# #     Main function to scrape RMA for both Annual and Semi-Annual plans
# #     """
# #     from .field_mapper import FieldMapper
# #     import copy
# #     from datetime import datetime, timedelta

# #     # Base payload
# #     base_payload = FieldMapper.map_for_scraper(params, "rma")
# #     print(f"Here is the base payload: {base_payload}")
# #     # Parse dateEffet
# #     date_effet = datetime.strptime(base_payload["dateEffet"], "%d-%m-%Y")

# #     # -------- Annual (12 months) --------
# #     annual_payload = copy.deepcopy(base_payload)
# #     annual_payload["duree"] = "12"
# #     annual_payload["dureeContratEnJour"] = 365
# #     annual_payload["dateEcheance"] = (date_effet + timedelta(days=365)).strftime("%d-%m-%Y")

# #     annual_result = fetch_rma_offers(annual_payload)

# #     # -------- Semi-Annual (6 months) --------
# #     semi_payload = copy.deepcopy(base_payload)
# #     semi_payload["duree"] = "6"
# #     semi_payload["dureeContratEnJour"] = 180
# #     semi_payload["dateEcheance"] = (date_effet + timedelta(days=180)).strftime("%d-%m-%Y")

# #     semi_result = fetch_rma_offers(semi_payload)


# #     return {
# #         "annual": annual_result,
# #         "semi_annual": semi_result,
# #     }



# # # ===== FOR LOCAL TESTING =====
# # if __name__ == "__main__":
# #     # Hardcoded payload for testing
# #     test_payload = {
# #         "nomOrRaisonSociale": "Huzaifa",
# #         "prenom": "Saeed",
# #         "titreCivilite": "1",
# #         "typePieceIdentite": "1",
# #         "situationFamiliale": "C",
# #         "telephone": "0661776677",
# #         "dateNaissance": "17-01-1969",
# #         "idVilleAdresse": "6",
# #         "dateObtentionPermis": "08-01-2017",
# #         "sexeConducteur": "M",
# #         "sexe": "M",
# #         "idPaysPermisConducteur": "212",
# #         "idPaysPermis": "212",
# #         "professionConducteur": "99",
# #         "profession": "99",
# #         "numeroClient": "308252166",
# #         "numeroClientConducteur": "308252166",
# #         "telephoneConducteur": "0661776677",
# #         "nomOrRaisonSocialeConducteur": "Huzaifa",
# #         "prenomConducteur": "Saeed",
# #         "situationFamilialeConducteur": "C",
# #         "dateNaissanceConducteur": "17-01-1969",
# #         "idVilleAdresseConducteur": "6",
# #         "titreCiviliteConducteur": "1",
# #         "dateObtentionPermisConducteur": "08-01-2017",
# #         "typePieceIdentiteConducteur": "1",
# #         "nombreEnfant": "0",
# #         "codeUsageVehicule": "1",
# #         "idGenre": "1",
# #         "typeImmatriculation": "3",
# #         "immatriculation": "00000-F-00",
# #         "tauxCRM": 1,
# #         "crmFMSAR": 1,
# #         "carburant": "2",
# #         "puissanceFiscale": "11",
# #         "dateMiseEnCirculation": "08-01-2017",
# #         "heureMiseEnCirculation": "04",
# #         "nombrePlace": 5,
# #         "valeurANeuf": "65000",
# #         "valeurVenale": "45000",
# #         "referenceCRMFMSAR": "14E9999/26/19599",
# #         "avecBaremeConventionnel": "off",
# #         "natureContrat": "F",
# #         "dateEffet": "08-01-2026",
# #         "heureEffet": 6,
# #         "dateEcheance": "08-01-2027",
# #         "heureEcheance": 6,
# #         "dateEvenement": "08-01-2026",
# #         "heureEvenement": 6,
# #         "duree": "12",
# #         "dureeContratEnJour": 365,
# #         "dateEtablissement": "08-01-2026",
# #         "typeContrat": 1,
# #         "modePaiement": "8",
# #         "modePaiementCanalDirect": "8",
# #         "typeLivraison": "home",
# #         "typeCouverture": "1",
# #         "clientConducteur": "on",
# #         "vehiculeAgarage": "off",
# #         "avecDelegation": "off",
# #         "dateEffetInitiale": "08-01-2026",
# #         "formatAttestation": "3",
# #         "avecReductionSaharienne": "off",
# #         "typeCanal": 3,
# #         "idUtilisateur": 3405,
# #         "idProduit": "1",
# #         "idIntermediaire": "8714",
# #         "typeClient": "1",
# #         "typeConducteur": "1",
# #         "numeroDevis": "202026013227",
# #         "typeEvenement": "100",
# #         "avecAntivole": "on",
# #         "intermediaryChanged": "off",
# #         "specialOffer": "Z200-AA"
# #     }

# #     # Test the scraper
# #     print("Testing RMA Scraper...")
# #     result = fetch_rma_offers(test_payload)

# #     if result:
# #         print(f"Success! Got {len(result)} offers")
# #         import json
# #         print(json.dumps(result, indent=2))
# #     else:
# #         print("Failed to fetch offers")


# import time
# import json
# from playwright.sync_api import sync_playwright

# def run():
#     with sync_playwright() as p:
#         # 1. Launch Browser with Stealth Settings
#         # We use specific arguments to hide the fact that this is an automated bot
#         browser = p.chromium.launch(
#             headless=False, # Set to True for production, False to see it working
#             args=[
#                 "--disable-blink-features=AutomationControlled",
#                 "--no-sandbox",
#                 "--disable-infobars"
#             ]
#         )
        
#         # Create a context with a real User Agent and viewport to mimic a real user
#         context = browser.new_context(
#             user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
#             viewport={"width": 1366, "height": 768},
#             locale="fr-FR",
#             timezone_id="Africa/Casablanca"
#         )
        
#         # Anti-detection script injection
#         context.add_init_script("""
#             Object.defineProperty(navigator, 'webdriver', {
#                 get: () => undefined
#             });
#         """)

#         page = context.new_page()

#         print("--- Navigating to Initial Page ---")
#         page.goto("https://direct.rmaassurance.com/souscrire")

#         # ---------------------------------------------------------
#         # STEP 1: Click the first "Suivant" button
#         # ---------------------------------------------------------
#         print("--- Clicking First 'Suivant' Button ---")
#         # We use a robust selector finding the text "Suivant" to avoid brittle dynamic classes
#         # page.wait_for_selector("text=Suivant")
#         # page.locator("button", has_text="Suivant").first.click()

#         # # ---------------------------------------------------------
#         # # STEP 2: Fill the Form (Step 2/3)
#         # # ---------------------------------------------------------
#         # print("--- Waiting for Form to Load ---")
#         # # Wait for the Name field to ensure page transition is complete
#         # page.wait_for_selector('input[name="subscriber.lastName"]')

#         # print("--- Filling Hardcoded Data ---")

#         # # --- Helper function for Material UI Autocomplete Dropdowns ---
#         # def select_mui_dropdown(label_text, value_to_type):
#         #     # 1. Find the input associated with the label
#         #     # We use XPath to find the label, then get the input inside the parent div
#         #     locator = page.locator(f"//label[contains(text(), '{label_text}')]/following-sibling::div//input")
#         #     locator.click()
#         #     # Clear existing text if any
#         #     locator.fill("") 
#         #     # Type the value slowly to trigger the dropdown
#         #     locator.type(value_to_type, delay=100)
            
#         #     # Wait for the dropdown options to appear (role="listbox") and click the first valid option
#         #     # Adjust specific selector if you need an exact match, currently selects first hit
#         #     page.locator("ul[role='listbox'] li").first.click()
#         #     time.sleep(0.5) # Brief pause for UI animation

#         # # 1. Personal Information
#         # page.fill('input[name="subscriber.lastName"]', "huzaifaaa")
#         # page.fill('input[name="subscriber.firstName"]', "Saeedaa")
        
#         # # ID 6 usually corresponds to a major city. We simulate typing to select it.
#         # select_mui_dropdown("Ville", "Rabat") 
        
#         # page.fill('input[name="subscriber.phone"]', "0666666666")
        
#         # # Date fields (Format YYYY-MM-DD or DD/MM/YYYY depending on locale)
#         # # MUI inputs often accept direct typing if focused.
#         # page.fill('//label[contains(text(), "Date de naissance")]/following-sibling::div//input', "01/01/1991")
#         # page.fill('//label[contains(text(), "Date d’obtention de permis")]/following-sibling::div//input', "01/01/2012")

#         # ## Select Standard Plate (Usually labeled "Normale" in French interfaces)
#         # # If the dropdown text on screen says "Standard", change "Normale" to "Standard" below.
#         # select_mui_dropdown("Type de plaque", "Plaque standard")        
#         # # Updated Plate Number format: 0000-F-00
#         # page.fill('input[name="vehicleInformations.plateNumber"]', "1000-F-00")
#         # select_mui_dropdown("Puissance fiscale", "6")
#         # select_mui_dropdown("Combustible", "DIESEL")
        
#         # page.fill('//label[contains(text(), "Date de mise en circulation")]/following-sibling::div//input', "01/01/2023")
        
#         # page.fill('input[name="vehicleInformations.newPrice"]', "400000")
#         # page.fill('input[name="vehicleInformations.marketPrice"]', "300000")
#         # page.fill('input[name="vehicleInformations.placesNumber"]', "5")

#         # # ---------------------------------------------------------
#         # # STEP 3: Submit and Intercept API
#         # # ---------------------------------------------------------
#         # print("--- Submitting and Intercepting Request ---")
#         input("Press Enter to submit the form and capture the API response...")
#         # We define the specific API endpoint we want to capture
#         target_url = "https://direct.rmaassurance.com/canaldirect/offer/api/offers"

#         # This block ensures we capture the response triggered by the click
#         with page.expect_response(lambda response: target_url in response.url and response.request.method == "POST", timeout=10000) as response_info:
            
#             # Click the Next/Submit button at the bottom of the form
#             # We look for the button inside the footer container to distinguish from the top one
#             time.sleep(500)
#             # page.locator("button", has_text="Suivant").last.click()
#             time.sleep(5)

#         # ---------------------------------------------------------
#         # STEP 4: Print Response
#         # ---------------------------------------------------------
#         api_response = response_info.value
        
#         print("\n" + "="*50)
#         print(f"STATUS CODE: {api_response.status}")
#         print("="*50)
        
#         try:
#             # Try to parse JSON, if it's text/html print text
#             json_data = api_response.json()
#             print("RESPONSE BODY (JSON):")
#             print(json.dumps(json_data, indent=4))
#         except:
#             print("RESPONSE BODY (TEXT):")
#             print(api_response.text())
            
#         print("="*50)
        
#         # Keep browser open briefly to verify visually
#         time.sleep(10000)
#         # browser.close()

# if __name__ == "__main__":
#     run()



import time
import random
import json
import os
from playwright.sync_api import sync_playwright

# --- CONFIGURATION ---
# Create a folder in your project directory to store the browser profile
USER_DATA_DIR = "./chrome_profile" 

if not os.path.exists(USER_DATA_DIR):
    os.makedirs(USER_DATA_DIR)

# --- HELPER FUNCTIONS ---
def random_sleep(min_seconds=0.5, max_seconds=1.5):
    time.sleep(random.uniform(min_seconds, max_seconds))

def human_type(page, selector, text):
    """Types text like a human with random delays."""
    try:
        page.hover(selector)
        random_sleep(0.2, 0.4)
        page.click(selector)
        
        for char in text:
            page.keyboard.type(char)
            # Random delay between keystrokes (30ms - 100ms)
            time.sleep(random.uniform(0.03, 0.1))
            
        random_sleep(0.3, 0.7)
    except Exception as e:
        print(f"Error typing into {selector}: {e}")

def select_mui_dropdown_human(page, label_text, value_to_type):
    """Selects from Material UI dropdown using keyboard navigation."""
    print(f"Selecting {label_text}...")
    xpath = f"//label[contains(text(), '{label_text}')]/following-sibling::div//input"
    
    human_type(page, xpath, value_to_type)
    
    try:
        # Wait for the dropdown list to appear
        page.wait_for_selector("ul[role='listbox']", state="visible", timeout=3000)
        random_sleep(0.3, 0.6)
        
        # Use keyboard to select (more human-like than clicking coordinates)
        page.keyboard.press("ArrowDown")
        time.sleep(0.1)
        page.keyboard.press("Enter")
        random_sleep(0.5, 1.0)
    except:
        print(f"Dropdown list for {label_text} did not appear or select correctly.")

# --- MANUAL STEALTH FUNCTION (Replaces the broken library) ---
def apply_stealth(page):
    """
    Manually injects JavaScript to hide automation signals.
    This bypasses the need for the 'playwright-stealth' library.
    """
    # 1. Mask the 'navigator.webdriver' flag (Key detection signal)
    page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    # 2. Mock the 'window.chrome' object (Missing in headless/automation)
    page.add_init_script("window.chrome = { runtime: {} };")
    
    # 3. Mock 'navigator.languages' to look like a real browser (French locale for this site)
    page.add_init_script("Object.defineProperty(navigator, 'languages', {get: () => ['fr-FR', 'fr', 'en-US', 'en']})")
    
    # 4. Mock 'navigator.plugins' (Automation often has 0 plugins)
    page.add_init_script("""
        Object.defineProperty(navigator, 'plugins', {
            get: () => [1, 2, 3, 4, 5]
        });
    """)
    
    # 5. Mock 'navigator.permissions' (Often checked by WAFs)
    page.add_init_script("""
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) => (
            parameters.name === 'notifications' ?
            Promise.resolve({ state: 'denied' }) :
            originalQuery(parameters)
        );
    """)

# --- MAIN EXECUTION ---
def run():
    with sync_playwright() as p:
        print("--- Launching Browser (Stealth Mode) ---")
        
        # Launch persistent context
        # This saves cookies/cache to a folder, making you look like a returning user
        context = p.chromium.launch_persistent_context(
            user_data_dir=USER_DATA_DIR,
            channel="chrome",  # Uses your REAL Google Chrome
            headless=False,    # Keep False for maximum stealth
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-infobars",
                "--start-maximized",
                "--disable-dev-shm-usage",
                "--disable-extensions",
            ],
            viewport=None
        )
        
        page = context.pages[0]
        
        # APPLY THE MANUAL STEALTH FIX
        apply_stealth(page)

        print("--- Navigating to Site ---")
        page.goto("https://direct.rmaassurance.com/souscrire")
        page.wait_for_load_state("networkidle")

        # ---------------------------------------------------------
        # STEP 1: UI Interaction
        # ---------------------------------------------------------
        print("--- Clicking First 'Suivant' ---")
        
        # Check if button exists (might be logged in or already past step 1)
        if page.locator("button", has_text="Suivant").count() > 0:
            try:
                page.locator("button", has_text="Suivant").first.click()
            except:
                pass

        print("--- Waiting for Form ---")
        try:
            page.wait_for_selector('input[name="subscriber.lastName"]', timeout=10000)
        except:
            print("Form not found. You might be blocked or on a different step.")

        print("--- Filling Form (Human Style) ---")
        
        # 1. Personal Information
        human_type(page, 'input[name="subscriber.lastName"]', "Huzaifa")
        human_type(page, 'input[name="subscriber.firstName"]', "Saeed")
        
        select_mui_dropdown_human(page, "Ville", "CASABLANCA") 
        
        human_type(page, 'input[name="subscriber.phone"]', "0666666666")
        
        # Dates (Digits only)
        human_type(page, '//label[contains(text(), "Date de naissance")]/following-sibling::div//input', "01011991")
        human_type(page, '//label[contains(text(), "Date d’obtention de permis")]/following-sibling::div//input', "01012012")

        # 2. Vehicle Information
        select_mui_dropdown_human(page, "Type de plaque", "Plaque standard") 
        human_type(page, 'input[name="vehicleInformations.plateNumber"]', "0000-F-00")
        select_mui_dropdown_human(page, "Puissance fiscale", "6")
        select_mui_dropdown_human(page, "Combustible", "DIESEL")
        
        human_type(page, '//label[contains(text(), "Date de mise en circulation")]/following-sibling::div//input', "01012023")
        
        human_type(page, 'input[name="vehicleInformations.newPrice"]', "400000")
        human_type(page, 'input[name="vehicleInformations.marketPrice"]', "300000")
        # human_type(page, 'input[name="vehicleInformations.placesNumber"]', "5")

        # ---------------------------------------------------------
        # STEP 2: Submit and Intercept
        # ---------------------------------------------------------
        print("--- Submitting Form ---")
        target_url = "https://direct.rmaassurance.com/canaldirect/offer/api/offers"

        submit_btn = page.locator("button", has_text="Suivant").last
        submit_btn.scroll_into_view_if_needed()
        random_sleep(1, 2)

        try:
            # Wait specifically for the POST request to the API
            with page.expect_response(lambda response: target_url in response.url and response.request.method == "POST", timeout=20000) as response_info:
                submit_btn.click()
                
            api_response = response_info.value
            
            print("\n" + "="*50)
            print(f"STATUS CODE: {api_response.status}")
            print("="*50)
            
            try:
                print("RESPONSE BODY (JSON):")
                print(json.dumps(api_response.json(), indent=4))
            except:
                print("RESPONSE BODY (TEXT):")
                print(api_response.text())
            print("="*50)

        except Exception as e:
            print(f"Submission failed or timed out: {e}")
            page.screenshot(path="debug_error.png")

        # Keeping browser open for debugging
        time.sleep(5)

if __name__ == "__main__":
    run()