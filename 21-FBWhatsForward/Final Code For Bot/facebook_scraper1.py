import time
import logging
import random
import os
import re
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from utils import load_config

# Configure logger for this module
logger = logging.getLogger(__name__)

def create_post_fingerprint(post):
    """
    Create a consistent, unique identifier for a post that works across runs.
    This combines multiple fields to make a reliable fingerprint.
    """
    parts = []
    
    # Use multiple components for identification
    if "text" in post and post["text"]:
        # Clean text to remove variable parts like timestamps
        clean_text = post["text"]
        # Remove common dynamic elements like timestamps and view counts
        clean_text = re.sub(r'\b\d+[hm]\b', '', clean_text)  # Remove "5h", "10m", etc.
        clean_text = re.sub(r'\d+\s+views', '', clean_text)  # Remove view counts
        parts.append(clean_text[:200])  # Use more text for better matching
    
    # Handle both old format (video_url) and new format (video_urls)
    if "video_urls" in post and post["video_urls"]:
        # Use all videos for the fingerprint to ensure consistency
        for video_url in post["video_urls"]:
            if '/videos/' in video_url:
                video_id = video_url.split('/videos/')[1].split('/')[0]
                parts.append(f"video:{video_id}")
            elif '/reel/' in video_url:
                video_id = video_url.split('/reel/')[1].split('/')[0]
                parts.append(f"reel:{video_id}")
            else:
                parts.append(video_url)
    elif "video_url" in post and post["video_url"]:
        # For backwards compatibility
        video_url = post["video_url"]
        if '/videos/' in video_url:
            video_id = video_url.split('/videos/')[1].split('/')[0]
            parts.append(f"video:{video_id}")
        elif '/reel/' in video_url:
            video_id = video_url.split('/reel/')[1].split('/')[0]
            parts.append(f"reel:{video_id}")
        else:
            parts.append(video_url)
    
    # Important: Do NOT use image URLs in fingerprint as they are less stable
    # and may change between runs, especially if they contain thumbnails
    
    # Use post_number if available (though less reliable across runs)
    if "post_number" in post:
        parts.append(f"num:{post['post_number']}")
    
    # Join all components with a separator
    fingerprint = "||".join(parts)
    
    # If we still have nothing, use the timestamp as a last resort
    if not fingerprint and "timestamp" in post:
        fingerprint = f"timestamp:{post['timestamp']}"
    
    return fingerprint

def makedriver(config=None):
    """Create and configure a Chrome WebDriver"""
    if config is None:
        config = load_config()
    
    fb_config = config.get("facebook", {})
    headless = fb_config.get("headless", False)
    
    # Setup Chrome options
    options = Options()
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument("--disable-notifications")
    
    # Set headless mode if configured
    if headless:
        options.add_argument("--headless=new")
    
    # Use a realistic user agent
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    # Initialize the driver
    driver = webdriver.Chrome(options=options)
    logger.info("WebDriver initialized")
    return driver

def dismiss_login_popup(driver, profile_url, config=None):
    """Visit Facebook profile and dismiss the login popup."""
    if config is None:
        config = load_config()
    
    delays = config.get("delays", {})
    after_page_load = delays.get("after_page_load", 5)
    after_popup_dismiss = delays.get("after_popup_dismiss", 3)
    
    try:
        logger.info(f"Navigating to {profile_url}")
        driver.get(profile_url)
        
        # Wait for page to load
        logger.info(f"Waiting {after_page_load} seconds for page to load")
        time.sleep(after_page_load)
        
        # Look for the login dialog
        logger.info("Looking for login popup dialog...")
        try:
            wait = WebDriverWait(driver, 10)
            dialog = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div[role='dialog']")))
            logger.info("Found login dialog")
            
            # Try different methods to find the close button
            close_button = None
            
            # Method 1: Look for a button directly inside the dialog
            try:
                close_button = dialog.find_element(By.CSS_SELECTOR, "div[role='button']")
                logger.info("Found close button using Method 1")
            except:
                logger.info("Method 1 failed to find close button")
            
            # Method 2: Look for a specific aria-label
            if not close_button:
                try:
                    close_button = dialog.find_element(By.CSS_SELECTOR, "[aria-label='Close']")
                    logger.info("Found close button using Method 2")
                except:
                    logger.info("Method 2 failed to find close button")
            
            # If we found a close button, click it
            if close_button:
                logger.info("Clicking close button...")
                close_button.click()
                logger.info("Clicked close button")
                logger.info(f"Waiting {after_popup_dismiss} seconds after dismissing popup")
                time.sleep(after_popup_dismiss)
            else:
                logger.warning("Could not find close button in the login dialog")
        
        except Exception as e:
            logger.info(f"No login popup found or error: {e}")
        
        # Wait to see the final state
        time.sleep(2)
        
    except Exception as e:
        logger.error(f"Error in dismiss_login_popup: {e}")

