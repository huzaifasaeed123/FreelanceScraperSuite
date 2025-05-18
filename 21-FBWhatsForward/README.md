# FBWhatsForward - Facebook to WhatsApp Post Forwarder Bot

This repository contains a bot that automatically scrapes posts from a Facebook page and forwards them to WhatsApp. The bot supports text posts, images, and videos, with intelligent duplicate detection to avoid sending the same content multiple times.

## Repository Structure

### 📁 Development & Testing Code
Development environment and test files used during the creation of the bot. These files were used to test individual components and functionality before integration.

### 📁 FacebookBot(Final_Version)
Ready-to-use executable version of the bot:
- **FacebookBot.exe** - Main executable file
- **Start_Bot.bat** - Script to run the bot
- **Setup_Bot.bat** - Initial setup script
- **config.txt** - Configuration file (edit before running)
- **README.md** - User guide with detailed instructions

Simply download this folder if you want to use the bot without modifying the code.

### 📁 Final Code For Bot
The full source code of the bot:

- **main.py** - Entry point that runs the main loop checking for new posts
- **facebook_scraper1.py** - Contains functions for navigating Facebook and scraping posts
- **whatsapp_sender.py** - Handles downloading videos and sending content to WhatsApp
- **post_tracker.py** - Tracks which posts have been sent to avoid duplicates
- **utils.py** - Utility functions for configuration and general helpers

The bot works by periodically checking a configured Facebook page, scrolling to load content, identifying new posts by comparing with previously sent ones, and forwarding any new content to a WhatsApp number via API.

### 📁 Previous Bot
Legacy version developed previously that is no longer functional. Retained for reference purposes.

## Quick Start

### Using the Executable Version
1. Download the **FacebookBot(Final_Version)** folder
2. Run `Setup_Bot.bat` once
3. Edit `config.txt` with your settings (Facebook page URL and WhatsApp API credentials)
4. Run `Start_Bot.bat` to start the bot

### Running from Source Code
1. Download the **Final Code For Bot** folder
2. Install required dependencies: `pip install selenium yt-dlp requests`
3. Edit `config.txt` with your settings
4. Run `python main.py`

## Features
- Automatic post detection and extraction
- Support for text, images, and videos
- Robust duplicate detection to prevent sending the same post twice
- Natural scrolling behavior to avoid detection
- Headless operation option for server deployment
- Detailed logging for troubleshooting

## Requirements
- Windows OS
- Internet connection
- WhatsApp API credentials (if using the bot to send messages)

## License
This project is for educational purposes only. Use responsibly and in accordance with Facebook's Terms of Service.
