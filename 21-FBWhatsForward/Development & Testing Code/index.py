import json
import time
import datetime
import copy
import requests
import uuid
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
import os
import sys
import platform
import logging
import random

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_script_directory():
    """Gets the directory where the script (or executable) is located."""
    if getattr(sys, 'frozen', False):
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
    logging.info(f"Success to send Text Message, resp: {response.text.encode('utf8')}")

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
    logging.info(f"Success to send url Message, resp: {response.text.encode('utf8')}")
    
def create_driver(chromeOptions):
    """Create a WebDriver instance with proper error handling."""
    try:
        # Initialize the driver without using Service object (simpler approach)
        driver = webdriver.Chrome(options=chromeOptions)
        return driver
    except Exception as e:
        logging.error(f"Error creating WebDriver: {e}")
        return None

def force_navigate(driver, url, max_attempts=3):
    """Force navigation to a URL with multiple attempts and JavaScript."""
    for attempt in range(1, max_attempts + 1):
        try:
            logging.info(f"Navigation attempt {attempt}/{max_attempts} to {url}")
            
            # First, try regular navigation
            driver.get(url)
            time.sleep(5)  # Give time to start loading
            
            current_url = driver.current_url
            logging.info(f"Current URL after get(): {current_url}")
            
            # If we're still on the new tab page or about:blank, try JavaScript navigation
            if "chrome://" in current_url or "about:blank" in current_url:
                logging.info(f"Still on {current_url}, trying JavaScript navigation")
                driver.execute_script(f"window.location.href = '{url}';")
                time.sleep(5)
                
                current_url = driver.current_url
                logging.info(f"Current URL after JavaScript navigation: {current_url}")
                
                # If still not on the target URL, try with window.open
                if "chrome://" in current_url or "about:blank" in current_url:
                    logging.info("Trying window.open approach")
                    driver.execute_script(f"window.open('{url}', '_self');")
                    time.sleep(5)
            
            # Check if we've navigated away from chrome:// URLs
            current_url = driver.current_url
            if not current_url.startswith("chrome://") and not current_url.startswith("about:blank"):
                logging.info(f"Successfully navigated to: {current_url}")
                return True
            
            logging.warning(f"Navigation attempt {attempt} failed. Current URL: {current_url}")
            
        except Exception as e:
            logging.error(f"Error during navigation attempt {attempt}: {e}")
        
        # Wait before retrying
        time.sleep(2)
    
    return False

