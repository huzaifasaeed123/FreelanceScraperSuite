import yt_dlp
import os
import requests
import logging
import time
import re
import json
# Helper to clean up caption content

# Step 1: Download Facebook video with fixed name
def download_facebook_video(video_url, output_dir="result"):
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

    print(f"Downloading video from: {video_url}")
    with yt_dlp.YoutubeDL(ytdl_opts) as ydl:
        try:
            info = ydl.extract_info(video_url, download=True)
            description=info.get("description",'')
            print(f"Download completed: {output_path}")
            return output_path, description
        except Exception as e:
            print(f"Error downloading video: {e}")
            return None, None

# Step 2: Upload to Catbox
def upload_to_catbox(filepath):
    try:
        with open(filepath, 'rb') as f:
            r = requests.post('https://catbox.moe/user/api.php',
                              data={'reqtype': 'fileupload'},
                              files={'fileToUpload': f})
        if r.status_code == 200:
            return r.text.strip()
        else:
            print("Upload failed:", r.text)
            return None
    except Exception as e:
        print(f"Error uploading to Catbox: {e}")
        return None

# Step 3: Send file via WhatsApp
def sendmsgurl(thenumber, captions, urlfile, filename, instance, api):
    url = f"https://7105.api.greenapi.com/waInstance{instance}/sendFileByUrl/{api}"
    chatid = f"{thenumber}@c.us"
    payload = {
        "chatId": chatid,
        "urlFile": urlfile,
        "fileName": filename,
        "caption": captions
    }
    headers = {'Content-Type': 'application/json'}
    response = requests.post(url, json=payload, headers=headers)
    print(f"WhatsApp API response: {response.text}")



# Main process
if __name__ == "__main__":
    video_url = "https://www.facebook.com/61556572291686/videos/1542573089757961/"  # Replace with your link
    phone_number = "923471729745"
    instance_id = "7105205743"
    api_key = "3029b532f92048e0bbfa4adcb6aed55574b994edae144847a4"

    downloaded_file, description = download_facebook_video(video_url)

    if downloaded_file:
        uploaded_url = upload_to_catbox(downloaded_file)
        if uploaded_url:
            print("Uploaded file URL:", uploaded_url)

            sendmsgurl(
                thenumber=phone_number,
                captions=(description + "\n" if description else "") + "",
                urlfile=uploaded_url,
                filename=os.path.basename(downloaded_file),
                instance=instance_id,
                api=api_key
            )

            try:
                os.remove(downloaded_file)
                print(f"Deleted local file: {downloaded_file}")
            except Exception as e:
                print(f"Error deleting file: {e}")
        else:
            print("Failed to upload the video.")
    else:
        print("Video download failed.")
#Testing For Image Direct Upload
# sendmsgurl(
#                 thenumber=923471729745,
#                 captions="jghg",
#                 urlfile="https://scontent.fisb5-2.fna.fbcdn.net/v/t15.5256-10/497915012_4194569750776220_7030896294187867369_n.jpg?stp=dst-jpg_s960x960_tt6&_nc_cat=109&ccb=1-7&_nc_sid=7965db&_nc_ohc=_oiwZpFcE9kQ7kNvwFqBh3A&_nc_oc=AdlOWmSLkwSDpQFL12WXasWW5Onf3MmFPzjvCtuzRha7tUg4f1y8RKtmxACY4BiUchw&_nc_zt=23&_nc_ht=scontent.fisb5-2.fna&_nc_gid=ic-C6d9IzjnHMGGGiw1Zzw&oh=00_AfKolg_BpcwO6BacDt1HG1WRFkxz9oXQUT86DZQJCUBunQ&oe=6829D2E6",
#                 filename="huzada.jpg",
#                 instance=7105205743,
#                 api="3029b532f92048e0bbfa4adcb6aed55574b994edae144847a4"
#     )
