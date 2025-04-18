import replicate
import os
import requests
os.environ["REPLICATE_API_TOKEN"] = "r8_Kq95WuzQtpq3pR3bSaWeFrbeTxaUMne2PcpBP"

input = {
    "seed": 42,
    "image": "https://replicate.delivery/pbxt/JqifieOm5VA07pzpBWY4BNr2cf9YpQRjbGT3wBYFx9ANENSf/ai_face2.png",
    "prompt": "photo of a beautiful girl wearing casual shirt in a garden"
}

output = replicate.run(
    "lucataco/ip_adapter-sdxl-face:226c6bf67a75a129b0f978e518fed33e1fb13956e15761c1ac53c9d2f898c9af",
    input=input
)
for index, item in enumerate(output):
    with open(f"output_{index}.png", "wb") as file:
        file.write(item.read())
#=> output_0.png written to disk