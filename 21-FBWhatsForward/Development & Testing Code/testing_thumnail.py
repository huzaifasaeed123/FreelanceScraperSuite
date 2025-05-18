import os
from bs4 import BeautifulSoup

def analyze_post_images(html_file="index.html"):
    """
    Load HTML post content and analyze all img tags to identify video thumbnails
    """
    # Read the HTML file
    with open(html_file, 'r', encoding='utf-8') as file:
        html_content = file.read()
    
    # Parse HTML content
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Find all img tags
    all_images = soup.find_all('img')
    print(f"Found {len(all_images)} total image tags")
    
    for i, img in enumerate(all_images):
        print(f"\n--- Image #{i+1} ---")
        print(f"Src: {img.get('src', 'None')}")
        print(f"Alt: {img.get('alt', 'None')}")
        print(f"Class: {img.get('class', 'None')}")
        print(f"Width x Height: {img.get('width', 'Auto')} x {img.get('height', 'Auto')}")
        
        # Check for video-related parent elements
        parent = img.parent
        print(f"Parent tag: {parent.name}")
        print(f"Parent class: {parent.get('class', 'None')}")
        
        # Check if image is inside a video player container
        video_container = find_video_container(img)
        if video_container:
            print("*** LIKELY VIDEO THUMBNAIL - Inside video container ***")
            print(f"Video container class: {video_container.get('class', 'None')}")
        
        # Look for play button or video controls near the image
        play_button = find_nearby_element(img, ['role', 'aria-label'], ['button', 'Play', 'Play video'])
        if play_button:
            print("*** LIKELY VIDEO THUMBNAIL - Has play button nearby ***")
        
        # Check image dimensions - video thumbnails often have specific aspect ratios
        if has_video_dimensions(img):
            print("*** LIKELY VIDEO THUMBNAIL - Has video-like dimensions ***")
        
        # Check for common video thumbnail class patterns
        if has_video_classes(img):
            print("*** LIKELY VIDEO THUMBNAIL - Has video-related classes ***")

def find_video_container(img, max_levels=5):
    """Look for video containers up to max_levels parents above the image"""
    element = img
    for _ in range(max_levels):
        if element.parent:
            element = element.parent
            # Check if this element looks like a video container
            if element.name in ['div'] and element.get('class'):
                classes = ' '.join(element.get('class', []))
                video_indicators = ['video', 'player', 'media']
                for indicator in video_indicators:
                    if indicator in classes.lower():
                        return element
                        
            # Check if there's a video element nearby
            if element.find('video'):
                return element
    return None

def find_nearby_element(img, attrs, values):
    """Look for elements with specific attributes/values near the image"""
    parent = img.parent
    for attr in attrs:
        for value in values:
            # Look for elements that have the attribute with the specified value
            found = parent.find_all(lambda tag: tag.get(attr) and value.lower() in tag.get(attr).lower())
            if found:
                return found[0]
    return None

def has_video_dimensions(img):
    """Check if image has dimensions typical for video thumbnails"""
    width = img.get('width')
    height = img.get('height')
    
    if not width or not height:
        return False
    
    try:
        width = int(width)
        height = int(height)
        # Check for common video aspect ratios (16:9, 4:3)
        ratio = width / height
        return 1.3 <= ratio <= 2.0  # Common video aspect ratios
    except (ValueError, ZeroDivisionError):
        return False

def has_video_classes(img):
    """Check if image has classes that suggest it's a video thumbnail"""
    classes = ' '.join(img.get('class', []))
    video_class_indicators = ['thumbnail', 'video', 'play', 'poster']
    
    for indicator in video_class_indicators:
        if indicator in classes.lower():
            return True
    return False

if __name__ == "__main__":
    analyze_post_images()