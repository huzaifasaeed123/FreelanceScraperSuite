import yt_dlp
import os

# Function to download a Facebook video
def download_facebook_video(video_url, output_dir="result"):
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Set output template
    output_template = f'{output_dir}/%(title)s.%(ext)s'
    
    # Configure yt-dlp options
    ytdl_opts = {
        'outtmpl': output_template,
        'format': 'bestvideo+bestaudio/best',  # Best quality
        'merge_output_format': 'mp4',          # Output as MP4
        'noplaylist': True,                    # Download single video, not playlist
        'quiet': False,                        # Show progress
        'no_warnings': False,                  # Show warnings
        'ignoreerrors': True,                  # Continue on download errors
        'geo_bypass': True,                    # Bypass geo-restrictions
    }
    
    # Print status
    print(f"Downloading video from: {video_url}")
    print(f"Output directory: {output_dir}")
    
    # Create downloader instance and download the video
    with yt_dlp.YoutubeDL(ytdl_opts) as ydl:
        try:
            info = ydl.extract_info(video_url, download=True)
            # Get the downloaded file path
            if info and 'title' in info:
                file_path = os.path.join(output_dir, f"{info['title']}.mp4")
                print(f"Download completed: {file_path}")
                return file_path
            else:
                print("Download completed but couldn't determine file path")
                return None
        except Exception as e:
            print(f"Error downloading video: {e}")
            return None

# Example usage
if __name__ == "__main__":
    # Replace with your Facebook video URL
    video_url = "https://www.facebook.com/watch?v=1758188051687583"
    
    # Download the video
    downloaded_file = download_facebook_video(video_url)
    
    if downloaded_file:
        print(f"Video saved to: {downloaded_file}")
    else:
        print("Failed to download video")