import os
import time
import logging
import requests
import yt_dlp
from utils import load_config

# Configure logger for this module
logger = logging.getLogger(__name__)

def download_facebook_video(video_url, config=None):
    """Download Facebook video using yt-dlp"""
    if config is None:
        config = load_config()
    
    general_config = config.get("general", {})
    output_dir = general_config.get("output_dir", "result")
    
    os.makedirs(output_dir, exist_ok=True)
    
    timestamp = int(time.time())
    filename = f"video_{timestamp}.mp4"
    output_path = os.path.join(output_dir, filename)

    ytdl_opts = {
        'outtmpl': output_path,
        'format': 'mp4[height<=480]/best[height<=480]/best',
        'merge_output_format': 'mp4',
        'noplaylist': True,
        'quiet': False,
        'no_warnings': False,
        'ignoreerrors': True,
        'geo_bypass': True,
    }

    logger.info(f"Downloading video from: {video_url}")
    with yt_dlp.YoutubeDL(ytdl_opts) as ydl:
        try:
            info = ydl.extract_info(video_url, download=True)
            description = info.get("description", '')
            logger.info(f"Download completed: {output_path}")
            return output_path, description
        except Exception as e:
            logger.error(f"Error downloading video: {e}")
            return None, None

def upload_to_catbox(filepath):
    """Upload file to Catbox and get a direct URL"""
    try:
        with open(filepath, 'rb') as f:
            logger.info(f"Uploading file to Catbox: {filepath}")
            r = requests.post('https://catbox.moe/user/api.php',
                              data={'reqtype': 'fileupload'},
                              files={'fileToUpload': f})
        if r.status_code == 200:
            return r.text.strip()
        else:
            logger.error(f"Upload failed: {r.text}")
            return None
    except Exception as e:
        logger.error(f"Error uploading to Catbox: {e}")
        return None

def sendmsg(thenumber, msg, instance, api):
    """Send a text message via WhatsApp API"""
    url = f"https://7105.api.greenapi.com/waInstance{instance}/sendMessage/{api}"
    chatid = f"{thenumber}@c.us"
    payload = {
        "chatId": chatid,
        "message": msg
    }
    headers = {'Content-Type': 'application/json'}
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        logger.info(f"Text message sent. Response: {response.text.encode('utf8')}")
        return True
    except Exception as e:
        logger.error(f"Error sending text message: {e}")
        return False

def sendmsgurl(thenumber, captions, urlfile, filename, instance, api):
    """Send a file via URL through WhatsApp API"""
    url = f"https://7105.api.greenapi.com/waInstance{instance}/sendFileByUrl/{api}"
    chatid = f"{thenumber}@c.us"
    payload = {
        "chatId": chatid,   
        "urlFile": urlfile,
        "fileName": filename,
        "caption": captions
    }
    headers = {'Content-Type': 'application/json'}
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        logger.info(f"URL file message sent. Response: {response.text.encode('utf8')}")
        return True
    except Exception as e:
        logger.error(f"Error sending URL file message: {e}")
        return False

def normalize_url(url):
    """Normalize a URL by removing query parameters and fragments"""
    return url.split('?')[0].split('#')[0]

def extract_video_id(url):
    """Extract video ID from a Facebook video URL"""
    if '/videos/' in url:
        try:
            return url.split('/videos/')[1].split('/')[0]
        except IndexError:
            pass
    elif '/reel/' in url:
        try:
            return url.split('/reel/')[1].split('/')[0]
        except IndexError:
            pass
    return None

def deduplicate_urls(urls, extract_id_func=None):
    """
    Deduplicate URLs by normalizing and/or extracting IDs
    
    Args:
        urls: List of URLs to deduplicate
        extract_id_func: Optional function to extract unique IDs from URLs
                         If None, uses normalize_url for deduplication
    
    Returns:
        List of deduplicated URLs
    """
    unique_urls = []
    seen_keys = set()
    
    for url in urls:
        if extract_id_func:
            # Use the ID extraction function if provided
            key = extract_id_func(url)
            # If ID extraction fails, fall back to normalized URL
            if not key:
                key = normalize_url(url)
        else:
            # Otherwise just normalize the URL
            key = normalize_url(url)
        
        if key not in seen_keys:
            seen_keys.add(key)
            unique_urls.append(url)
    
    return unique_urls

