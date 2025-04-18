class Profile:
    """Simple model for profile data"""
    def __init__(self, profile_id, gender, ethnicity, ethnicity_example):
        self.profile_id = profile_id
        self.gender = gender
        self.ethnicity = ethnicity
        self.ethnicity_example = ethnicity_example
        self.images = []
        
    def to_dict(self):
        """Convert to dictionary for JSON response"""
        return {
            'profile_id': self.profile_id,
            'gender': self.gender,
            'ethnicity': self.ethnicity,
            'ethnicity_example': self.ethnicity_example,
            'images': [img.to_dict() for img in self.images]
        }
        
class Image:
    """Simple model for image data"""
    def __init__(self, image_id, url, prompt, image_type='scene'):
        self.image_id = image_id
        self.url = url
        self.prompt = prompt
        self.type = image_type  # 'reference' or 'scene'
        self.scene = None
        self.pose = None
        self.outfit = None
        
    def to_dict(self):
        """Convert to dictionary for JSON response"""
        return {
            'image_id': self.image_id,
            'url': self.url,
            'prompt': self.prompt,
            'type': self.type,
            'scene': self.scene,
            'pose': self.pose,
            'outfit': self.outfit
        }