def scrape_facebook_posts(profile_url, chromeOptions):
    driver = None
    
    try:
        # Create driver
        driver = create_driver(chromeOptions)
        if not driver:
            logging.error("Failed to create WebDriver instance")
            return {}
        
        # Set page load timeout - not too short
        driver.set_page_load_timeout(60)
        
        # Force navigation to the URL with multiple attempts
        navigation_success = force_navigate(driver, profile_url)
        
        if not navigation_success:
            logging.error(f"Failed to navigate to {profile_url} after multiple attempts")
            return {}
        
        # Wait for the content to load
        time.sleep(10)
        
        logging.info(f"Current page title: {driver.title}")
        
        # Take a screenshot for debugging
        screenshot_path = os.path.join(get_script_directory(), "facebook_page.png")
        driver.save_screenshot(screenshot_path)
        logging.info(f"Screenshot saved to: {screenshot_path}")
        
        # Try different CSS selectors - Facebook mobile might have changed UI
        # Common selectors for posts on Facebook mobile
        possible_selectors = [
            "#screen-root > div > div.m.vscroller > div[data-tracking-duration-id]",
            "div[data-tracking-duration-id]",
            "div[data-video-id]",
            "div[data-gt]",  # Generic Facebook post container
            "article",       # Facebook posts often use article tags
            "div[role='article']",  # Common role for posts
            "div.story_body_container"  # Another common Facebook post container
        ]
        
        found_elements = False
        durationElements = []
        
        for selector in possible_selectors:
            try:
                logging.info(f"Trying selector: {selector}")
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    logging.info(f"Found {len(elements)} elements with selector: {selector}")
                    durationElements = elements
                    found_elements = True
                    break
            except Exception as e:
                logging.warning(f"Error with selector {selector}: {e}")
        
        if not found_elements:
            logging.warning("Could not find posts with any of the known selectors")
            # Find all visible text for debugging
            try:
                body_text = driver.find_element(By.TAG_NAME, "body").text
                logging.info(f"Page body text (first 500 chars): {body_text[:500]}...")
            except Exception as e:
                logging.error(f"Could not get body text: {e}")
            return {}
        
        allTheData = {}
        
        for idx, element in enumerate(durationElements[:5]):  # Limit to first 5 posts for efficiency
            try:
                # Get a unique ID - either from data attribute or just use index
                post_id = element.get_attribute("data-tracking-duration-id") or str(idx + 1)
                
                # Extract text content
                post_text = element.text
                header = "N/A"
                description = "N/A"
                
                # Try to split into header and description if text is long enough
                if post_text:
                    lines = post_text.split('\n')
                    if len(lines) > 1:
                        header = lines[0]
                        description = '\n'.join(lines[1:])
                    else:
                        description = post_text
                
                # Look for images
                image_src = "N/A"
                try:
                    images = element.find_elements(By.TAG_NAME, "img")
                    for img in images:
                        src = img.get_attribute("src")
                        if src and not src.endswith(".svg") and "emoji" not in src.lower():
                            image_src = src
                            break
                except Exception as img_err:
                    logging.warning(f"Error finding images: {img_err}")
                
                # UPDATED VIDEO URL EXTRACTION
                video_url = "N/A"
                try:
                    # First approach: Find direct data-video-id attribute on any element
                    video_elements = element.find_elements(By.CSS_SELECTOR, '[data-video-id]')
                    if video_elements:
                        video_id = video_elements[0].get_attribute("data-video-id")
                        if video_id:
                            # Construct a permanent video URL
                            video_url = f"https://web.facebook.com/reel/{video_id}"
                            logging.info(f"Found video with ID: {video_id}, created URL: {video_url}")
                    
                    # Second approach: Look for the specific structure shown in the screenshot
                    if video_url == "N/A":
                        data_video_elements = element.find_elements(By.CSS_SELECTOR, '[data-video-id]')
                        for vid_element in data_video_elements:
                            video_id = vid_element.get_attribute("data-video-id")
                            if video_id:
                                video_url = f"https://web.facebook.com/reel/{video_id}"
                                logging.info(f"Found video ID in specific element: {video_id}")
                                break
                    
                    # Third approach: Check for video player elements and traverse up to find video ID
                    if video_url == "N/A":
                        video_players = element.find_elements(By.CSS_SELECTOR, '[aria-label="Video player"]')
                        if not video_players:
                            # Try different selectors that might indicate a video
                            video_players = element.find_elements(By.CSS_SELECTOR, '.x1lliihq')
                        
                        if video_players:
                            # Try to find parent elements that might contain the video ID
                            for player in video_players:
                                # Try to get the parent element with data-video-id
                                try:
                                    parent = player
                                    for _ in range(5):  # Check up to 5 levels up
                                        if parent:
                                            # Try different attributes that might contain video ID
                                            for attr in ["data-video-id", "data-videoid", "id"]:
                                                vid_id = parent.get_attribute(attr)
                                                if vid_id and vid_id.isdigit() and len(vid_id) > 8:
                                                    video_url = f"https://web.facebook.com/reel/{vid_id}"
                                                    logging.info(f"Found video ID in parent: {vid_id}")
                                                    break
                                            
                                            if video_url != "N/A":
                                                break
                                                
                                            # Get parent element
                                            parent = parent.find_element(By.XPATH, "..")
                                        else:
                                            break
                                        
                                    if video_url != "N/A":
                                        break
                                except Exception as parent_err:
                                    logging.warning(f"Error traversing parents: {parent_err}")
                    
                    # Fourth approach: Look for any element with 'data-video-' prefixed attributes
                    if video_url == "N/A":
                        # Use JavaScript to find elements with data-video attributes
                        script = """
                        return Array.from(document.querySelectorAll('*')).filter(el => {
                            for (let attr of el.attributes) {
                                if (attr.name.startsWith('data-video-')) return true;
                            }
                            return false;
                        }).map(el => {
                            let attrs = {};
                            for (let attr of el.attributes) {
                                if (attr.name.startsWith('data-video-')) {
                                    attrs[attr.name] = attr.value;
                                }
                            }
                            return attrs;
                        });
                        """
                        try:
                            video_attrs = driver.execute_script(script)
                            if video_attrs and len(video_attrs) > 0:
                                for attrs in video_attrs:
                                    if 'data-video-id' in attrs:
                                        vid_id = attrs['data-video-id']
                                        if vid_id and vid_id.isdigit() and len(vid_id) > 8:
                                            video_url = f"https://web.facebook.com/reel/{vid_id}"
                                            logging.info(f"Found video ID using JS: {vid_id}")
                                            break
                        except Exception as js_err:
                            logging.warning(f"Error executing JavaScript: {js_err}")
                    
                    # Fifth approach: Check the source code for video IDs
                    if video_url == "N/A":
                        try:
                            html_source = element.get_attribute('outerHTML')
                            # Look for patterns like data-video-id="12345678901234"
                            import re
                            video_id_matches = re.findall(r'data-video-id=["\'](\d+)["\']', html_source)
                            if video_id_matches:
                                video_id = video_id_matches[0]
                                video_url = f"https://web.facebook.com/reel/{video_id}"
                                logging.info(f"Found video ID using regex: {video_id}")
                        except Exception as src_err:
                            logging.warning(f"Error checking source: {src_err}")
                    
                    # Final fallback: original method but avoid blob URLs
                    if video_url == "N/A":
                        videos = element.find_elements(By.TAG_NAME, "video")
                        if videos:
                            src = videos[0].get_attribute("src") or "N/A"
                            if src != "N/A" and not src.startswith("blob:"):
                                video_url = src
                                logging.info(f"Using direct video source: {src}")
                
                except Exception as vid_err:
                    logging.warning(f"Error finding videos: {vid_err}")
                
                # Store the data
                allTheData[post_id] = {
                    "header": header,
                    "description": description,
                    "data_video_url": video_url,
                    "image_src": image_src
                }
                
            except Exception as e:
                logging.warning(f"Error processing post {idx}: {e}")
        
        if allTheData:
            logging.info(f"Successfully scraped {len(allTheData)} posts")
        else:
            logging.warning("No posts could be extracted")
            
        return allTheData

    except TimeoutException as e:
        logging.error(f"Timeout during Facebook scraping: {e}")
        return {}
    except WebDriverException as e:
        logging.error(f"WebDriver error during Facebook scraping: {e}")
        return {}
    except Exception as e:
        logging.error(f"Unexpected error during Facebook scraping: {e}")
        return {}
    finally:
        if driver:
            try:
                driver.quit()
                logging.info("Browser closed successfully")
            except Exception as e:
                logging.error(f"Error closing browser: {e}")
