import time
import logging
import random
from selenium.webdriver.common.action_chains import ActionChains
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def scrape_facebook_posts(driver):
    try:
        logging.info("Scraping Facebook posts")
        
        # Find all posts using the data-pagelet attribute pattern
        post_selector = "div[data-pagelet^='TimelineFeedUnit_']"
        posts = driver.find_elements(By.CSS_SELECTOR, post_selector)
        
        logging.info(f"Found {len(posts)} posts with selector: {post_selector}")
        
        # If no posts found, try alternative selectors
        if not posts:
            alternative_selectors = [
                "div[role='article']",
                "div.x1yztbdb",
                ".userContentWrapper"
            ]
            
            for selector in alternative_selectors:
                posts = driver.find_elements(By.CSS_SELECTOR, selector)
                if posts:
                    logging.info(f"Found {len(posts)} posts with alternative selector: {selector}")
                    break
        
        # Process each post
        results = []
        for idx, post in enumerate(posts):
            post_data = {"post_number": idx + 1}
            
            # Extract image data - find all img tags and clean their src URLs
            try:
                images = post.find_elements(By.TAG_NAME, "img")
                image_urls = []
                
                for img in images:
                    src = img.get_attribute("src")
                    if src:
                        # Skip SVG images and emoji images which are not content
                        if src.endswith(".svg") or "emoji" in src.lower():
                            continue
                            
                        # Skip small icons and UI elements (typically small images)
                        width = img.get_attribute("width")
                        height = img.get_attribute("height")
                        if width and height:
                            try:
                                if int(width) < 50 or int(height) < 50:
                                    continue
                            except ValueError:
                                # If width/height aren't numeric, still include the image
                                pass
                        
                        # Remove query parameters (everything after ?)
                        clean_src = src
                        
                        # Add to our list if it's not already there
                        if clean_src not in image_urls:
                            image_urls.append(clean_src)
                
                if image_urls:
                    post_data["image_urls"] = image_urls
                    logging.info(f"Found {len(image_urls)} images in post {idx + 1}")
                    # Log first image URL as example
                    if image_urls:
                        logging.info(f"First image: {image_urls[0]}")
                
            except Exception as e:
                logging.warning(f"Error extracting image data: {e}")
            # Extract post text using multiple strategies
            try:
                post_text = ""   
                # Strategy 1: Look for divs with dir="auto" and style containing text-align:start
                text_divs = post.find_elements(By.CSS_SELECTOR, "div[dir='auto'][style*='text-align: start']")
                
                if text_divs:
                    # Collect text from all matching divs
                    text_parts = []
                    for div in text_divs:
                        div_text = div.text.strip()
                        if div_text:
                            text_parts.append(div_text)
                    
                    # Join all text parts with newlines
                    post_text = "\n".join(text_parts)
                
                # Strategy 2 (fallback): Look for divs with data-ad-comet-preview="message" attribute
                if not post_text:
                    message_divs = post.find_elements(By.CSS_SELECTOR, "div[data-ad-comet-preview='message'], div[data-ad-preview='message']")
                    
                    if message_divs:
                        # Collect text from all matching divs
                        text_parts = []
                        for div in message_divs:
                            div_text = div.text.strip()
                            if div_text:
                                text_parts.append(div_text)
                        
                        # Join all text parts with newlines
                        post_text = "\n".join(text_parts)
                
                post_data["text"] = post_text
                logging.info(f"Post {idx + 1} text: {post_text[:100]}{'...' if len(post_text) > 100 else ''}")
                
            except Exception as e:
                logging.warning(f"Error getting post text: {e}")
                post_data["text"] = ""

            # NEW METHOD: Extract video links from role="link" elements
            try:
                # Find all elements with role="link" within the post
                link_elements = post.find_elements(By.CSS_SELECTOR, "[role='link']")
                video_links = []
                
                for link in link_elements:
                    href = link.get_attribute("href")
                    if href:
                        # Check if the href contains 'videos' or 'reel'
                        if 'videos' in href or 'reel' in href:
                            # Remove parameters (everything after '?')
                            clean_url = href.split('?')[0]
                            video_links.append(clean_url)
                
                if video_links:
                    # Use the first video link found
                    post_data["video_link"] = video_links[0]
                    logging.info(f"Found video link in post {idx + 1}: {video_links[0]}")
            except Exception as e:
                logging.warning(f"Error extracting video links: {e}")
            
           
            results.append(post_data)
        
        return results
        
    except Exception as e:
        logging.error(f"Error scraping posts: {e}")
        return []
