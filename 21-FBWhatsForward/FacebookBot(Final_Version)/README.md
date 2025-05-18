# Facebook Bot User Guide

## Overview
This bot automatically scrapes posts from a Facebook page and forwards them to WhatsApp. It can handle text posts, images, and videos.

## Initial Setup
1. Extract the ZIP file to a folder on your computer
2. Run `Setup_Bot.bat` once to create necessary folders
3. Edit `config.txt` with your settings (see Configuration section below)
4. Run `Start_Bot.bat` to launch the bot

## Configuration
Open `config.txt` in any text editor (like Notepad) to configure the bot:

### Important Settings to Change:
- `profile_url`: The Facebook page you want to monitor
- `phone_number`: Your WhatsApp number where posts will be sent
- `instance` and `api`: Your WhatsApp API credentials (contact your administrator if you need new credentials)

### Other Settings You Can Adjust:
- `headless`: Set to true to run invisibly, false to see the browser
- `check_interval`: How often to check for new posts (in seconds)
- `posts_to_scrape`: Maximum number of posts to process each time

## Running the Bot
1. Double-click on `Start_Bot.bat`
2. The bot will start running in a command window
3. Leave this window open - closing it will stop the bot
4. To stop the bot manually, close the command window

## Troubleshooting
- If the bot crashes or stops working, check `facebook_bot.log` for error messages
- If no posts are being sent, verify your WhatsApp API credentials
- If the bot can't access Facebook, try setting `headless=false` to see what's happening

## Files and Folders
- `FacebookBot.exe`: The main program
- `config.txt`: Configuration settings
- `Start_Bot.bat`: Script to start the bot
- `Setup_Bot.bat`: Initial setup script
- `sent_posts.json`: Tracks posts that have already been sent
- `result/`: Folder for temporary video storage
- `facebook_bot.log`: Log file for diagnosing issues

For additional help or to report issues, please contact your administrator.
