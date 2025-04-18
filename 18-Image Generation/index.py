import os
import json
import random
import time
import replicate
import requests
from pathlib import Path

# Set the API token as an environment variable
os.environ["REPLICATE_API_TOKEN"] = "r8_Kq95WuzQtpq3pR3bSaWeFrbeTxaUMne2PcpBP"

# Create base output directory
base_output_dir = Path("generated_profiles")
base_output_dir.mkdir(exist_ok=True)

# Track used attributes to ensure diversity
used_ethnicities = []
used_genders = []

class FileOutputEncoder(json.JSONEncoder):
    """Custom JSON encoder to handle non-serializable objects"""
    def default(self, obj):
        try:
            # First attempt to use the default encoder
            return super().default(obj)
        except TypeError:
            # If it fails, convert to string
            return str(obj)

def generate_traits(person_index):
    """Generate random traits for a person, ensuring diversity from previous profiles"""
    global used_ethnicities, used_genders
    
    # List of ethnicities as mentioned in the document
    ethnicities = [
        "Sub-Saharan African", "North African/Middle Eastern", "European", 
        "East Asian", "South Asian", "Southeast Asian", "Central Asian",
        "Pacific Islander", "Indigenous Peoples of the Americas", "Melanesian",
        "Afro-Caribbean/Afro-Latinx", "Mixed/Multiracial"
    ]
    
    genders = ["male", "female"]
    
    # For diversity, avoid repeating ethnicities and genders if possible
    available_ethnicities = [e for e in ethnicities if e not in used_ethnicities]
    available_genders = [g for g in genders if g not in used_genders]
    
    # If we've used all options, reset the lists
    if not available_ethnicities:
        available_ethnicities = ethnicities
    if not available_genders:
        available_genders = genders
    
    # Pick a primary ethnicity and gender
    primary_ethnicity = random.choice(available_ethnicities)
    gender = random.choice(available_genders)
    
    # Track what we've used
    used_ethnicities.append(primary_ethnicity)
    used_genders.append(gender)
    
    # Keep lists at a reasonable size
    if len(used_ethnicities) > 5:
        used_ethnicities.pop(0)
    if len(used_genders) > 2:
        used_genders.pop(0)
    
    # Gender values
    gender_value = 90 if gender == "male" else 90
    opposite_gender_value = 100 - gender_value
    
    # Generate ethnicity values
    ethnicity_values = []
    total = 0
    
    for ethnicity in ethnicities:
        if ethnicity == primary_ethnicity:
            value = random.randint(60, 90)
        else:
            value = random.randint(2, 20)
        total += value
        ethnicity_values.append({"name": ethnicity, "value": [max(0, value-5), min(100, value+5)]})
    
    # Normalize values to ensure they make sense proportionally
    factor = 100 / total if total > 0 else 1
    for item in ethnicity_values:
        normalized_value = round(item["value"][0] * factor)
        item["value"] = [max(0, normalized_value-5), min(100, normalized_value+5)]
    
    # Randomize physical attributes based on gender
    if gender == "male":
        weight_range = [65, 85]
        height_range = [170, 190]
        waist_range = [75, 95]
        bust_range = [90, 110]
        hips_range = [90, 110]
    else:
        weight_range = [50, 70]
        height_range = [155, 175]
        waist_range = [60, 80]
        bust_range = [80, 100]
        hips_range = [85, 105]
    
    # Generate a base set of traits for the person
    base_traits = {
        "celibacy": [random.randint(20, 80), random.randint(20, 80)],
        "cooperativeness": [random.randint(50, 90), random.randint(50, 90)],
        "intelligence": [random.randint(60, 95), random.randint(60, 95)],
        "weight": [random.randint(*weight_range), random.randint(*weight_range)],
        "waist": [random.randint(*waist_range), random.randint(*waist_range)],
        "bust": [random.randint(*bust_range), random.randint(*bust_range)],
        "hips": [random.randint(*hips_range), random.randint(*hips_range)],
        "gender": [
            {"name": "male", "value": [gender_value-5, gender_value+5]},
            {"name": "female", "value": [opposite_gender_value-5, opposite_gender_value+5]}
        ],
        "age": [random.randint(20, 35), random.randint(20, 35)],
        "height": [random.randint(*height_range), random.randint(*height_range)],
        "face": [random.randint(60, 95), random.randint(60, 95)],
        "ethnicity": ethnicity_values,
        "big_spender": [random.randint(30, 80), random.randint(30, 80)],
        "presentable": [random.randint(60, 95), random.randint(60, 95)],
        "muscle_percentage": [random.randint(10, 30), random.randint(10, 30)],
        "fat_percentage": [random.randint(10, 30), random.randint(10, 30)],
        "dominance": [random.randint(30, 90), random.randint(30, 90)],
        "power": [random.randint(40, 90), random.randint(40, 90)],
        "confidence": [random.randint(50, 95), random.randint(50, 95)]
    }
    
    # Make sure upper and lower bounds make sense (lower <= upper)
    for key, value in base_traits.items():
        if isinstance(value, list) and isinstance(value[0], (int, float)) and isinstance(value[1], (int, float)):
            lower, upper = min(value), max(value)
            base_traits[key] = [lower, upper]
    
    return base_traits, gender, primary_ethnicity

