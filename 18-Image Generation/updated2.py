import os
import json
import random
import time
import replicate
import requests
from pathlib import Path
from io import BytesIO
import base64

# Set the API token as an environment variable
os.environ["REPLICATE_API_TOKEN"] = "r8_Kq95WuzQtpq3pR3bSaWeFrbeTxaUMne2PcpBP"

# Create base output directory
base_output_dir = Path("generated_profiles")
base_output_dir.mkdir(exist_ok=True)

# Track used attributes to ensure diversity
used_ethnicities = []
used_genders = []

# Define ethnicity traits for prompt enhancement
ETHNICITY_TRAITS = {
    "Sub-Saharan African": {
        "traits": "Dark to very dark skin, tightly coiled hair (Type 4 texture), broad nose, fuller lips",
        "examples": ["Bantu", "Zulu", "Yoruba", "Maasai", "Dinka", "Aka", "Mbuti"]
    },
    "North African/Middle Eastern": {
        "traits": "Olive to light brown skin, wavy to curly hair, prominent nose, lighter eye colors in some populations",
        "examples": ["Berber", "Arab", "Persian", "Bedouin"]
    },
    "European": {
        "traits": "Light skin tones, varied hair colors (blonde, brown, red), varied eye colors (blue, green, brown), straight to wavy hair",
        "examples": ["Scandinavian", "Slavic", "Mediterranean", "Italian", "Greek"]
    },
    "East Asian": {
        "traits": "Lighter yellowish skin tones, straight black hair, monolid or epicanthic fold eyes, rounded face shapes",
        "examples": ["Han Chinese", "Korean", "Japanese"]
    },
    "South Asian": {
        "traits": "Brown to dark brown skin tones, straight to wavy black hair, prominent facial features such as sharp nose and full lips",
        "examples": ["Tamil", "Punjabi", "Bengali"]
    },
    "Southeast Asian": {
        "traits": "Tan to medium brown skin tones, straight to wavy black hair, almond-shaped eyes, rounder facial features",
        "examples": ["Thai", "Filipino", "Khmer", "Malay"]
    },
    "Central Asian": {
        "traits": "Light to tan skin tones, straight black or brown hair, mixed East Asian and European features like high cheekbones and epicanthic fold",
        "examples": ["Kazakh", "Uzbek", "Mongol", "Turkmen"]
    },
    "Pacific Islander": {
        "traits": "Medium to dark brown skin tones, wavy to curly black hair, robust build, rounder facial features",
        "examples": ["Samoan", "Tongan", "Micronesian", "Fijian"]
    },
    "Indigenous Peoples of the Americas": {
        "traits": "Medium to tan skin tones, straight black hair, high cheekbones, prominent noses",
        "examples": ["Navajo", "Quechua", "Inuit", "Maya"]
    },
    "Melanesian": {
        "traits": "Very dark skin tones, frizzy or afro-textured hair, distinct facial features like wide noses and high cheekbones",
        "examples": ["Papua New Guinean", "Solomon Islander"]
    },
    "Afro-Caribbean/Afro-Latinx": {
        "traits": "Mixed African, European, and Indigenous features; dark skin tones with varied facial structures and hair textures",
        "examples": ["Jamaican", "Dominican", "Haitian", "Afro-Brazilian"]
    },
    "Mixed/Multiracial": {
        "traits": "Highly variable; combinations of traits from multiple ethnic groups depending on ancestry",
        "examples": ["Eurasian", "Afro-European", "Mestizo"]
    }
}

