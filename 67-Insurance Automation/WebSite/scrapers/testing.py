# import time
# import random
# import json
# import os
# from selenium import webdriver
# from selenium.webdriver.chrome.service import Service
# from selenium.webdriver.chrome.options import Options
# from selenium.webdriver.common.by import By
# from selenium.webdriver.common.keys import Keys
# from selenium.webdriver.common.action_chains import ActionChains
# from selenium.webdriver.support.ui import WebDriverWait
# from selenium.webdriver.support import expected_conditions as EC
# from webdriver_manager.chrome import ChromeDriverManager

# # --- CONFIGURATION ---
# # We use a standard path. No need to delete this constantly like the other library.
# PROFILE_PATH = os.path.abspath("./stable_chrome_profile")

# # --- HELPER FUNCTIONS ---
# def random_sleep(min_seconds=0.5, max_seconds=1.5):
#     time.sleep(random.uniform(min_seconds, max_seconds))

# def human_click(driver, element):
#     """Moves mouse to element, hovers, then clicks."""
#     try:
#         actions = ActionChains(driver)
#         actions.move_to_element(element).pause(random.uniform(0.1, 0.3)).click().perform()
#     except:
#         # Fallback to JS click if hover fails
#         driver.execute_script("arguments[0].click();", element)

# def human_type(driver, element, text):
#     """Types with random delays."""
#     try:
#         element.click()
#         time.sleep(0.2)
#         for char in text:
#             element.send_keys(char)
#             time.sleep(random.uniform(0.03, 0.1)) # Fast but human
#         random_sleep(0.3, 0.7)
#     except:
#         pass

# def select_mui_dropdown(driver, label_text, value):
#     """Robust dropdown selector."""
#     print(f"Selecting {label_text}...")
#     try:
#         # Find input by label
#         xpath = f"//label[contains(text(), '{label_text}')]/following-sibling::div//input"
#         inp = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, xpath)))
        
#         human_type(driver, inp, value)
        
#         # Wait for popup list
#         WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.CSS_SELECTOR, "ul[role='listbox']")))
#         time.sleep(0.3)
#         inp.send_keys(Keys.ARROW_DOWN)
#         time.sleep(0.1)
#         inp.send_keys(Keys.ENTER)
#         time.sleep(0.5)
#     except Exception as e:
#         print(f"Warning: Could not select {label_text}: {e}")

# def setup_driver():
#     """
#     Sets up a Standard Selenium driver with Stealth Configs.
#     This is the Long-Term Support (LTS) way.
#     """
#     options = Options()
    
#     # 1. STEALTH ARGUMENTS (The robust way)
#     # This hides the "Chrome is being controlled by automated test software" bar
#     options.add_argument("--disable-blink-features=AutomationControlled") 
#     options.add_experimental_option("excludeSwitches", ["enable-automation"])
#     options.add_experimental_option("useAutomationExtension", False)
    
#     # 2. STANDARD SETTINGS
#     options.add_argument("--start-maximized")
#     options.add_argument("--disable-popup-blocking")
#     options.add_argument(f"user-data-dir={PROFILE_PATH}")
    
#     # 3. HEADLESS NEW (Uncomment when ready)
#     # options.add_argument("--headless=new") 

#     # 4. Auto-install the CORRECT driver version
#     service = Service(ChromeDriverManager().install())
    
#     driver = webdriver.Chrome(service=service, options=options)
    
#     # 5. EXECUTE CDP STEALTH COMMAND
#     # This manually removes the 'navigator.webdriver' flag via protocol
#     driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
#         "source": """
#             Object.defineProperty(navigator, 'webdriver', {
#                 get: () => undefined
#             })
#         """
#     })
    
#     return driver

# def inject_interceptor(driver):
#     """Injects JS to capture API responses."""
#     js_script = """
#     window.capturedApiData = null;
#     const originalFetch = window.fetch;
#     window.fetch = async (...args) => {
#         const response = await originalFetch(...args);
#         if (args[0] && args[0].toString().includes('/offer/api/offers')) {
#             const clone = response.clone();
#             clone.json().then(data => window.capturedApiData = data)
#                  .catch(err => console.log(err));
#         }
#         return response;
#     };
#     """
#     driver.execute_script(js_script)

# # --- MAIN EXECUTION ---
# def run():
#     # Setup Driver (Safe Mode)
#     driver = setup_driver()
    
#     try:
#         print("--- Navigating ---")
#         driver.get("https://direct.rmaassurance.com/souscrire")
#         inject_interceptor(driver)

#         # Wait for load
#         wait = WebDriverWait(driver, 15)
        
#         # --- Handle Cookie Banner ---
#         try:
#             cookie = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Accepter')]")))
#             cookie.click()
#             print("Cookies accepted.")
#             time.sleep(1)
#         except:
#             print("No cookie banner.")

