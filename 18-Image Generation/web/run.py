#!/usr/bin/env python3
"""
Quick start script for the AI Person Generator application.
This script checks for required dependencies and helps with setup.
"""

import os
import sys
import subprocess
import platform
from pathlib import Path
import webbrowser
import time

def check_dependencies():
    """Check if required packages are installed"""
    try:
        import flask
        import replicate
        return True
    except ImportError:
        return False

def install_dependencies():
    """Install required packages"""
    print("Installing required dependencies...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        return True
    except subprocess.CalledProcessError:
        return False

def check_api_key():
    """Check if Replicate API key is set"""
    api_key = os.environ.get("REPLICATE_API_TOKEN")
    
    if not api_key:
        # Check if .env file exists
        if os.path.exists(".env"):
            # Try to load from .env file
            with open(".env", "r") as f:
                for line in f:
                    if line.startswith("REPLICATE_API_TOKEN="):
                        api_key = line.split("=")[1].strip()
                        os.environ["REPLICATE_API_TOKEN"] = api_key
                        break
    
    return bool(api_key)

def prompt_for_api_key():
    """Prompt user to enter Replicate API key"""
    print("\n[SETUP] Replicate API key is required for image generation.")
    print("Get your API key from: https://replicate.com/account/api-tokens")
    
    api_key = input("\nEnter your Replicate API key: ")
    
    if api_key:
        # Set environment variable
        os.environ["REPLICATE_API_TOKEN"] = api_key
        
        # Save to .env file
        with open(".env", "w") as f:
            f.write(f"REPLICATE_API_TOKEN={api_key}\n")
        
        print("API key saved to .env file")
        return True
    
    return False

def create_directories():
    """Create necessary directories"""
    os.makedirs("static/generated_profiles", exist_ok=True)

def start_application():
    """Start the Flask application"""
    print("\n[STARTING] AI Person Generator")
    print("=" * 50)
    print("The web interface will be available at: http://localhost:5000")
    print("Press Ctrl+C to stop the application")
    print("=" * 50 + "\n")
    
    # Open web browser after a short delay
    def open_browser():
        time.sleep(1.5)
        webbrowser.open("http://localhost:5000/static/index.html")
    
    import threading
    threading.Thread(target=open_browser).start()
    
    # Import and run the Flask app
    from app import app
    app.run(debug=True, port=5000)

def main():
    print("\n" + "=" * 50)
    print("AI Person Generator - Setup")
    print("=" * 50)
    
    # Check and create directories
    create_directories()
    
    # Check dependencies
    if not check_dependencies():
        print("\n[SETUP] Required packages are not installed.")
        
        if install_dependencies():
            print("[SETUP] Successfully installed dependencies.")
        else:
            print("[ERROR] Failed to install dependencies.")
            print("Please manually install packages from requirements.txt:")
            print("pip install -r requirements.txt")
            return
    
    # Check API key
    if not check_api_key():
        print("\n[SETUP] Replicate API key not found.")
        
        if not prompt_for_api_key():
            print("[ERROR] API key is required to use this application.")
            print("You can set it later by creating a .env file with:")
            print("REPLICATE_API_TOKEN=your_api_key_here")
            return
    
    # Start the application
    try:
        start_application()
    except KeyboardInterrupt:
        print("\n\nApplication stopped. Thank you for using AI Person Generator!")

if __name__ == "__main__":
    main()