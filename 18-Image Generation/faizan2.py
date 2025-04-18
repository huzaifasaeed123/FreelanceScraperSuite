import os
import replicate
import requests
from pathlib import Path

# Set the API token
os.environ["REPLICATE_API_TOKEN"] = "r8_Kq95WuzQtpq3pR3bSaWeFrbeTxaUMne2PcpBP"
# os.environ["REPLICATE_API_TOKEN1"] = "r8_ZhohKjVTz68Y4tmabHSCobdklzARPws3ZvIgz"

# Create output directory if it doesn't exist
output_dir = Path("generated_image")
output_dir.mkdir(exist_ok=True)

def generate_single_image():
    """Generate a single image with the specified prompt"""
    
    # The detailed prompt describing the person
    prompt = """
Generate a hyper-realistic image of a female person, aged 28 years old, with light fair skin that has warm undertones. She stands confidently in a natural, slightly posed stance, exuding elegance and grace.

### Face Details:
- Hair: She has long, voluminous hair that cascades down her back in soft, bouncy waves. The hair color is a deep, rich chestnut brown with golden caramel highlights woven through the length, catching the light in a natural shine. The hair is styled in a relaxed, side-swept style with gentle waves that frame her face softly. The ends of her hair curl slightly, and there’s a slight tousled, effortless look to it.
- Eyes: Her eyes are large, almond-shaped, and mesmerizing with a striking emerald green color. The sclera is bright, and the iris has subtle golden flecks near the pupils. Her eyelashes are long, dark, and voluminous, giving her a naturally wide-eyed appearance. Her eyelids are smooth with faint, soft creases. Her eyebrows are thick, dark brown, and slightly arched, giving her a soft yet defined expression.
- Nose: She has a well-defined, straight nose with a delicate bridge. The tip is soft and slightly rounded, with perfectly proportioned nostrils. The nose blends harmoniously with her other features, neither too prominent nor too subtle.
- Mouth: Her lips are full and plump, with a natural pinkish hue. The upper lip has a well-defined cupid’s bow, while the lower lip is fuller and gently curved. She’s smiling softly, with the corners of her mouth slightly turned upward, exuding warmth and charm.
- Cheeks: Her cheekbones are high and sculpted, giving her face a structured, yet soft, look. There is a natural flush on her cheeks, as though she’s just walked in from the cold, giving her a healthy, radiant glow.
- Chin and Jawline: Her chin is softly rounded, with no sharp angles. Her jawline is elegant, with a gentle curve leading to the neck, which gives her a smooth, balanced appearance.
- Skin Texture: Her skin is flawless with a smooth, porcelain-like texture, completely free of blemishes or imperfections. There is a slight natural sheen to her skin, making her appear youthful and fresh. Her complexion is evenly toned with a warm undertone, and a healthy glow accentuates her features.

### Body Features:
- Neck: Her neck is long and graceful, with a slight natural curve. The skin on her neck is smooth, and the collarbones are subtly visible, giving her a delicate and feminine silhouette.
- Shoulders and Upper Body: Her shoulders are narrow yet well-proportioned, tapering gently down to her torso. Her upper arms are slender with slight muscle tone visible in the forearms, and her skin is soft, smooth, and glowing. 
- Bust and Torso: She has a well-balanced, moderate bust that fits proportionally with her frame. The top of her chest has a slight curvature that is not too prominent but provides a soft, natural femininity. Her waist is slim, with a subtle hourglass figure that enhances her body’s curves. The slight curve of her waist blends smoothly into her hips.
- Waist and Abdomen: Her waist is clearly defined, narrowing gently but subtly. The abdomen is flat, with smooth, unblemished skin. There’s a slight natural definition along the sides of her torso, revealing a healthy and active lifestyle.
- Hips: Her hips are proportionate to her waist, with soft curves that suggest a natural, feminine silhouette. There is a subtle curve where her hips meet her thighs, giving her a balanced, athletic shape. 
- Legs: Her legs are long and slender, with a healthy muscle definition visible in her thighs and calves. The skin on her legs is smooth and even-toned, and the overall shape is athletic yet elegant. Her knees are soft and gently rounded.
- Feet: Her feet are small and delicate with well-shaped toes, and the skin is smooth, giving an overall graceful appearance. She is standing barefoot, with one foot slightly forward, allowing her posture to appear natural and effortless.

### Hands and Arms:
- Hands: Her hands are elegant and delicate, with long, slender fingers. Her nails are painted with a soft nude polish, and the skin on her hands is smooth with no visible wrinkles. She is casually resting one hand on her hip, while the other hangs by her side, relaxed and graceful.
- Arms: Her arms are slim with subtle muscle definition in the upper arms and forearms. The skin is smooth and even-toned. The veins are slightly visible beneath the skin, showing her athletic build.

### Clothing and Style:
- Outfit: She’s dressed in a stylish, tailored white blouse made of soft, luxurious fabric that fits perfectly, cinching slightly at the waist. The blouse has delicate lace accents at the cuffs, giving it a touch of vintage elegance. She wears high-waisted black trousers that flow naturally down to her ankles, accentuating her slender legs. The trousers fit her perfectly, with a slight flare at the bottom. Her outfit is polished yet casual, ideal for a chic, modern look.
- Footwear: She’s wearing simple, elegant black flats that complement her outfit, maintaining the sleek and minimalistic aesthetic.

### Lighting and Environment:
- The lighting is soft and natural, coming from the left side. It creates soft shadows on her body and face, enhancing her features. The light is warm, casting a subtle glow on her skin, creating a natural, flawless finish.
- Background: The background is softly blurred with the suggestion of a bright, green park filled with distant trees. There is a calm and peaceful ambiance with soft bokeh lights in the distance, giving the scene a serene, elegant feel.
- Posture and Expression: She is standing upright, with a confident yet relaxed stance. Her body is angled slightly to the side, but her face is directed towards the viewer, giving the photo a direct, approachable look. She has a gentle, knowing smile, exuding both confidence and warmth.

*Camera Settings*: The photo is taken in a 4:3 aspect ratio, resembling a candid, real-life portrait taken with a DSLR camera. The composition is balanced, focusing on the upper body and face, with a soft focus effect that highlights the person in the foreground.
"""
    
    # Add specification for full-body framing
    full_prompt = prompt + "\nFull head-to-toe framing, zoomed-out, full-body shot with 4:3 aspect ratio."
    
    # Define negative prompt to avoid common issues
    negative_prompt = "cropped image, close-up, cut off, partial body, zoomed in, deformed, unrealistic, cartoon, anime, drawing, painting, sketch, bad anatomy, blurry, low quality"
    
    print("Generating image with prompt:")
    print(full_prompt)
    print("\nNegative prompt:")
    print(negative_prompt)
    
    # SDXL model on Replicate
    model = "stability-ai/sdxl:c221b2b8ef527988fb59bf24a8b97c4561f1c671f73bd389f866bfb27c061316"
    
    try:
        # Generate the image
        print("\nStarting image generation...")
        output = replicate.run(
            model,
            input={
                "prompt": full_prompt,
                "negative_prompt": negative_prompt,
                "width": 768,
                "height": 1024,
                "num_outputs": 1,
                "scheduler": "K_EULER_ANCESTRAL",
                "num_inference_steps": 30,
                "guidance_scale": 7.5
            }
        )
        
        # Get the image URL
        if not output:
            print("No output received from the model")
            return None
        
        if isinstance(output, list) and len(output) > 0:
            image_url = output[0]
        else:
            image_url = output
        
        print(f"Image generated successfully. URL: {image_url}")
        
        # Download the image
        response = requests.get(image_url)
        if response.status_code != 200:
            print(f"Failed to download image: {response.status_code}")
            return None
        
        # Save the image
        filename = "african_female_park.jpg"
        filepath = output_dir / filename
        
        with open(filepath, "wb") as f:
            f.write(response.content)
        
        print(f"Image saved to: {filepath}")
        return filepath
        
    except Exception as e:
        print(f"Error generating image: {str(e)}")
        return None

if __name__ == "__main__":
    result = generate_single_image()
    if result:
        print(f"Image generation complete! The image is saved at: {result}")
    else:
        print("Image generation failed.")