def scroll_naturally(driver, config=None):
    """Perform a smooth, incremental scroll"""
    if config is None:
        config = load_config()
    
    fb_config = config.get("facebook", {})
    delays = config.get("delays", {})
    
    scroll_distance = fb_config.get("scroll_distance", 2100)
    duration = fb_config.get("scroll_duration", 5)
    step_size = fb_config.get("scroll_step_size", 50)
    headless = fb_config.get("headless", False)
    after_scroll = delays.get("after_scroll", 5)
    
    try:
        logger.info(f"Starting incremental scroll of ~{scroll_distance} pixels over ~{duration} seconds")
        
        # Get initial scroll position
        initial_position = driver.execute_script("return window.pageYOffset;")
        logger.info(f"Initial scroll position: {initial_position}px")
        
        # Calculate how many steps we need and the delay between steps
        steps = max(int(scroll_distance / step_size), 1)
        delay_between_steps = duration / steps
        
        # Get page height to avoid scrolling past the bottom
        page_height = driver.execute_script("return document.body.scrollHeight")
        viewport_height = driver.execute_script("return window.innerHeight")
        
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
                logger.info("Already at the bottom of the page")
                break
                
            # Adjust step if needed
            if current_step > remaining_page:
                current_step = max(1, int(remaining_page * 0.9))  # Leave a little room
                logger.info(f"Approaching bottom, adjusted step to {current_step}px")
            
            # Execute the scroll - this works in both headless and non-headless
            driver.execute_script(f"window.scrollBy(0, {current_step});")
            
            scrolled += current_step
            
            # Add a randomized delay between scrolls
            time.sleep(delay_between_steps * random.uniform(0.8, 1.2))
            
            # Log progress occasionally
            if (i + 1) % 5 == 0 or i == steps - 1:
                current_position = driver.execute_script("return window.pageYOffset;")
                logger.info(f"Scrolled to position {current_position}px (step {i+1}/{steps})")
                
                # Check if new content has loaded by looking at page height
                new_page_height = driver.execute_script("return document.body.scrollHeight")
                if new_page_height > page_height:
                    logger.info(f"Page height increased from {page_height} to {new_page_height}")
                    page_height = new_page_height
        
        # Get final scroll position
        final_position = driver.execute_script("return window.pageYOffset;")
        logger.info(f"Final scroll position: {final_position}px (moved {final_position - initial_position}px)")
        
        # Wait for content to load after scrolling
        logger.info(f"Waiting {after_scroll} seconds for content to load after scrolling")
        time.sleep(after_scroll)
        
        return True
        
    except Exception as e:
        logger.error(f"Error during scrolling: {e}")
        return False