def scroll_naturally(driver, scroll_distance=2100, duration=5, step_size=50, headless=True):
    """
    Perform a smooth, incremental scroll that works in both headless and normal browsers.
    
    Args:
        driver: Selenium WebDriver instance
        scroll_distance: Total pixels to scroll (default 1000)
        duration: Approximately how many seconds the scroll should take (default 5)
        step_size: Maximum pixels to scroll in each small movement (default 50)
        headless: Whether the browser is running in headless mode (default True)
        
    Returns:
        bool: True if scrolling was performed successfully, False otherwise
    """
    try:
        logging.info(f"Starting incremental scroll of ~{scroll_distance} pixels over ~{duration} seconds")
        
        # Get initial scroll position
        initial_position = driver.execute_script("return window.pageYOffset;")
        logging.info(f"Initial scroll position: {initial_position}px")
        
        # Calculate how many steps we need and the delay between steps
        steps = max(int(scroll_distance / step_size), 1)
        delay_between_steps = duration / steps
        
        # Get page height to avoid scrolling past the bottom
        page_height = driver.execute_script("return document.body.scrollHeight")
        viewport_height = driver.execute_script("return window.innerHeight")
        
        # Only do mouse movements if not in headless mode
        actions = None
        # if not headless:
        #     actions = ActionChains(driver)
        #     # Try to move mouse to middle of viewport (only in non-headless mode)
        #     try:
        #         body = driver.find_element(By.TAG_NAME, "body")
        #         viewport_width = driver.execute_script("return window.innerWidth")
        #         actions.move_to_element_with_offset(body, viewport_width // 2, viewport_height // 2)
        #         actions.perform()
        #     except Exception as e:
        #         logging.warning(f"Mouse movement failed (non-critical): {e}")
        
        # Perform the scroll in small steps
        scrolled = 0
        for i in range(steps):
            # Add some randomness to the step size
            current_step = min(
                random.randint(int(step_size * 0.7), int(step_size * 1.3)),
                scroll_distance - scrolled
            )
            
            # Make sure we won't scroll past the bottom of the page
            current_position = driver.execute_script("return window.pageYOffset;")
            remaining_page = page_height - current_position - viewport_height
            
            if remaining_page <= 0:
                logging.info("Already at the bottom of the page")
                break
                
            # Adjust step if needed
            if current_step > remaining_page:
                current_step = max(1, int(remaining_page * 0.9))  # Leave a little room
                logging.info(f"Approaching bottom, adjusted step to {current_step}px")
            
            # Execute the scroll - this works in both headless and non-headless
            driver.execute_script(f"window.scrollBy(0, {current_step});")
            
            # Move mouse slightly if not in headless mode (completely optional)
            if not headless and actions and random.random() < 0.3:
                try:
                    actions.move_by_offset(random.randint(-10, 10), random.randint(-5, 5))
                    actions.perform()
                except:
                    pass  # Ignore mouse errors
            
            scrolled += current_step
            
            # Add a randomized delay between scrolls
            time.sleep(delay_between_steps * random.uniform(0.8, 1.2))
            
            # Log progress occasionally
            if (i + 1) % 5 == 0 or i == steps - 1:
                current_position = driver.execute_script("return window.pageYOffset;")
                logging.info(f"Scrolled to position {current_position}px (step {i+1}/{steps})")
                
                # Check if new content has loaded by looking at page height
                new_page_height = driver.execute_script("return document.body.scrollHeight")
                if new_page_height > page_height:
                    logging.info(f"Page height increased from {page_height} to {new_page_height}")
                    page_height = new_page_height
        
        # Get final scroll position
        final_position = driver.execute_script("return window.pageYOffset;")
        logging.info(f"Final scroll position: {final_position}px (moved {final_position - initial_position}px)")
        
        # Wait a moment for any dynamic content to load
        time.sleep(2)
        
        return True
        
    except Exception as e:
        logging.error(f"Error during scrolling: {e}")
        return False