def create_prompt(traits, gender, primary_ethnicity, scene, pose, outfit):
    """Create a prompt for the image generation based on traits"""
    ethnicity_desc = primary_ethnicity.lower()
    
    age = (traits["age"][0] + traits["age"][1]) // 2
    height = (traits["height"][0] + traits["height"][1]) // 2
    weight = (traits["weight"][0] + traits["weight"][1]) // 2
    
    confidence_level = "confident" if traits["confidence"][1] > 70 else "reserved"
    muscle_level = "muscular" if traits["muscle_percentage"][1] > 20 else "average build"
    
    base_prompt = (
        f"full head-to-toe framing, zoomed-out, full-body shot of a candid {gender}, "
        f"{ethnicity_desc}, {age} years old, {height}cm tall, {weight}kg, {muscle_level}, "
        f"{confidence_level} person {pose} in {scene}, wearing {outfit}, "
        f"Tinder-style photo, 50mm camera, raw style, natural lighting, no professional photography, "
        f"realistic smartphone photo, amateur photo, 4:3 aspect ratio"
    )
    
    return base_prompt

def generate_images_for_person(person_index, num_images=8):
    """Generate a set of images of the same person in different scenarios"""
    print(f"\n=========================================")
    print(f"Generating profile {person_index+1} with {num_images} images")
    print(f"=========================================\n")
    
    # Generate consistent traits for the person
    traits, gender, primary_ethnicity = generate_traits(person_index)
    
    # Create a profile ID (timestamp-based with index)
    profile_id = f"{int(time.time())}_{person_index+1}"
    
    # Create a person-specific directory
    output_dir = base_output_dir / f"person_{profile_id}"
    output_dir.mkdir(exist_ok=True)
    
    print(f"Creating new profile: {profile_id}")
    print(f"Gender: {gender}")
    print(f"Primary Ethnicity: {primary_ethnicity}")
    print(f"Age: {traits['age'][0]}-{traits['age'][1]} years")
    print(f"Height: {traits['height'][0]}-{traits['height'][1]} cm")
    
    # Sample scenes, poses, and outfits for diversity
    scenes = [
        "a cafe", "a park", "a beach", "a street", "a gym", 
        "a restaurant", "a library", "hiking trail", "city square",
        "shopping mall", "museum", "bar", "concert", "farmer's market",
        "coffee shop", "bookstore", "art gallery"
    ]
    
    poses = [
        "standing casually", "sitting relaxed", "walking naturally",
        "laughing", "smiling at camera", "looking away from camera",
        "engaged in conversation", "reading a book", "using a phone",
        "drinking coffee", "eating food", "taking a selfie", 
        "stretching", "playing with a pet", "sitting cross-legged"
    ]
    
    outfits = [
        "casual jeans and t-shirt", "formal attire", "athletic wear",
        "summer dress", "business casual", "beach outfit", "winter clothing",
        "party outfit", "outdoor adventure clothing", "streetwear",
        "loungewear", "vintage style clothing", "elegant evening wear"
    ]
    
    # SDXL model on Replicate
    model = "stability-ai/sdxl:c221b2b8ef527988fb59bf24a8b97c4561f1c671f73bd389f866bfb27c061316"
    
    images_data = []
    
    # Generate each image with variations in scene, pose, and outfit
    for i in range(num_images):
        # Select different settings for each image
        scene = random.choice(scenes)
        pose = random.choice(poses)
        outfit = random.choice(outfits)
        
        # Create the prompt for this specific image
        prompt = create_prompt(traits, gender, primary_ethnicity, scene, pose, outfit)
        
        print(f"\nGenerating image {i+1}/{num_images}")
        print(f"Prompt: {prompt}")
        
        try:
            # Use the replicate.run function to generate the image
            output = replicate.run(
                model,
                input={
                    "prompt": prompt,
                    "negative_prompt": "cropped image, close-up, cut off, partial body, zoomed in, deformed, unrealistic, cartoon, anime, drawing, painting, sketch, bad anatomy, blurry, low quality",
                    "width": 768,
                    "height": 1024,
                    "num_outputs": 1,
                    "scheduler": "K_EULER_ANCESTRAL",
                    "num_inference_steps": 30,
                    "guidance_scale": 7.5
                }
            )
            
            # The output is a list of image URLs
            if not output:
                print("No output received from the model")
                continue
                
            # Get the URL of the first image - ensure it's a string
            if isinstance(output, list) and len(output) > 0:
                image_url = str(output[0])
            else:
                image_url = str(output)
            
            # Download the image
            response = requests.get(image_url)
            if response.status_code != 200:
                print(f"Failed to download image: {response.status_code}")
                continue
                
            # Create a filename based on profile and image index
            image_id = f"{i+1:03d}"
            filename = f"{image_id}.jpg"
            filepath = output_dir / filename
            
            # Save the image
            with open(filepath, "wb") as f:
                f.write(response.content)
            
            print(f"Image saved to: {filepath}")
            
            # Generate image-specific trait variations (slightly varied from base traits)
            image_traits = {}
            for key, value in traits.items():
                if isinstance(value, list):
                    if isinstance(value[0], (int, float)) and isinstance(value[1], (int, float)):
                        # For numeric ranges, slightly modify the ranges
                        lower = max(0, value[0] - random.randint(0, 10))
                        upper = min(100, value[1] + random.randint(0, 10))
                        image_traits[key] = [lower, upper]
                    else:
                        # For complex structures like gender and ethnicity, copy as is
                        image_traits[key] = value
            
            # Create a serializable dictionary for this image
            image_data = {
                "image_id": image_id,
                "profile_id": profile_id,
                "filepath": str(filepath),
                "url": image_url,
                "prompt": prompt,
                "scene": scene,
                "pose": pose,
                "outfit": outfit
            }
            
            # Add traits as a separate step to ensure they're serializable
            serializable_traits = {}
            for key, value in image_traits.items():
                # Convert any complex objects to strings if needed
                if isinstance(value, (list, dict, str, int, float, bool, type(None))):
                    serializable_traits[key] = value
                else:
                    serializable_traits[key] = str(value)
            
            image_data["traits"] = serializable_traits
            images_data.append(image_data)
            
        except Exception as e:
            print(f"Error generating image {i+1}: {str(e)}")
    
    # Save metadata using custom encoder to handle any non-serializable objects
    try:
        metadata_file = output_dir / "metadata.json"
        with open(metadata_file, "w") as f:
            json.dump({
                "profile_id": profile_id,
                "base_traits": traits,
                "gender": gender,
                "primary_ethnicity": primary_ethnicity,
                "images": images_data
            }, f, indent=2, cls=FileOutputEncoder)
        
        print(f"\nGenerated {len(images_data)} images of profile {profile_id}")
        print(f"Metadata saved to: {metadata_file}")
    except TypeError as e:
        print(f"Error saving metadata: {str(e)}")
        # Fallback: save only basic info
        try:
            basic_metadata = {
                "profile_id": profile_id,
                "gender": gender,
                "primary_ethnicity": primary_ethnicity,
                "images_generated": len(images_data),
                "image_filepaths": [img["filepath"] for img in images_data]
            }
            fallback_metadata_file = output_dir / "basic_metadata.json"
            with open(fallback_metadata_file, "w") as f:
                json.dump(basic_metadata, f, indent=2)
            print(f"Saved basic metadata to: {fallback_metadata_file}")
        except Exception as e2:
            print(f"Error saving basic metadata: {str(e2)}")
    
    return profile_id, len(images_data)