def scrape_facebook_posts(driver, config=None):
    """Scrape Facebook posts and return post data"""
    if config is None:
        config = load_config()
    
    general_config = config.get("general", {})
    fb_config = config.get("facebook", {})
    max_posts = fb_config.get("posts_to_scrape", 5)
    
    try:
        logger.info("Scraping Facebook posts")
        
        # Find all posts using the data-pagelet attribute pattern
        post_selector = "div[data-pagelet^='TimelineFeedUnit_']"
        posts = driver.find_elements(By.CSS_SELECTOR, post_selector)
        
        logger.info(f"Found {len(posts)} posts with selector: {post_selector}")
        
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
                    logger.info(f"Found {len(posts)} posts with alternative selector: {selector}")
                    break
        
        # Process each post (limit to max_posts)
        results = []
        for idx, post in enumerate(posts[:max_posts]):
            post_data = {"post_number": idx + 1}
            
            # Add timestamp
            post_data["timestamp"] = int(time.time())
            
            # Extract image data - find all img tags and clean their src URLs
            try:
                images = post.find_elements(By.TAG_NAME, "img")
                image_urls = []
                seen_image_urls = set()  # For tracking normalized URLs
                skipped_thumbnails = 0
                
                logger.info(f"Found {len(images)} total images in post {idx + 1}")
                
                for img_idx, img in enumerate(images):
                    try:
                        src = img.get_attribute("src")
                        if not src:
                            continue
                            
                        # Skip video thumbnails based on URL pattern
                        # Video thumbnails contain "t15.5256" in the URL path
                        if "t15.5256" in src:
                            skipped_thumbnails += 1
                            logger.info(f"Skipping video thumbnail in post {idx + 1}, image {img_idx+1} (URL pattern match)")
                            continue
                            
                        # # Also check alt text as a backup method
                        # try:
                        #     alt_text = img.get_attribute("alt")
                        #     if alt_text and alt_text == "Video thumbnail":
                        #         skipped_thumbnails += 1
                        #         logger.info(f"Skipping video thumbnail in post {idx + 1}, image {img_idx+1} (alt text match)")
                        #         continue
                        # except:
                        #     # If we can't get alt text, rely on the URL pattern check above
                        #     pass
                            
                        # Skip SVG images and emoji images which are not content
                        if src.endswith(".svg") or "emoji" in src.lower():
                            continue
                            
                        # Skip small icons and UI elements (typically small images)
                        try:
                            width = img.get_attribute("width")
                            height = img.get_attribute("height")
                            if width and height:
                                width_val = int(width)
                                height_val = int(height)
                                if width_val < 50 or height_val < 50:
                                    continue
                        except:
                            # If we can't get dimensions, don't filter based on size
                            pass
                        
                        # Normalize the URL by removing parameters and fragments
                        normalized_url = src.split('?')[0].split('#')[0]
                        
                        # Add only if we haven't seen this normalized URL yet
                        if normalized_url not in seen_image_urls:
                            seen_image_urls.add(normalized_url)
                            image_urls.append(src)
                    
                    except Exception as inner_e:
                        # If there's an error with a specific image, log it and continue
                        logger.debug(f"Error processing image {img_idx+1} in post {idx + 1}: {inner_e}")
                        continue
                
                if skipped_thumbnails > 0:
                    logger.info(f"Skipped {skipped_thumbnails} video thumbnails in post {idx + 1}")
                    
                if image_urls:
                    post_data["image_urls"] = image_urls
                    logger.info(f"Found {len(image_urls)} unique images in post {idx + 1}")
                    # Log first image URL as example
                    if image_urls:
                        logger.info(f"First image: {image_urls[0]}")
                
            except Exception as e:
                logger.warning(f"Error extracting image data: {e}")
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
                # Log post text (truncated if needed)
                if post_text:
                    try:
                        logger.info(f"Post {idx + 1} text: {post_text[:100]}{'...' if len(post_text) > 100 else ''}")
                    except UnicodeEncodeError:
                        # Handle potential encoding issues with non-Latin text
                        logger.info(f"Post {idx + 1} contains text in non-Latin characters")
                else:
                    logger.info(f"Post {idx + 1} has no text content")
                
            except Exception as e:
                logger.warning(f"Error getting post text: {e}")
                post_data["text"] = ""

            # Extract video links from role="link" elements
            try:
                # Find all elements with role="link" within the post
                link_elements = post.find_elements(By.CSS_SELECTOR, "[role='link']")
                video_links = []
                seen_video_ids = set()  # For tracking normalized video IDs
                
                for link in link_elements:
                    href = link.get_attribute("href")
                    if href:
                        # Check if the href contains 'videos' or 'reel'
                        if 'videos' in href or 'reel' in href:
                            # Remove parameters (everything after '?')
                            clean_url = href.split('?')[0]
                            
                            # Extract video ID for normalization
                            video_id = None
                            if '/videos/' in clean_url:
                                try:
                                    video_id = clean_url.split('/videos/')[1].split('/')[0]
                                except IndexError:
                                    video_id = None
                            elif '/reel/' in clean_url:
                                try:
                                    video_id = clean_url.split('/reel/')[1].split('/')[0]
                                except IndexError:
                                    video_id = None
                            
                            # Use video ID if available, otherwise use the full URL for deduplication
                            dedup_key = video_id if video_id else clean_url
                            
                            # Only add if we haven't seen this video before
                            if dedup_key and dedup_key not in seen_video_ids:
                                seen_video_ids.add(dedup_key)
                                video_links.append(clean_url)
                
                if video_links:
                    # Store all unique video links
                    post_data["video_urls"] = video_links
                    logger.info(f"Found {len(video_links)} unique video links in post {idx + 1}")
                    
                    # Keep video_url for backwards compatibility
                    if video_links:
                        post_data["video_url"] = video_links[0]
                        logger.info(f"First video: {video_links[0]}")
            except Exception as e:
                logger.warning(f"Error extracting video links: {e}")
            
            # Generate fingerprint for post comparison
            post_data["fingerprint"] = create_post_fingerprint(post_data)
            if post_data["fingerprint"]:
                logger.info(f"Post {idx + 1} fingerprint: {post_data['fingerprint'][:50]}...")
            
            results.append(post_data)
        
        return results
        
    except Exception as e:
        logger.error(f"Error scraping posts: {e}")
        return []