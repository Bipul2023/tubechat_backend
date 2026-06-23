
import yt_dlp
import hashlib
from django.core.cache import cache

def get_youtube_info(url):
    cache_key = f"yt_info_{hashlib.md5(url.encode()).hexdigest()}"
    cached_info = cache.get(cache_key)
    
    if cached_info:
        return cached_info.get('title'), cached_info.get('channel')

    # 'quiet': True prevents yt-dlp from printing console logs
    # 'extract_flat': True extracts metadata without downloading the video
    ydl_opts = {'quiet': True, 'extract_flat': True,  'cookiefile': 'cookies.txt'} 
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        # download=False ensures we only grab the metadata
        info_dict = ydl.extract_info(url, download=False)
        
        title = info_dict.get('title')
        channel = info_dict.get('uploader') # 'uploader' usually holds the channel name
        
        # Cache for 24 hours (86400 seconds)
        cache.set(cache_key, {'title': title, 'channel': channel}, timeout=86400)
        
        return title, channel

# import socket
# import sys

# def verify_tor_on_startup(host="127.0.0.1", port=9050):
#     """Run this exactly once when the server or worker initializes."""
#     print("Checking dependency: Tor Daemon...")
#     try:
#         with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
#             s.settimeout(1.5)
#             s.connect((host, port))
#             print("✅ Tor Daemon is connected and listening on port 9050.")
#             return True
#     except (socket.timeout, ConnectionRefusedError):
#         sys.exit(
#             "\n❌❌[CRITICAL ERROR] Tor daemon is NOT running or listening on port 9050.\n"
#             "The application cannot start without it.\n"
#             "Please run:\n"
#             "  sudo apt update && sudo apt install tor -y\n"
#             "  sudo systemctl start tor\n"
#         )