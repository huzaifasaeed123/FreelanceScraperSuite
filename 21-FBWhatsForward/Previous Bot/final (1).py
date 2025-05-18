import json
import time
import datetime
import copy
import requests
import uuid
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import os
import sys
import platform
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_script_directory():
    """Gets the directory where the script (or executable) is located."""
    if getattr(sys, 'frozen', False):
        # If the application is run as a bundle, the PyInstaller bootloader
        # sets the 'frozen' flag and creates the '_MEIPASS' attribute.
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.abspath(__file__))

def get_default_chrome_user_data_dir():
    """Gets the user-data-dir relative to the script's location."""
    script_dir = get_script_directory()
    return os.path.join(script_dir, "chrome_user_data")

def read_config_from_file(filepath):
    """Reads configuration parameters from a text file."""
    config = {}
    try:
        with open(filepath, 'r') as f:
            for line in f:
                line = line.strip()
                if line and '=' in line:
                    key, value = line.split('=', 1)
                    config[key.strip()] = value.strip()
    except FileNotFoundError:
        logging.warning(f"Config file not found: {filepath}. Using default settings.")
    except Exception as e:
        logging.error(f"Error reading config file: {e}")
    return config

    
def sendmsg(thenumber, msg, instance, api):
    url = f"https://7105.api.greenapi.com/waInstance{instance}/sendMessage/{api}"
    chatid = f"{thenumber}@c.us"
    payload = {
        "chatId": chatid,
        "message": msg
    }
    headers = {'Content-Type': 'application/json'}
    response = requests.post(url, json=payload, headers=headers)
    logging.info(f"Success to send Message, resp: {response.text.encode('utf8')}")

def sendmsgurl(thenumber, captions, urlfile, filename, instance, api):
    url = f"https://7105.api.greenapi.com/waInstance{instance}/sendFileByUrl/{api}"
    chatid = f"{thenumber}@c.us"
    payload = {
        "chatId": chatid,
        "urlFile": urlfile,
        "fileName": filename,
        "caption": captions
    }
    headers = {'Content-Type': 'application/json'}
    response = requests.post(url, json=payload, headers=headers)
    logging.info(f"Success to send Message, resp: {response.text.encode('utf8')}")
    
def scrape_facebook_posts(profile_url,chromeoptions):
    driver = webdriver.Chrome(options=chromeOptions)

    try:
        driver.get(profile_url)
        time.sleep(5)
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, "#screen-root > div > div.m.vscroller")))
        
        durationElements = driver.find_elements(By.CSS_SELECTOR, "#screen-root > div > div.m.vscroller > div[data-tracking-duration-id]")
        allTheData = {}

        for element in durationElements:
            durationIdValue = element.get_attribute("data-tracking-duration-id")
            
            if durationIdValue:
                selector = f"#screen-root > div > div.m.vscroller > div[data-tracking-duration-id='{durationIdValue}']"
                elements_list = driver.find_elements(By.CSS_SELECTOR, selector)
                countNumber = len(elements_list)
                has_action = any(e.get_attribute("data-action-id") for e in elements_list)

                header, description, video_url, image_src = "N/A", "N/A", "N/A", "N/A"

                try:
                    first_element = elements_list[0]
                    header = first_element.find_element(By.CSS_SELECTOR, "span.f5").text

                    if len(elements_list) > 1:
                        description = elements_list[1].text

                    if len(elements_list) > 2:
                        third_element = elements_list[2]
                        try:
                            video_div = third_element.find_element(By.CSS_SELECTOR, 'div[aria-label="Video player"]')
                            video_url = video_div.get_attribute("data-video-url") or "N/A"
                        except NoSuchElementException:
                            video_url = "N/A"

                    if len(elements_list) >= 3:
                        search_element = elements_list[1] if len(elements_list) == 3 else elements_list[2]
                        try:
                            image_element = search_element.find_element(By.CSS_SELECTOR, 'img[data-type="image"]')
                            image_src = image_element.get_attribute("src") or "N/A"
                        except NoSuchElementException:
                            image_src = "N/A"

                except (IndexError, NoSuchElementException):
                    logging.warning(f"Element structure mismatch for ID: {durationIdValue}")
                allTheData[durationIdValue] = {
                    "count": countNumber,
                    "has_action": has_action,
                    "header": header,
                    "description": description,
                    "data_video_url": video_url,
                    "image_src": image_src
                }
            else:
                logging.warning(f"Skipping element with no duration ID")
        return allTheData

    except Exception as e:
        logging.warning(f"Error: {e}")
        return {}

    finally:
        driver.quit()

