import time
import random
import json
from playwright.sync_api import sync_playwright

# --- HELPER FUNCTIONS ---

def random_sleep(min_ms=500, max_ms=1500):
    """Sleeps for a random amount of milliseconds."""
    time.sleep(random.uniform(min_ms, max_ms) / 1000)

def fill_mui_dropdown(page, label_text, value):
    """Handles MUI dropdowns using standard Playwright locators."""
    print(f"Selecting {label_text}: {value}...")
    try:
        # Using a more robust selector for MUI Autocomplete
        dropdown_input = page.locator(f"div.direct-MuiAutocomplete-root:has(label:has-text('{label_text}')) input")
        dropdown_input.wait_for(state="visible", timeout=10000)
        
        dropdown_input.click()
        random_sleep(300, 600)
        dropdown_input.fill(value)
        
        # Wait for the dropdown options listbox
        page.wait_for_selector("ul[role='listbox']", timeout=5000)
        random_sleep(500, 800)

        page.keyboard.press("ArrowDown")
        page.keyboard.press("Enter")
        random_sleep(800, 1200)
    except Exception as e:
        print(f"Warning: Could not select {label_text}: {e}")

def run():
    with sync_playwright() as p:
        # --- BROWSER CONFIGURATION ---
        # Using Firefox as it's generally more stable for this specific site's MUI
        browser = p.firefox.launch(headless=True) 
        
        # Adding a realistic User Agent and Locale for anti-detection
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
            locale="fr-FR",
            viewport={'width': 1920, 'height': 1080}
        )
        
        page = context.new_page()

        try:
            print("--- Navigating to RMA Assurance ---")
            page.goto("https://direct.rmaassurance.com/souscrire", timeout=60000)
            
            # --- Handle Cookie Banner ---
            try:
                page.locator("button:has-text('Accepter')").click(timeout=5000)
                print("Cookies accepted.")
            except:
                pass

            # --- Step 1: Transition ---
            print("--- Clicking First 'Suivant' ---")
            page.locator("button:has-text('Suivant')").first.click()
            
            # Wait for form to actually load
            name_input = page.locator('input[name="subscriber.lastName"]')
            name_input.wait_for(state="visible", timeout=20000)
            random_sleep(1000, 2000)

            # --- Step 2: Fill Form ---
            print("--- Filling Form Details ---")
            
            # Personal Info
            page.locator('input[name="subscriber.lastName"]').fill("Huzaifa")
            page.locator('input[name="subscriber.firstName"]').fill("Saeed")
            
            fill_mui_dropdown(page, "Ville", "CASABLANCA")
            page.locator('input[name="subscriber.phone"]').fill("0666666666")

            # Dates via Placeholders
            page.locator('input[placeholder="JJ/MM/AAAA"]').nth(0).fill("01/01/1991")
            page.locator('input[placeholder="JJ/MM/AAAA"]').nth(1).fill("01/01/2012")

            # Scroll to Vehicle Section
            page.mouse.wheel(0, 600)
            random_sleep(1000, 1500)

            # Vehicle Info
            fill_mui_dropdown(page, "Type de plaque", "Plaque standard")
            page.locator('input[name="vehicleInformations.plateNumber"]').fill("0000-F-00")
            
            fill_mui_dropdown(page, "Puissance fiscale", "6")
            fill_mui_dropdown(page, "Combustible", "DIESEL")
            
            page.locator('input[placeholder="JJ/MM/AAAA"]').nth(2).fill("01/01/2023")
            
            # Numerical Values
            page.locator('input[name="vehicleInformations.newPrice"]').fill("400000")
            page.locator('input[name="vehicleInformations.marketPrice"]').fill("300000")
            page.locator('input[name="vehicleInformations.placesNumber"]').fill("5")

            # --- Step 3: Submit & Capture Traffic ---
            print("--- Submitting & Capturing API Traffic ---")
            
            with page.expect_response(
                lambda r: "/offer/api/offers" in r.url and r.status == 200, 
                timeout=30000
            ) as resp:
                page.locator("button:has-text('Suivant')").last.click()

            # --- Step 4: Process Results ---
            json_data = resp.value.json()
            with open("insurance_data.json", "w", encoding="utf-8") as f:
                json.dump(json_data, f, indent=4)
            
            print("\n" + "="*30)
            print("SUCCESS: Data captured and saved.")
            print("="*30)

        except Exception as e:
            print(f"Critical Error: {e}")
            page.screenshot(path="error_playwright.png")
            print("Error screenshot saved.")
            
        finally:
            random_sleep(5000, 7000)
            browser.close()

if __name__ == "__main__":
    run()