def dismiss_login_popup(driver,profile_url):
    """Visit Facebook profile and dismiss the login popup."""
    # driver = None
    try:
        logging.info(f"Navigating to {profile_url}")
        driver.get(profile_url)
        
        # Wait for page to load
        time.sleep(3)
        
        # Take a screenshot before looking for the popup
        driver.save_screenshot("before_closing_popup.png")
        logging.info("Saved screenshot before closing popup")
        
        # Look for the login dialog
        logging.info("Looking for login popup dialog...")
        wait = WebDriverWait(driver, 10)
        
        # First, try to find the dialog
        dialog = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div[role='dialog']")))
        logging.info("Found login dialog")
        
        # Now find the close button inside the dialog
        # There might be multiple ways the close button is structured, so we'll try a few
        close_button = None
        
        # Method 1: Look for a button directly inside the dialog
        try:
            close_button = dialog.find_element(By.CSS_SELECTOR, "div[role='button']")
            logging.info("Found close button using Method 1")
        except:
            logging.info("Method 1 failed to find close button")
        
        # Method 2: Look for a specific aria-label that might be associated with close buttons
        if not close_button:
            try:
                close_button = dialog.find_element(By.CSS_SELECTOR, "[aria-label='Close']")
                logging.info("Found close button using Method 2")
            except:
                logging.info("Method 2 failed to find close button")
        
        
        # If we found a close button, click it
        if close_button:
            logging.info("Clicking close button...")
            close_button.click()
            logging.info("Clicked close button")
            
            # Wait a moment to see the result
            time.sleep(3)
            
            # Take another screenshot after clicking
            driver.save_screenshot("after_closing_popup.png")
            logging.info("Saved screenshot after closing popup")
        else:
            logging.warning("Could not find close button in the login dialog")
            
            # Take a screenshot of the dialog for debugging
            dialog.screenshot("login_dialog.png")
            logging.info("Saved screenshot of the login dialog")
            
            # Save the HTML of the dialog for debugging
            with open("dialog_html.txt", "w", encoding="utf-8") as f:
                f.write(dialog.get_attribute("outerHTML"))
            logging.info("Saved dialog HTML to dialog_html.txt")
        
        # Wait a bit longer to see the final state
        time.sleep(10)
        
        logging.info("Test completed")
        
    except Exception as e:
        logging.error(f"Error: {e}")
    finally:
        pass
        # if driver:
        #     driver.quit()
        #     logging.info("WebDriver closed")
def makedriver():
    # Setup Chrome options
        options = Options()
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        options.add_argument("--disable-notifications")
        
        # Use a realistic user agent
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        # Initialize the driver
        driver = webdriver.Chrome(options=options)
        logging.info("WebDriver initialized")
        return driver
        # Navigate to the Facebook profile
if __name__ == "__main__":
    profile_url="https://m.facebook.com/profile.php?id=61556572291686"
    profile_url="https://www.facebook.com/bbcurdu"
    driver=makedriver()
    dismiss_login_popup(driver,profile_url)
    scroll_naturally(driver)
    time.sleep(10)
    scrape_facebook_posts(driver)
    time.sleep(50)