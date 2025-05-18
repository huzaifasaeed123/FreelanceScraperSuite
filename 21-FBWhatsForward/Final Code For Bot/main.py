import os
import time
import logging
from datetime import datetime
from utils import load_config
from post_tracker import SentPostsTracker

# Import functions from our modules
from facebook_scraper1 import makedriver, dismiss_login_popup, scroll_naturally, scrape_facebook_posts
from whatsapp_sender import send_post_to_whatsapp

def setup_logging():
    """Set up logging with proper encodings to handle Unicode characters"""
    config = load_config()
    general_config = config.get("general", {})
    log_file = general_config.get("log_file", "facebook_bot.log")
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Clear any existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Create file handler with UTF-8 encoding
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(file_formatter)
    
    # Create console handler that won't try to print Unicode that CMD can't handle
    console_handler = logging.StreamHandler()
    console_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(console_formatter)
    
    # Add the handlers to the root logger
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    
    # Create a module-specific logger
    logger = logging.getLogger(__name__)
    return logger

def process_posts(driver, config=None, post_tracker=None):
    """Process posts: scrape, identify new ones, send to WhatsApp"""
    if config is None:
        config = load_config()
    
    # Create post tracker if not provided
    if post_tracker is None:
        post_tracker = SentPostsTracker("sent_posts.json")
    
    # Scrape posts
    current_posts = scrape_facebook_posts(driver, config)
    
    if current_posts:
        # Filter to get only new posts
        new_posts = post_tracker.filter_new_posts(current_posts)
        
        if new_posts:
            logging.info(f"Found {len(new_posts)} new posts to send")
            
            # Send each new post
            delays = config.get("delays", {})
            between_posts_delay = delays.get("between_posts", 3)
            
            for post in new_posts:
                success = send_post_to_whatsapp(post, config)
                
                # Only mark as sent if actually sent successfully
                if success:
                    post_tracker.mark_as_sent(post)
                
                # Add delay between sending posts
                if len(new_posts) > 1:
                    logging.info(f"Waiting {between_posts_delay} seconds before next post")
                    time.sleep(between_posts_delay)
                
            return len(new_posts)
        else:
            logging.info("No new posts found")
            return 0
    else:
        logging.warning("No posts found during scraping")
        return 0

def main():
    """Main function that runs periodically to check for new posts"""
    # Set up logging first to handle Unicode properly
    logger = setup_logging()
    
    # Load configuration
    config = load_config()
    general_config = config.get("general", {})
    facebook_config = config.get("facebook", {})
    
    profile_url = facebook_config.get("profile_url", "https://www.facebook.com/bbcurdu")
    check_interval = general_config.get("check_interval", 600)
    output_dir = general_config.get("output_dir", "result")
    
    # Create output directory for videos
    os.makedirs(output_dir, exist_ok=True)
    
    # Create post tracker once
    post_tracker = SentPostsTracker("sent_posts.json")
    
    # Set up driver only once
    driver = None
    
    try:
        # Create driver
        driver = makedriver(config)
        
        while True:
            start_time = time.time()
            logger.info(f"Starting Facebook post check at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            try:
                # Navigate to the profile and dismiss login popup
                dismiss_login_popup(driver, profile_url, config)
                
                # Scroll down to load more content
                scroll_naturally(driver, config)
                
                # Process the posts
                process_posts(driver, config, post_tracker)
                
            except Exception as e:
                logger.error(f"Error during post processing: {e}")
            
            # Calculate how long to wait until the next check
            elapsed_time = time.time() - start_time
            wait_time = max(10, check_interval - elapsed_time)
            
            logger.info(f"Finished processing. Waiting {wait_time:.0f} seconds until next check...")
            time.sleep(wait_time)
            
    except KeyboardInterrupt:
        logger.info("Script interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error in main loop: {e}")
    finally:
        # Clean up
        if driver:
            driver.quit()
            logger.info("WebDriver closed")

if __name__ == "__main__":
    main()