# Color palettes for different outfits to ensure variety
OUTFIT_COLORS = {
    "casual jeans and t-shirt": ["blue jeans with white t-shirt", "black jeans with gray t-shirt", "blue jeans with red t-shirt", 
                                "ripped jeans with band t-shirt", "light wash jeans with pastel t-shirt"],
    "formal attire": ["black suit with white shirt", "navy suit with light blue shirt", "gray suit with pink tie", 
                     "black dress with pearl necklace", "maroon evening gown", "tuxedo with bow tie"],
    "athletic wear": ["black leggings with sports bra", "running shorts with tank top", "tracksuit in blue", 
                     "yoga pants with fitted top", "basketball jersey and shorts"],
    "summer dress": ["floral sundress in yellow", "light blue maxi dress", "white beach dress", "red summer dress with spaghetti straps", 
                    "pastel pink dress with sandals"],
    "business casual": ["khaki pants with button-up shirt", "pencil skirt with blouse", "chinos with polo shirt", 
                       "dress pants with cardigan", "blazer with jeans"],
    "beach outfit": ["swim trunks in bright colors", "bikini with cover-up", "board shorts with tank top", 
                    "one-piece swimsuit with sun hat", "swim shorts with Hawaiian shirt"],
    "winter clothing": ["heavy coat with scarf and gloves", "sweater with jeans and boots", "parka with beanie", 
                       "turtleneck with wool pants", "puffer jacket with thermal pants"],
    "party outfit": ["sequin dress", "button-up shirt with dress pants", "cocktail dress in black", 
                    "blazer with stylish jeans", "mini dress with heels"],
    "outdoor adventure clothing": ["hiking pants with moisture-wicking shirt", "cargo shorts with t-shirt", "fishing vest with hat", 
                                 "utility pants with fleece jacket", "khaki shirt with shorts"],
    "streetwear": ["oversized hoodie with baggy jeans", "graphic t-shirt with cargo pants", "bomber jacket with skinny jeans", 
                  "tracksuit with sneakers", "urban style jacket with distressed jeans"],
    "loungewear": ["sweatpants with comfortable t-shirt", "pajama set", "joggers with hoodie", 
                  "leggings with oversized sweater", "cotton shorts with tank top"],
    "vintage style clothing": ["50s style swing dress", "70s bellbottoms with tie-dye shirt", "80s neon outfit", 
                             "retro high-waisted jeans with crop top", "classic pin-up style dress"],
    "elegant evening wear": ["floor-length gown in emerald green", "black tie attire with bowtie", "silk dress with elegant jewelry", 
                           "designer suit with pocket square", "satin dress with shawl"]
}

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
    ethnicities = list(ETHNICITY_TRAITS.keys())
    
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
    
    # Generate all specified personality and physical traits with reasonable ranges
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
    
    # Select a specific example from the ethnicity
    ethnicity_example = random.choice(ETHNICITY_TRAITS[primary_ethnicity]["examples"])
    
    return base_traits, gender, primary_ethnicity, ethnicity_example

