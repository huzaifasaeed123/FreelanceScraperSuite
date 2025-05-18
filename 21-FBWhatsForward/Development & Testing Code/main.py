import json
import time
import datetime
import copy
import requests
import uuid
import os
import sys
import platform
import logging
import random
from facebook_scraper import get_posts, set_user_agent

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_script_directory():
    """Gets the directory where the script (or executable) is located."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.abspath(__file__))

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

def extract_profile_name(profile_url):
    """Extract profile name or ID from URL."""
    # Handle different URL formats
    if 'facebook.com/' in profile_url:
        parts = profile_url.split('facebook.com/')
        if len(parts) > 1:
            path = parts[1].strip('/')
            
            # Handle profile.php?id=XXX format
            if 'profile.php?id=' in path:
                return path  # Return the whole path including profile.php?id=
            
            # Handle facebook.com/username format
            return path.split('/')[0]
    
    # If not a standard format, return the full URL
    return profile_url

def scrape_facebook_posts_with_lib(profile_url):
    """Use facebook-scraper to get posts from a profile without login."""
    try:
        # Extract profile name/id from URL
        profile_name = extract_profile_name(profile_url)
        logging.info(f"Extracted profile name: {profile_name}")
        
        # Set a realistic user agent
        set_user_agent("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        # Get posts (limited to 5 to avoid rate limiting)
        posts = list(get_posts(profile_name, pages=1, extra_info=True, timeout=30))
        
        if not posts:
            logging.warning("No posts found")
            return {}
        
        allTheData = {}
        
        for idx, post in enumerate(posts[:5]):
            post_id = post.get('post_id', str(idx + 1))
            
            # Extract header (username) and description (text)
            header = post.get('username', 'N/A')
            description = post.get('text', 'N/A')
            
            # Extract video URL - facebook-scraper provides this directly
            video_url = post.get('video', 'N/A')
            if video_url:
                logging.info(f"Found video URL in post {post_id}: {video_url}")
            
            # Extract image URL
            image_src = 'N/A'
            if 'images' in post and post['images']:
                # Get the first image URL
                image_src = post['images'][0]
                logging.info(f"Found image URL in post {post_id}: {image_src}")
            
            # Store data in the same format as the original script
            allTheData[post_id] = {
                "header": header,
                "description": description,
                "data_video_url": video_url if video_url else 'N/A',
                "image_src": image_src
            }
            
            # Log the full post data for debugging
            logging.info(f"Post {post_id} data: {json.dumps(post, default=str)[:500]}...")
        
        if allTheData:
            logging.info(f"Successfully scraped {len(allTheData)} posts")
        else:
            logging.warning("No posts could be extracted")
            
        return allTheData
        
    except Exception as e:
        logging.error(f"Error in facebook-scraper: {e}")
        return {}

if __name__ == '__main__':
    script_dir = get_script_directory()
    config_file_path = os.path.join(script_dir, "config.txt")
    config = read_config_from_file(config_file_path)

    # Get configuration parameters
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
    
    sendmsg(recipient_number, "BOT STARTED WITH FACEBOOK-SCRAPER", instance, api)
    
    retry_count = 0
    max_retries = 5
    
    while True:
        try:
            data = scrape_facebook_posts_with_lib(profile_link)
            
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