def _clean_url(url_str):
    """ Extract the base URL part before any query parameters. """
    if url_str == 'N/A':
        return url_str
    return url_str.split('?')[0]

def has_diff(prev_post, current_post):
    """ Check for differences, ignoring query parameters in URLs. """
    check_fields = ['description', 'data_video_url', 'image_src']
    for key in check_fields:
        prev = prev_post.get(key, 'N/A')
        current = current_post.get(key, 'N/A')
        # Clean URLs only when comparing
        if key in ['data_video_url', 'image_src']:
            prev_clean = _clean_url(prev)
            current_clean = _clean_url(current)
            if prev_clean != current_clean:
                return True
        else:
            if prev != current:
                return True
    return False


if __name__ == '__main__':
    script_dir = get_script_directory()
    config_file_path = os.path.join(script_dir, "config.txt")
    config = read_config_from_file(config_file_path)

    # Determine user_data_dir
    default_user_data_dir = get_default_chrome_user_data_dir()
    user_data_dir = config.get("user-data-dir", default_user_data_dir)

    profile_directory = config.get("profile-directory")
    user_agent = config.get("user-agent")
    headless_str = config.get("headless", "True")
    headless = headless_str.lower() == "true"  # Convert to boolean
    
    chromeOptions = Options()
    if user_data_dir:
        logging.info(f"Using user-data-dir: {user_data_dir}")
        chromeOptions.add_argument(f"user-data-dir={user_data_dir}")

    if profile_directory:
        logging.info(f"Using profile-directory: {profile_directory}")
        chromeOptions.add_argument(f"profile-directory={profile_directory}")

    if user_agent:
        logging.info(f"Using user agent: {user_agent}")
        chromeOptions.add_argument(f"user-agent={user_agent}")

    if headless:
        logging.info("Running in headless mode")
        chromeOptions.add_argument("--headless")
        
    delay = config.get("delay-in-second")
    if delay:
        logging.info(f"Using delay: {delay}s")
        
    profile_link = config.get("profile_link")
    if profile_link:
        logging.info(f"Target Profile: {profile_link}")
        
    recipient_number = config.get("recipient_number")
    if recipient_number:
        logging.info(f"Recipient Number: {recipient_number}")
        
    instance = config.get("instance")
    if instance:
        logging.info(f"Instance: {instance}")
    
    api = config.get("api")
    if api:
        logging.info(f"API: {api}")
        
    
    previous_post = None
    
    sendmsg(recipient_number, "BOT STARTED", instance, api)
    while True:
        try:
            data = scrape_facebook_posts(profile_link, chromeOptions)
            logging.info(data)
            if not data:
                logging.warning("No data retrieved. Retrying...")
                time.sleep(10)
                continue

            current_first = data.get('1', {})
            if previous_post is None:
                previous_post = copy.deepcopy(current_first)
                logging.info(f"Baseline established at {datetime.datetime.now():%H:%M}")
                continue

            if has_diff(previous_post, current_first):
                logging.info(f"\n POST CHANGE DETECTED at {datetime.datetime.now()} \n")
                description = current_first.get('description', 'No description')
                video_url = current_first.get('data_video_url', 'N/A')
                image_url = current_first.get('image_src', 'N/A')

                if video_url != 'N/A':
                    filename = f"video_{uuid.uuid4().hex[:8]}.mp4"
                    sendmsgurl(recipient_number, description, video_url, filename, instance, api)
                elif image_url != 'N/A':
                    parts = image_url.split('/')
                    filename_part = parts[-1].split('?')[0]
                    if '.' not in filename_part:
                        filename_part += '.jpg'
                    sendmsgurl(recipient_number, description, image_url, filename_part, instance, api)
                else:
                    sendmsg(recipient_number, description, instance, api)

                previous_post = copy.deepcopy(current_first)


        except Exception as e:
            logging.critical(f"Error encountered: {e}")

        time.sleep(300)