#         # --- Step 1: Click First Button ---
#         print("--- Clicking First 'Suivant' ---")
#         try:
#             btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[normalize-space()='Suivant']")))
#             human_click(driver, btn)
#         except:
#             print("Could not find first button (maybe already on form).")

#         # --- Step 2: Fill Form ---
#         print("--- Filling Form ---")
#         wait.until(EC.presence_of_element_located((By.NAME, "subscriber.lastName")))
        
#         human_type(driver, driver.find_element(By.NAME, "subscriber.lastName"), "Huzaifa")
#         human_type(driver, driver.find_element(By.NAME, "subscriber.firstName"), "Saeed")
#         select_mui_dropdown(driver, "Ville", "CASABLANCA")
#         human_type(driver, driver.find_element(By.NAME, "subscriber.phone"), "0666666666")
        
#         # Dates (XPath helper)
#         def type_date(label, val):
#             el = driver.find_element(By.XPATH, f"//label[contains(text(), '{label}')]/following-sibling::div//input")
#             human_type(driver, el, val)
            
#         type_date("Date de naissance", "01011991")
#         type_date("Date d’obtention de permis", "01012012")

#         # Scroll
#         driver.execute_script("window.scrollBy(0, 500);")
#         time.sleep(1)

#         select_mui_dropdown(driver, "Type de plaque", "Plaque standard")
#         human_type(driver, driver.find_element(By.NAME, "vehicleInformations.plateNumber"), "0000-F-00")
#         select_mui_dropdown(driver, "Puissance fiscale", "6")
#         select_mui_dropdown(driver, "Combustible", "DIESEL")
#         type_date("Date de mise en circulation", "01012023")
#         human_type(driver, driver.find_element(By.NAME, "vehicleInformations.newPrice"), "400000")
#         human_type(driver, driver.find_element(By.NAME, "vehicleInformations.marketPrice"), "300000")

#         # --- Step 3: Submit ---
#         print("--- Submitting ---")
#         # Find the visible Suivant button at the bottom
#         all_btns = driver.find_elements(By.XPATH, "//button[normalize-space()='Suivant']")
#         if all_btns:
#             submit_btn = all_btns[-1]
#             driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", submit_btn)
#             time.sleep(1)
#             human_click(driver, submit_btn)
        
#         # --- Step 4: Capture Data ---
#         print("--- Waiting for Data ---")
#         captured_data = None
#         for _ in range(20):
#             captured_data = driver.execute_script("return window.capturedApiData;")
#             if captured_data: break
#             time.sleep(1)

#         print("\n" + "="*40)
#         if captured_data:
#             print("SUCCESS! JSON CAPTURED:")
#             print(json.dumps(captured_data, indent=4))
#         else:
#             print("No JSON captured. Check if form submitted correctly.")
#         print("="*40)

#     except Exception as e:
#         print(f"Error: {e}")
#         driver.save_screenshot("error_debug.png")
#     finally:
#         print("Closing browser...")
#         time.sleep(3)
#         driver.quit()

# if __name__ == "__main__":
#     run()



import time
import random
import json
import os
import zlib
# Use seleniumwire's webdriver instead of the standard one
from seleniumwire import webdriver 
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# --- HELPER FUNCTIONS ---
def random_sleep(min_seconds=0.5, max_seconds=1.5):
    time.sleep(random.uniform(min_seconds, max_seconds))

def human_click(driver, element):
    try:
        actions = ActionChains(driver)
        actions.move_to_element(element).pause(random.uniform(0.1, 0.3)).click().perform()
    except:
        driver.execute_script("arguments[0].click();", element)

def human_type(driver, element, text):
    try:
        element.click()
        time.sleep(0.2)
        for char in text:
            element.send_keys(char)
            time.sleep(random.uniform(0.03, 0.1))
        random_sleep(0.3, 0.7)
    except:
        pass

def select_mui_dropdown(driver, label_text, value):
    """Robust dropdown selector."""
    print(f"Selecting {label_text}...")
    try:
        xpath = f"//label[contains(text(), '{label_text}')]/following-sibling::div//input"
        inp = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, xpath)))
        
        human_type(driver, inp, value)
        
        WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.CSS_SELECTOR, "ul[role='listbox']")))
        time.sleep(0.3)
        inp.send_keys(Keys.ARROW_DOWN)
        time.sleep(0.1)
        inp.send_keys(Keys.ENTER)
        time.sleep(0.5)
    except Exception as e:
        print(f"Warning: Could not select {label_text}: {e}")