def create_reference_prompt(traits, gender, primary_ethnicity, ethnicity_example):
    """Create a detailed prompt for generating a good reference image with all specified attributes"""
    ethnicity_desc = primary_ethnicity.lower()
    ethnicity_traits = ETHNICITY_TRAITS[primary_ethnicity]["traits"]
    
    # Extract average values from trait ranges
    age = (traits["age"][0] + traits["age"][1]) // 2
    height = (traits["height"][0] + traits["height"][1]) // 2
    weight = (traits["weight"][0] + traits["weight"][1]) // 2
    waist = (traits["waist"][0] + traits["waist"][1]) // 2
    bust = (traits["bust"][0] + traits["bust"][1]) // 2
    hips = (traits["hips"][0] + traits["hips"][1]) // 2
    
    # Personality trait descriptions
    celibacy = (traits["celibacy"][0] + traits["celibacy"][1]) // 2
    celibacy_desc = "reserved and modest" if celibacy > 65 else "confident with sensual energy" if celibacy < 35 else ""
    
    intelligence = (traits["intelligence"][0] + traits["intelligence"][1]) // 2
    intelligence_desc = "intellectual appearance with thoughtful expression" if intelligence > 75 else ""
    
    confidence = (traits["confidence"][0] + traits["confidence"][1]) // 2
    confidence_desc = "highly confident" if confidence > 75 else "somewhat reserved" if confidence < 50 else "moderately confident"
    
    dominance = (traits["dominance"][0] + traits["dominance"][1]) // 2
    dominance_desc = "commanding presence" if dominance > 75 else "gentle demeanor" if dominance < 40 else ""
    
    presentable = (traits["presentable"][0] + traits["presentable"][1]) // 2
    presentable_desc = "well-groomed and polished appearance" if presentable > 70 else ""
    
    # Physical descriptions
    muscle_percentage = (traits["muscle_percentage"][0] + traits["muscle_percentage"][1]) // 2
    fat_percentage = (traits["fat_percentage"][0] + traits["fat_percentage"][1]) // 2
    
    if gender == "male":
        body_type_desc = (
            "athletic muscular build" if muscle_percentage > 25 and fat_percentage < 15 else
            "slim fit physique" if muscle_percentage > 15 and fat_percentage < 20 else
            "average male build" if fat_percentage < 25 else
            "stocky build" if fat_percentage > 25 else "average male build"
        )
    else:
        body_type_desc = (
            "athletic toned figure" if muscle_percentage > 20 and fat_percentage < 20 else
            "slim figure" if fat_percentage < 20 else
            "curvy figure" if fat_percentage > 20 and bust > 90 and hips > 90 else
            "average female build"
        )
    
    # Combine all traits into a comprehensive prompt
    detailed_traits = f"{ethnicity_traits}. {body_type_desc}. {confidence_desc}. " + \
                     f"{intelligence_desc} {presentable_desc} {dominance_desc} {celibacy_desc}".strip()
    
    # For reference image, create a neutral pose with clear face visibility
    reference_prompt = (
        f"professional headshot portrait of a {gender} {ethnicity_example}, "
        f"{ethnicity_desc} ethnicity with {detailed_traits}, "
        f"{age} years old, {height}cm tall, {weight}kg, waist {waist}cm, "
        f"bust {bust}cm, hips {hips}cm, looking directly at camera with neutral expression, "
        f"plain neutral background, even lighting, clear face visibility, "
        f"high detail, photorealistic, 4K, highly detailed face, professional photography"
    )
    
    return reference_prompt

def create_scene_prompt(traits, gender, primary_ethnicity, ethnicity_example, scene, pose, outfit, face_description=""):
    """Create a detailed prompt for scene images with appropriate outfit variations"""
    ethnicity_desc = primary_ethnicity.lower()
    ethnicity_traits = ETHNICITY_TRAITS[primary_ethnicity]["traits"]
    
    # Extract average values from trait ranges
    age = (traits["age"][0] + traits["age"][1]) // 2
    height = (traits["height"][0] + traits["height"][1]) // 2
    weight = (traits["weight"][0] + traits["weight"][1]) // 2
    
    confidence = (traits["confidence"][0] + traits["confidence"][1]) // 2
    confidence_desc = "confident" if confidence > 60 else "reserved"
    
    muscle_percentage = (traits["muscle_percentage"][0] + traits["muscle_percentage"][1]) // 2
    if gender == "male":
        body_type_desc = (
            "muscular" if muscle_percentage > 20 else "average build"
        )
    else:
        body_type_desc = (
            "toned" if muscle_percentage > 20 else "slender"
        )
    
    # Get a random specific color/style for the outfit
    specific_outfit = random.choice(OUTFIT_COLORS[outfit])
    
    # Add face description if provided (from reference image)
    face_details = f", {face_description}" if face_description else ""
    
    # Create a comprehensive scene-specific prompt
    base_prompt = (
        f"full body candid shot of a {gender} {ethnicity_example}, "
        f"{ethnicity_desc} ethnicity with {ethnicity_traits}, "
        f"{age} years old, {height}cm tall, {weight}kg, {body_type_desc}, "
        f"{confidence_desc} person{face_details} {pose} in {scene}, "
        f"wearing {specific_outfit}, "
        f"natural lighting, realistic photograph, candid moment, 50mm lens, 4:3 aspect ratio"
    )
    
    return base_prompt

