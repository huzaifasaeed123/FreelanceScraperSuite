import os
import json
import logging
import time

logger = logging.getLogger(__name__)

class SentPostsTracker:
    """
    Class to track and manage posts that have been sent to WhatsApp.
    This ensures we never send the same post twice.
    """
    
    def __init__(self, filename="sent_posts.json"):
        self.filename = filename
        self.sent_posts = self._load_sent_posts()
        self.sent_fingerprints = {post.get("fingerprint") for post in self.sent_posts if "fingerprint" in post}
        logger.info(f"Loaded {len(self.sent_fingerprints)} previous post fingerprints")
    
    def _load_sent_posts(self):
        """Load previously sent posts from the JSON file."""
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading sent posts: {e}")
                return []
        return []
    
    def _save_sent_posts(self):
        """Save the current list of sent posts to the JSON file."""
        try:
            with open(self.filename, 'w', encoding='utf-8') as f:
                json.dump(self.sent_posts, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error saving sent posts: {e}")
    
    def is_new_post(self, post):
        """Check if a post is new (hasn't been sent before)."""
        if not post:
            return False
            
        fingerprint = post.get("fingerprint")
        if not fingerprint:
            # If no fingerprint, use post_id as fallback
            fingerprint = post.get("post_id")
            
        if not fingerprint:
            logger.warning("Post has no fingerprint or post_id, treating as new")
            return True
            
        is_new = fingerprint not in self.sent_fingerprints
        
        # Log for debugging
        if is_new:
            logger.info(f"Post {post.get('post_number')} is NEW")
        else:
            logger.info(f"Post {post.get('post_number')} was ALREADY SENT (fingerprint match)")
            
        return is_new
    
    def mark_as_sent(self, post):
        """Mark a post as sent, so we don't send it again."""
        if not post:
            return
            
        fingerprint = post.get("fingerprint")
        if not fingerprint:
            logger.warning("Cannot mark post as sent: no fingerprint")
            return
            
        # Add to our set of sent fingerprints
        self.sent_fingerprints.add(fingerprint)
        
        # Add a sent timestamp to the post
        post_copy = post.copy()
        post_copy["sent_timestamp"] = int(time.time())
        
        # Add to our list of sent posts
        self.sent_posts.append(post_copy)
        
        # Save the updated list to disk
        self._save_sent_posts()
        
        logger.info(f"Marked post {post.get('post_number')} as sent")
    
    def filter_new_posts(self, posts):
        """Filter a list of posts to only return new ones."""
        new_posts = [post for post in posts if self.is_new_post(post)]
        logger.info(f"Filtered {len(posts)} posts to {len(new_posts)} new posts")
        return new_posts