# --- SETUP DRIVER WITH SELENIUM WIRE ---
def setup_driver():
    # Selenium Wire options
    seleniumwire_options = {
        'disable_encoding': True,  # Ask server not to compress data (makes reading JSON easier)
        'verify_ssl': False        # Prevent SSL errors
    }

    options = webdriver.ChromeOptions()
    
    # STEALTH ARGUMENTS
    options.add_argument("--disable-blink-features=AutomationControlled") 
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    
    options.add_argument("--start-maximized")
    options.add_argument("--disable-popup-blocking")
    
    # HEADLESS MODE (Optional: Uncomment to run invisible)
    options.add_argument("--headless=new") 

    # Install correct driver automatically
    service = Service(ChromeDriverManager().install())
    
    # Initialize Selenium Wire Driver
    driver = webdriver.Chrome(
        service=service, 
        options=options,
        seleniumwire_options=seleniumwire_options
    )
    
    return driver

# --- MAIN EXECUTION ---
def run():
    driver = setup_driver()
    
    try:
        print("--- Navigating ---")
        driver.get("https://direct.rmaassurance.com/souscrire")
        
        # Wait for load
        wait = WebDriverWait(driver, 15)
        
        # --- Handle Cookie Banner ---
        try:
            cookie = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Accepter')]")))
            cookie.click()
            print("Cookies accepted.")
            time.sleep(1)
        except:
            print("No cookie banner.")

        # --- Step 1: Click First Button ---
        print("--- Clicking First 'Suivant' ---")
        try:
            btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[normalize-space()='Suivant']")))
            human_click(driver, btn)
        except:
            print("Already on form or button missed.")

        # --- Step 2: Fill Form ---
        print("--- Filling Form ---")
        wait.until(EC.presence_of_element_located((By.NAME, "subscriber.lastName")))
        time.sleep(2)
        human_type(driver, driver.find_element(By.NAME, "subscriber.lastName"), "Huzaifa")
        human_type(driver, driver.find_element(By.NAME, "subscriber.firstName"), "Saeed")
        select_mui_dropdown(driver, "Ville", "CASABLANCA")
        human_type(driver, driver.find_element(By.NAME, "subscriber.phone"), "0666666666")
        
        # Dates
        def type_date(label, val):
            el = driver.find_element(By.XPATH, f"//label[contains(text(), '{label}')]/following-sibling::div//input")
            human_type(driver, el, val)
            
        type_date("Date de naissance", "01011991")
        type_date("Date d’obtention de permis", "01012012")

        driver.execute_script("window.scrollBy(0, 500);")
        time.sleep(1)

        select_mui_dropdown(driver, "Type de plaque", "Plaque standard")
        human_type(driver, driver.find_element(By.NAME, "vehicleInformations.plateNumber"), "0000-F-00")
        select_mui_dropdown(driver, "Puissance fiscale", "6")
        select_mui_dropdown(driver, "Combustible", "DIESEL")
        type_date("Date de mise en circulation", "01012023")
        human_type(driver, driver.find_element(By.NAME, "vehicleInformations.newPrice"), "400000")
        human_type(driver, driver.find_element(By.NAME, "vehicleInformations.marketPrice"), "300000")

        # --- Clear previous requests to ensure we catch the NEW one ---
        del driver.requests

        # --- Step 3: Submit ---
        print("--- Submitting ---")
        all_btns = driver.find_elements(By.XPATH, "//button[normalize-space()='Suivant']")
        if all_btns:
            submit_btn = all_btns[-1]
            driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", submit_btn)
            time.sleep(1)
            human_click(driver, submit_btn)
        
        # --- Step 4: Capture Data via Selenium Wire ---
        print("--- Waiting for Network Traffic ---")
        
        # Look for the specific API URL
        api_substring = "/offer/api/offers"
        captured_json = None

        # Wait up to 30 seconds for the request to appear in the background
        try:
            print("Listening for API...")
            time.sleep(10)
            request = driver.wait_for_request(api_substring, timeout=30)
            print(f"API Request Detected: {request.url}")
            
            if request.response:
                # print(request.response.text)
                # Decode the body (Selenium Wire handles gzip automatically mostly, but we ensure utf-8)
                body = request.response.body.decode('utf-8')
                print(body)
                captured_json = json.loads(body)
            else:
                print("Request found, but no response received yet.")
                
        except Exception as e:
            print(f"Time out or error waiting for request: {e}")
            # Fallback: Scan all requests just in case the wait missed it
            for req in driver.requests:
                if api_substring in req.url and req.response:
                    body = req.response.body.decode('utf-8')
                    captured_json = json.loads(body)
                    break

        print("\n" + "="*40)
        if captured_json:
            print("SUCCESS! DATA CAPTURED:")
            print(json.dumps(captured_json, indent=4))
            
            # Save to file
            with open("insurance_data.json", "w", encoding="utf-8") as f:
                json.dump(captured_json, f, indent=4)
            print("Saved to insurance_data.json")
        else:
            print("Failed to capture specific JSON.")
        print("="*40)

    except Exception as e:
        print(f"Critical Error: {e}")
        driver.save_screenshot("error_wire.png")
    finally:
        print("Closing...")
        time.sleep(3)
        driver.quit()

if __name__ == "__main__":
    run()