def generate_multiple_profiles(num_profiles=5, images_per_profile=8):
    """Generate multiple profiles with the specified number of images each"""
    print(f"Starting generation of {num_profiles} profiles with {images_per_profile} images each")
    
    results = []
    
    for i in range(num_profiles):
        profile_id, num_generated = generate_images_for_person(i, images_per_profile)
        results.append({
            "profile_id": profile_id,
            "images_generated": num_generated
        })
        
        # Sleep a bit between profiles to avoid rate limiting
        if i < num_profiles - 1:
            print(f"Waiting 5 seconds before generating next profile...")
            time.sleep(5)
    
    # Create a summary file
    try:
        summary_file = base_output_dir / "generation_summary.json"
        with open(summary_file, "w") as f:
            json.dump({
                "total_profiles": len(results),
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "profiles": results
            }, f, indent=2)
        
        print("\n=========================================")
        print(f"Completed generation of {len(results)} profiles")
        print(f"Summary saved to: {summary_file}")
        print("=========================================")
    except Exception as e:
        print(f"Error saving summary file: {str(e)}")
        print("\n=========================================")
        print(f"Completed generation of {len(results)} profiles")
        print("Could not save summary file due to error")
        print("=========================================")

if __name__ == "__main__":
    generate_multiple_profiles(1, 1)