def download_image(url):
    """Download an image from a URL and return it as bytes"""
    response = requests.get(url)
    if response.status_code != 200:
        raise Exception(f"Failed to download image: {response.status_code}")
    return response.content

def encode_image_base64(image_data):
    """Encode image bytes to base64 string for API submission"""
    return base64.b64encode(image_data).decode('utf-8')

def image_to_data_uri(image_data, mime_type="image/jpeg"):
    """Convert image bytes to data URI for API submission"""
    base64_data = base64.b64encode(image_data).decode('utf-8')
    return f"data:{mime_type};base64,{base64_data}"

def get_base64_from_file(filepath):
    """Read an image file and return base64 encoded string"""
    with open(filepath, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode('utf-8')

def generate_images_for_person(person_index, num_images=8):
    """Generate a set of images of the same person in different scenarios using a reference image approach"""
    print(f"\n=========================================")
    print(f"Generating profile {person_index+1} with {num_images} images using reference image")
    print(f"=========================================\n")
    
    # Generate comprehensive traits for the person
    traits, gender, primary_ethnicity, ethnicity_example = generate_traits(person_index)
    
    # Create a profile ID (timestamp-based with index)
    profile_id = f"{int(time.time())}_{person_index+1}"
    
    # Create a person-specific directory
    output_dir = base_output_dir / f"person_{profile_id}"
    output_dir.mkdir(exist_ok=True)
    
    print(f"Creating new profile: {profile_id}")
    print(f"Gender: {gender}")
    print(f"Primary Ethnicity: {primary_ethnicity}")
    print(f"Ethnicity Example: {ethnicity_example}")
    print(f"Age: {traits['age'][0]}-{traits['age'][1]} years")
    print(f"Height: {traits['height'][0]}-{traits['height'][1]} cm")
    
    # Sample scenes, poses, and outfits for diversity - keeping them diverse and detailed
    scenes = [
        "a bustling cafe with patrons in background", 
        "a sunny park with trees and benches", 
        "a tropical beach with ocean waves", 
        "a busy city street with skyscrapers", 
        "a modern gym with exercise equipment", 
        "an upscale restaurant with ambient lighting", 
        "a public library with bookshelves", 
        "a scenic hiking trail with mountains",
        "a historic city square with fountains",
        "a modern shopping mall with storefronts",
        "an art museum with exhibits",
        "a stylish bar with mood lighting",
        "an outdoor concert venue with crowd",
        "a colorful farmer's market with produce stalls",
        "a cozy coffee shop with wooden furniture",
        "a vintage bookstore with stacked shelves",
        "a contemporary art gallery with exhibits"
    ]
    
    poses = [
        "standing casually with hands in pockets", 
        "sitting relaxed in a chair", 
        "walking naturally with confident stride",
        "laughing genuinely at something off-camera", 
        "smiling warmly at camera", 
        "looking thoughtfully away from camera",
        "engaged in conversation with someone", 
        "reading intently from a book", 
        "using a smartphone with focused attention",
        "drinking casually from a coffee cup", 
        "enjoying a meal with utensils in hand", 
        "taking a selfie with arm extended", 
        "stretching arms after exercise", 
        "playing gently with a pet", 
        "sitting cross-legged on the floor"
    ]
    
    # Keep the outfit categories but will use specific variations from OUTFIT_COLORS
    outfits = list(OUTFIT_COLORS.keys())
    
    # SDXL models on Replicate
    # Base model for initial image generation
    base_model = "stability-ai/sdxl:c221b2b8ef527988fb59bf24a8b97c4561f1c671f73bd389f866bfb27c061316"
    
    # Using the verified working IP-Adapter model from docs
    ip_adapter_model = "lucataco/ip_adapter-sdxl-face:226c6bf67a75a129b0f978e518fed33e1fb13956e15761c1ac53c9d2f898c9af"
    
    images_data = []
    reference_image_data = None
    reference_url = None
    face_description = ""
    
    # Step 1: Generate a reference image with detailed attributes
    print("\n========== STEP 1: GENERATING REFERENCE IMAGE ==========")
    reference_prompt = create_reference_prompt(traits, gender, primary_ethnicity, ethnicity_example)
    print(f"Reference Image Prompt: {reference_prompt}")
    
    try:
        # Generate the reference image using the base model
        output = replicate.run(
            base_model,
            input={
                "prompt": reference_prompt,
                "negative_prompt": "deformed face, unrealistic, cartoon, anime, drawing, painting, sketch, bad anatomy, blurry, low quality, distorted face, bad face, extra limbs, disfigured, ugly, poorly drawn hands, missing limbs, floating limbs, disconnected limbs, malformed hands, blurry, watermark, logo, text, typography",
                "width": 768,
                "height": 768,  # Square format for face reference
                "num_outputs": 1,
                "scheduler": "K_EULER_ANCESTRAL",
                "num_inference_steps": 50,  # More steps for better quality
                "guidance_scale": 8.0  # Higher guidance for more prompt adherence
            }
        )
        
        # Handle the generator output from replicate.run
        try:
            # Convert generator to list if it is a generator
            if hasattr(output, '__next__') or hasattr(output, '__iter__'):
                output_list = list(output)
                if output_list:
                    reference_url = str(output_list[0])
                    print(f"Generated reference image URL: {reference_url}")
                else:
                    print("No reference image was generated (empty generator). Falling back to non-reference approach.")
                    reference_url = None
            # Handle if it's already a list
            elif isinstance(output, list) and len(output) > 0:
                reference_url = str(output[0])
                print(f"Generated reference image URL: {reference_url}")
            # Handle string/other types
            elif output:
                reference_url = str(output)
                print(f"Generated reference image URL: {reference_url}")
            else:
                print("No reference image was generated. Falling back to non-reference approach.")
                reference_url = None
        except Exception as e:
            print(f"Error processing reference image output: {str(e)}")
            print(f"Output type: {type(output)}")
            reference_url = None
            
        # If we got a URL, download and save the reference image
        if reference_url:
            try:
                print(f"Downloading reference image from: {reference_url}")
                reference_image_data = download_image(reference_url)
                
                # Save the reference image
                reference_filepath = output_dir / "reference.jpg"
                with open(reference_filepath, "wb") as f:
                    f.write(reference_image_data)
                
                print(f"Reference image saved to: {reference_filepath}")
                
                # Enhanced face description to maintain consistency
                face_description = f"same face as reference image, identical facial features, same person"
            except Exception as e:
                print(f"Error downloading reference image: {str(e)}")
                reference_image_data = None
                reference_url = None
                
    except Exception as e:
        print(f"Error generating reference image: {str(e)}")
        print("Continuing with non-reference approach.")
        reference_image_data = None
        reference_url = None
    
    # Step 2: Generate additional images using the reference image
    print("\n========== STEP 2: GENERATING SCENE IMAGES ==========")
    
    # Generate each image with variations in scene, pose, and outfit
    for i in range(num_images):
        # Select different settings for each image
        scene = random.choice(scenes)
        pose = random.choice(poses)
        outfit = random.choice(outfits)
        
        # Create the detailed prompt for this specific image
        prompt = create_scene_prompt(traits, gender, primary_ethnicity, ethnicity_example, scene, pose, outfit, face_description)
        
        print(f"\nGenerating image {i+1}/{num_images}")
        print(f"Prompt: {prompt}")
        
        try:
            # If we have a reference image, use the IP-Adapter model as shown in Replicate docs
            if reference_image_data and reference_url:
                print(f"Using IP-Adapter with reference image: {reference_url}")
                
                # Setup inputs exactly as shown in the Replicate docs
                ip_adapter_input = {
                    "seed": random.randint(1, 10000000),  # Random seed for variety but keeping face
                    "image": reference_url,  # URL to the reference image
                    "prompt": prompt,
                    "negative_prompt": "deformed face, unrealistic, cartoon, anime, drawing, painting, sketch, bad anatomy, blurry, low quality, distorted face, bad face, extra limbs, disfigured, ugly, poorly drawn hands, missing limbs, disconnected limbs, malformed hands, blurry, watermark, logo, text"
                }
                
                # Run the model exactly as shown in the docs
                output = replicate.run(ip_adapter_model, input=ip_adapter_input)
                
                # Process the generator output as demonstrated in the docs
                # This is a key difference - we handle the returned generator differently
                output_images = []
                for index, item in enumerate(output):
                    # Create a filename based on profile and image index
                    image_id = f"{i+1:03d}"
                    filename = f"{image_id}.jpg"
                    filepath = output_dir / filename
                    
                    # Save the image directly from the binary data
                    with open(filepath, "wb") as file:
                        file.write(item.read())
                    
                    print(f"Image saved to: {filepath}")
                    output_images.append(filepath)
                
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
                
                # Create a serializable dictionary for this image with enhanced metadata
                image_data = {
                    "image_id": image_id,
                    "profile_id": profile_id,
                    "filepath": str(filepath),
                    "reference_url": reference_url,  # Store reference instead of output URL
                    "prompt": prompt,
                    "scene": scene,
                    "pose": pose,
                    "outfit": random.choice(OUTFIT_COLORS[outfit]),  # Store the specific outfit variation
                    "ethnicity_example": ethnicity_example,
                    "reference_based": True
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
            else:
                # Fallback to original method if reference image generation failed
                output = replicate.run(
                    base_model,
                    input={
                        "prompt": prompt,
                        "negative_prompt": "deformed face, unrealistic, cartoon, anime, drawing, painting, sketch, bad anatomy, blurry, low quality, distorted face, bad face, extra limbs, disfigured, ugly, poorly drawn hands, missing limbs, disconnected limbs, malformed hands, blurry, watermark, logo, text",
                        "width": 768,
                        "height": 1024,
                        "num_outputs": 1,
                        "scheduler": "K_EULER_ANCESTRAL",
                        "num_inference_steps": 30,
                        "guidance_scale": 7.5
                    }
                )
            
                print(f"Output type: {type(output)}")
                
                # Process output for fallback method
                try:
                    # Convert generator to list if it is a generator
                    if hasattr(output, '__next__') or hasattr(output, '__iter__'):
                        output_list = list(output)
                        if output_list:
                            image_url = str(output_list[0])
                            print(f"Generated image URL: {image_url}")
                        else:
                            print("No image was generated (empty generator).")
                            continue
                    # Handle if it's already a list
                    elif isinstance(output, list) and len(output) > 0:
                        image_url = str(output[0])
                        print(f"Generated image URL: {image_url}")
                    # Handle string/other types
                    elif output:
                        image_url = str(output)
                        print(f"Generated image URL: {image_url}")
                    else:
                        print("No image was generated.")
                        continue
                except Exception as e:
                    print(f"Error processing image output: {str(e)}")
                    print(f"Output type: {type(output)}")
                    continue
                
                # Download the image for the fallback method
                try:
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
                        "outfit": random.choice(OUTFIT_COLORS[outfit]),
                        "ethnicity_example": ethnicity_example,
                        "reference_based": False
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
                    print(f"Error saving image {i+1}: {str(e)}")
            
            # Add a short delay between generations to avoid rate limiting
            if i < num_images - 1:
                time.sleep(2)
            
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
                "ethnicity_example": ethnicity_example,
                "ethnicity_traits": ETHNICITY_TRAITS[primary_ethnicity]["traits"],
                "reference_based": reference_image_data is not None,
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
                "ethnicity_example": ethnicity_example,
                "reference_based": reference_image_data is not None,
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
    # Generate profiles with the specified number of images each
    # Default: 1 profile with 8 images
    generate_multiple_profiles(1, 8)