def send_post_to_whatsapp(post, config=None):
    """Send a post to WhatsApp based on its content type"""
    if config is None:
        config = load_config()
    
    whatsapp_config = config.get("whatsapp", {})
    delays = config.get("delays", {})
    
    phone_number = whatsapp_config.get("phone_number")
    instance_id = whatsapp_config.get("instance")
    api_key = whatsapp_config.get("api")
    between_posts_delay = delays.get("between_posts", 3)
    
    try:
        logger.info(f"Sending post {post['post_number']} to WhatsApp")
        
        # Prepare initial caption text from post
        caption = post.get('text', '')
        if not caption:
            caption = "New post"
        
        success = True
        sent_anything = False
        
        # Handle multiple videos
        if 'video_urls' in post and post['video_urls']:
            # Deduplicate video URLs
            original_video_urls = post['video_urls']
            video_urls = deduplicate_urls(original_video_urls, extract_video_id)
            
            if len(video_urls) < len(original_video_urls):
                logger.info(f"Removed {len(original_video_urls) - len(video_urls)} duplicate videos")
            
            logger.info(f"Processing post with {len(video_urls)} unique videos")
            
            # Send each video
            for i, video_url in enumerate(video_urls):
                logger.info(f"Processing video {i+1}/{len(video_urls)}: {video_url}")
                
                # Download the video
                video_path, video_description = download_facebook_video(video_url, config)
                
                if video_path:
                    # Upload to Catbox
                    uploaded_url = upload_to_catbox(video_path)
                    
                    if uploaded_url:
                        logger.info(f"Video uploaded successfully: {uploaded_url}")
                        
                        # Send the video via WhatsApp
                        video_filename = os.path.basename(video_path)
                        
                        # Prepare caption for this video
                        if i == 0:
                            # For first video, use full caption
                            if video_description and not caption:
                                # If no post text but we have video description
                                video_caption = video_description
                            elif video_description and video_description not in caption:
                                # If both exist and not duplicate
                                video_caption = f"{caption}\n\n{video_description}"
                            else:
                                video_caption = caption
                        else:
                            # For subsequent videos, use a simpler caption
                            video_caption = f"Video {i+1}/{len(video_urls)}"
                            if video_description:
                                video_caption += f"\n\n{video_description}"
                        
                        # Send the video
                        video_success = sendmsgurl(
                            thenumber=phone_number,
                            captions=video_caption,
                            urlfile=uploaded_url,
                            filename=video_filename,
                            instance=instance_id,
                            api=api_key
                        )
                        
                        success = success and video_success
                        sent_anything = True
                        
                        # Clean up the local file
                        try:
                            os.remove(video_path)
                            logger.info(f"Deleted local video file: {video_path}")
                        except Exception as e:
                            logger.error(f"Error deleting video file: {e}")
                        
                        # Add delay between sending multiple videos
                        if i < len(video_urls) - 1:
                            time.sleep(between_posts_delay)
                    else:
                        logger.error(f"Failed to upload video to Catbox")
                else:
                    logger.error(f"Failed to download video from {video_url}")
        
        # Handle single video (for backwards compatibility)
        elif 'video_url' in post and post['video_url']:
            logger.info(f"Processing video post: {post['video_url']}")
            
            # Download the video
            video_path, video_description = download_facebook_video(post['video_url'], config)
            
            if video_path:
                # Upload to Catbox
                uploaded_url = upload_to_catbox(video_path)
                
                if uploaded_url:
                    logger.info(f"Video uploaded successfully: {uploaded_url}")
                    
                    # Send the video via WhatsApp
                    video_filename = os.path.basename(video_path)
                    
                    # Prepare caption
                    if video_description and not caption:
                        # If no post text but we have video description
                        video_caption = video_description
                    elif video_description and video_description not in caption:
                        # If both exist and not duplicate
                        video_caption = f"{caption}\n\n{video_description}"
                    else:
                        video_caption = caption
                    
                    # Send the video
                    video_success = sendmsgurl(
                        thenumber=phone_number,
                        captions=video_caption,
                        urlfile=uploaded_url,
                        filename=video_filename,
                        instance=instance_id,
                        api=api_key
                    )
                    
                    success = success and video_success
                    sent_anything = True
                    
                    # Clean up the local file
                    try:
                        os.remove(video_path)
                        logger.info(f"Deleted local video file: {video_path}")
                    except Exception as e:
                        logger.error(f"Error deleting video file: {e}")
                else:
                    logger.error(f"Failed to upload video to Catbox")
                    return False
            else:
                logger.error(f"Failed to download video from {post['video_url']}")
                return False
        
        # Handle images
        if 'image_urls' in post and post['image_urls']:
            # Deduplicate images
            original_image_urls = post['image_urls']
            image_urls = deduplicate_urls(original_image_urls)
            
            if len(image_urls) < len(original_image_urls):
                logger.info(f"Removed {len(original_image_urls) - len(image_urls)} duplicate images")
            
            logger.info(f"Processing post with {len(image_urls)} unique images")
            
            # Send each image
            for i, image_url in enumerate(image_urls):
                logger.info(f"Processing image {i+1}/{len(image_urls)}")
                
                # Extract a base filename from the URL
                image_filename = f"image_{int(time.time())}_{i}.jpg"
                if '/' in image_url:
                    url_filename = image_url.split('/')[-1].split('?')[0]
                    if '.' in url_filename:
                        image_filename = url_filename
                
                # Prepare caption for this image
                if i == 0 and not sent_anything:
                    # For first image and nothing sent yet, use full caption
                    image_caption = caption
                else:
                    # For subsequent images, use a simpler caption
                    image_caption = f"Image {i+1}/{len(image_urls)}"
                
                # Send the image
                image_success = sendmsgurl(
                    thenumber=phone_number,
                    captions=image_caption,
                    urlfile=image_url,
                    filename=image_filename,
                    instance=instance_id,
                    api=api_key
                )
                
                success = success and image_success
                sent_anything = True
                
                # Add delay between sending multiple images
                if i < len(image_urls) - 1:
                    time.sleep(between_posts_delay)
        
        # If it's just a text post with no media
        if not sent_anything:
            logger.info("Processing text-only post")
            
            # Send text message
            text_success = sendmsg(
                thenumber=phone_number,
                msg=caption,
                instance=instance_id,
                api=api_key
            )
            
            success = success and text_success
            sent_anything = True
        
        return success and sent_anything
        
    except Exception as e:
        logger.error(f"Error sending post to WhatsApp: {e}")
        return False