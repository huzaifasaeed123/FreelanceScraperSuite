import os
from pathlib import Path
from flask import url_for

def get_image_url(profile_id, filename, request=None):
    """Generate a URL for an image based on profile ID and filename"""
    # Return a properly formatted URL for the image
    return f"/images/person_{profile_id}/{filename}"

def ensure_directories():
    """Ensure all required directories exist"""
    base_dir = Path("static/generated_profiles")
    base_dir.mkdir(exist_ok=True, parents=True)
    return base_dir