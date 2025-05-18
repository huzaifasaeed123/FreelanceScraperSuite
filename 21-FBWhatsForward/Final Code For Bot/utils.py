import os
import logging

def load_config(filepath="config.txt"):
    """Load configuration from simple text file with key=value format"""
    # Default values in case config file is missing or incomplete
    config = {
        "facebook": {
            "profile_url": "https://www.facebook.com/bbcurdu",
            "headless": False,
            "scroll_distance": 2100,
            "scroll_duration": 5,
            "scroll_step_size": 50,
            "posts_to_scrape": 5
        },
        "whatsapp": {
            "phone_number": "923471729745",
            "instance": "7105205743",
            "api": "3029b532f92048e0bbfa4adcb6aed55574b994edae144847a4"
        },
        "general": {
            "check_interval": 600,
            "output_dir": "result",
            "previous_posts_file": "previous_posts.json",
            "log_file": "facebook_bot.log"
        },
        "delays": {
            "after_page_load": 5,
            "after_popup_dismiss": 3,
            "after_scroll": 5,
            "between_posts": 3
        }
    }
    
    try:
        if not os.path.exists(filepath):
            logging.warning(f"Config file not found: {filepath}. Using default settings.")
            return config
        
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                
                # Skip comments and empty lines
                if not line or line.startswith('#'):
                    continue
                
                # Process key=value pairs
                if '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    
                    # Convert value to appropriate type
                    if value.lower() == 'true':
                        value = True
                    elif value.lower() == 'false':
                        value = False
                    elif value.isdigit():
                        value = int(value)
                    
                    # Assign to the appropriate section
                    if key in ['profile_url', 'headless', 'scroll_distance', 'posts_to_scrape']:
                        config['facebook'][key] = value
                    elif key in ['phone_number', 'instance', 'api']:
                        config['whatsapp'][key] = value
                    elif key in ['check_interval', 'output_dir', 'previous_posts_file', 'log_file']:
                        config['general'][key] = value
                    elif key in ['after_page_load', 'after_popup_dismiss', 'after_scroll', 'between_posts']:
                        config['delays'][key] = value
        
        return config
                    
    except Exception as e:
        logging.error(f"Error loading config file: {e}")
        return config