def _clean_url(url_str):
    """ Extract the base URL part before any query parameters. """
    if url_str == 'N/A':
        return url_str
    return url_str.split('?')[0]

def has_diff(prev_post, current_post):
    """ Check for differences, ignoring query parameters in URLs. """
    if not prev_post or not current_post:
        return False
        
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
    headless_str = config.get("headless", "False")  # Default to non-headless for troubleshooting
    headless = headless_str.lower() == "true"  # Convert to boolean
    
    chromeOptions = Options()
    #6282137125683
    # Essential options for avoiding detection
    chromeOptions.add_argument("--disable-blink-features=AutomationControlled")
    chromeOptions.add_experimental_option("excludeSwitches", ["enable-automation"])
    chromeOptions.add_experimental_option("useAutomationExtension", False)

    # Additional stealth options
    chromeOptions.add_argument("--disable-gpu")
    chromeOptions.add_argument("--no-sandbox")
    chromeOptions.add_argument("--disable-setuid-sandbox")
    chromeOptions.add_argument("--disable-dev-shm-usage")
    chromeOptions.add_argument("--disable-accelerated-2d-canvas")
    chromeOptions.add_argument("--disable-gpu-sandbox")
    chromeOptions.add_argument("--disable-features=IsolateOrigins,site-per-process")

    # Try without user data directory first
    # If you need to use it, uncomment these lines:
    # if user_data_dir:
    #     chromeOptions.add_argument(f"user-data-dir={user_data_dir}")
    # if profile_directory:
    #     chromeOptions.add_argument(f"profile-directory={profile_directory}")

    # Use a real browser user agent
    chromeOptions.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

    # Disable automation flags
    chromeOptions.add_experimental_option("prefs", {
        "credentials_enable_service": False,
        "profile.password_manager_enabled": False,
        "profile.default_content_setting_values.notifications": 2,
        "excludeSwitches": ["enable-logging"],
        "useAutomationExtension": False,
    })

    # Add these to avoid detection
    chromeOptions.add_argument("--disable-logging")
    chromeOptions.add_argument("--disable-gpu-sandbox")
    chromeOptions.add_argument("--disable-software-rasterizer")
    chromeOptions.add_argument("--disable-background-timer-throttling")
    chromeOptions.add_argument("--disable-backgrounding-occluded-windows")
    chromeOptions.add_argument("--disable-renderer-backgrounding")
    chromeOptions.add_argument("--disable-features=TranslateUI")
    chromeOptions.add_argument("--disable-ipc-flooding-protection")
    delay = config.get("delay-in-second")
    if delay:
        try:
            delay_seconds = int(delay)
            logging.info(f"Using delay: {delay_seconds}s")
        except ValueError:
            delay_seconds = 300
            logging.warning(f"Invalid delay value: {delay}. Using default: {delay_seconds}s")
    else:
        delay_seconds = 300
        
    profile_link = config.get("profile_link")
    if profile_link:
        logging.info(f"Target Profile: {profile_link}")
    else:
        logging.error("No profile_link specified in config.txt. Exiting.")
        sys.exit(1)
        
    recipient_number = config.get("recipient_number")
    if recipient_number:
        logging.info(f"Recipient Number: {recipient_number}")
    else:
        logging.warning("No recipient_number specified in config.txt.")
        
    instance = config.get("instance")
    if instance:
        logging.info(f"Instance: {instance}")
    else:
        logging.error("No instance specified in config.txt. Exiting.")
        sys.exit(1)
    
    api = config.get("api")
    if api:
        logging.info(f"API: {api}")
    else:
        logging.error("No API key specified in config.txt. Exiting.")
        sys.exit(1)
    
    previous_post = None
    
    sendmsg(recipient_number, "BOT STARTED WITH ENHANCED NAVIGATION", instance, api)
    
    retry_count = 0
    max_retries = 5
    
    while True:
        try:
            data = scrape_facebook_posts(profile_link, chromeOptions)
            
            if not data:
                retry_count += 1
                logging.warning(f"No data retrieved. Retry {retry_count}/{max_retries}")
                
                if retry_count >= max_retries:
                    logging.error(f"Failed to retrieve data after {max_retries} attempts. Resetting retry counter and continuing...")
                    retry_count = 0
                    sendmsg(recipient_number, "Warning: Unable to retrieve post data after multiple attempts. Bot is still running.", instance, api)
                
                # Use a shorter timeout for retries
                time.sleep(30)
                continue
            
            # If we got data, reset retry counter
            retry_count = 0
            logging.info(f"Retrieved data: {data}")

            # Get the first post (or any post, for simplicity)
            post_ids = list(data.keys())
            if not post_ids:
                logging.warning("No post IDs found in data")
                continue
                
            current_first_id = post_ids[0]
            current_first = data.get(current_first_id, {})
            
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

        except KeyboardInterrupt:
            logging.info("Script interrupted by user. Shutting down...")
            sendmsg(recipient_number, "BOT STOPPED BY USER", instance, api)
            sys.exit(0)
        except Exception as e:
            logging.critical(f"Error encountered: {e}")
            sendmsg(recipient_number, f"Error encountered: {str(e)[:100]}... Bot is still running.", instance, api)

        # Use the configured delay between main loop iterations
        time.sleep(delay_seconds)