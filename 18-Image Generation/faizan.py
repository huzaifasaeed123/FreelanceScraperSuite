import replicate
import requests
import os
# Your Replicate API Token (Replace with your token)
# API_TOKEN = "r8_OaUhmPKppKQG9zblfcevLVTJHwaDjnc11jg16"
os.environ["REPLICATE_API_TOKEN"] = "r8_Kq95WuzQtpq3pR3bSaWeFrbeTxaUMne2PcpBP"
# Set up the model on Replicate
model = "stability-ai/stable-diffusion-2"  # Replace with the appropriate model if using something else

# The detailed prompt we generated for the image
prompt = """
Create an image of a young adult (around 28 years old, 170cm tall, weighing around 65kg) who is female with a Sub-Saharan African ethnicity. She has a slender physique with a muscular build and a confident expression. Her skin is smooth and deep brown, and her hair is styled in a natural curly Afro.

Facial Features: Her face is oval-shaped with a slight angular jawline, full lips with a natural pink hue, and almond-shaped dark brown eyes. She has slightly arched eyebrows and a soft, warm smile.
Outfit: She is wearing casual jeans and a t-shirt, and her style is comfortable yet chic.
Scene: She is standing casually in a park with trees and grass in the background, illuminated by soft, natural sunlight from the golden hour.
Lighting & Mood: The lighting should capture the soft glow of the late afternoon sun, with natural, realistic details—no professional photography, just a candid moment like a smartphone photo. Her expression is relaxed and approachable.
"""

# Call the API to generate the image
def generate_image(prompt):
    output = replicate.run(
        model,
        input={
            "prompt": prompt,
            "negative_prompt": "cropped image, close-up, cut off, partial body, zoomed in, deformed, unrealistic, cartoon, anime, drawing, painting, sketch, bad anatomy, blurry, low quality",
            "width": 768,
            "height": 1024,
            "num_outputs": 1,
            "scheduler": "K_EULER_ANCESTRAL",  # Example scheduler
            "num_inference_steps": 30,  # Adjust steps for quality
            "guidance_scale": 7.5  # Adjust guidance scale for better adherence to the prompt
        }
    )

    # Get the output URL of the generated image
    image_url = output[0]  # Assuming the output is a URL of the generated image
    print(f"Image generated: {image_url}")

    # Download the image
    response = requests.get(image_url)
    if response.status_code == 200:
        with open("generated_image.jpg", "wb") as file:
            file.write(response.content)
        print("Image saved as 'generated_image.jpg'")
    else:
        print(f"Failed to download image: {response.status_code}")

# Run the function to generate the image
generate_image(prompt)