
import time
import random
import json
from camoufox.sync_api import Camoufox

# Store captured request/response data
captured_requests = []

def random_sleep(min_ms=500, max_ms=1500):
    time.sleep(random.uniform(min_ms, max_ms) / 1000)

def fill_mui_dropdown(page, label_text, value):
    """Handles MUI dropdowns by clicking the input via its label and selecting an option."""
    print(f"Selecting {label_text}: {value}...")
    try:
        # Use fuzzy text matching for the label to handle the curly ' and *
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
    except Exception as e:
        print(f"Warning: Could not select {label_text}: {e}")

def run():
    def capture_request(request):
        """Intercept and capture all requests."""
        try:
            if "/offer/api/offers" in request.url:
                request_data = {
                    "url": request.url,
                    "method": request.method,
                    "headers": dict(request.headers),
                }
                # Try to capture post data
                try:
                    if request.post_data:
                        request_data["payload"] = request.post_data
                        # Try to parse as JSON
                        try:
                            request_data["payload_parsed"] = json.loads(request.post_data)
                        except:
                            pass
                except:
                    pass
                captured_requests.append(request_data)
        except Exception as e:
            print(f"Error capturing request: {e}")
    
    with Camoufox(headless=True, humanize=True, os="windows", geoip=True) as browser:
        page = browser.new_page()
        
        # Set up request interception
        page.on("request", capture_request)

        try:
            print("--- Navigating to RMA Assurance ---")
            page.goto("https://direct.rmaassurance.com/souscrire", timeout=60000)

            # Step 1: Click 'Suivant' to reach the form in the screenshot
            print("--- Clicking First 'Suivant' ---")
            page.locator("button:has-text('Suivant')").first.click()
            
            # CRITICAL: Wait for the specific form input to be attached and visible
            # We use the 'name' attribute from your HTML as it's the most stable
            name_input = page.locator('input[name="subscriber.lastName"]')
            name_input.wait_for(state="visible", timeout=20000)
            random_sleep(1000, 2000)

            # --- Step 2: Fill Form using name attributes ---
            print("--- Filling Form Details ---")
            
            # Personal Info
            page.locator('input[name="subscriber.lastName"]').fill("Huzaifa")
            page.locator('input[name="subscriber.firstName"]').fill("Saeed")
            
            # Ville (Dropdown)
            fill_mui_dropdown(page, "Ville", "CASABLANCA")
            
            # Phone
            page.locator('input[name="subscriber.phone"]').fill("0666666666")

            # Dates - Using placeholders because the label text is tricky
            # Format: JJ/MM/AAAA or YYYY-MM-DD depending on browser locale
            page.locator('input[placeholder="JJ/MM/AAAA"]').nth(0).fill("01/01/1991")
            page.locator('input[placeholder="JJ/MM/AAAA"]').nth(1).fill("01/01/2012")

            # Vehicle Section
            page.mouse.wheel(0, 600)
            random_sleep(1000, 1500)

            fill_mui_dropdown(page, "Type de plaque", "Plaque standard")
            page.locator('input[name="vehicleInformations.plateNumber"]').fill("0000-F-00")
            
            fill_mui_dropdown(page, "Puissance fiscale", "6")
            fill_mui_dropdown(page, "Combustible", "DIESEL")
            
            # Vehicle Date
            page.locator('input[placeholder="JJ/MM/AAAA"]').nth(2).fill("01/01/2023")
            
            # Prices
            page.locator('input[name="vehicleInformations.newPrice"]').fill("400000")
            page.locator('input[name="vehicleInformations.marketPrice"]').fill("300000")
            page.locator('input[name="vehicleInformations.placesNumber"]').fill("5")

            # --- Step 3: Submit & Capture ---
            print("--- Submitting Form ---")
            with page.expect_response(lambda r: "/offer/api/offers" in r.url and r.status == 200, timeout=30000) as resp:
                page.locator("button:has-text('Suivant')").last.click()

            # --- Step 4: Save Result ---
            response_data = resp.value.json()
            
            # Combine request and response data
            output_data = {
                "captured_requests": captured_requests,
                "response": response_data
            }
            
            with open("insurance_data.json", "w", encoding="utf-8") as f:
                json.dump(output_data, f, indent=4, ensure_ascii=False)
            
            print("\n=== VERIFICATION REPORT ===")
            print(f"Total requests captured: {len(captured_requests)}")
            for i, req in enumerate(captured_requests):
                print(f"\n--- Request {i+1} ---")
                print(f"URL: {req['url']}")
                print(f"Method: {req['method']}")
                if "payload_parsed" in req:
                    print(f"Payload (parsed):")
                    print(json.dumps(req["payload_parsed"], indent=2, ensure_ascii=False))
                elif "payload" in req:
                    print(f"Payload (raw): {req['payload']}")
            print("\nSUCCESS: Data captured and saved to insurance_data.json")

        except Exception as e:
            print(f"Critical Error: {e}")
            page.screenshot(path="error_debug.png")
        finally:
            random_sleep(5000, 7000)

if __name__ == "__main__":
    run()