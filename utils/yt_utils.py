
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
    ydl_opts = {'quiet': True, 'extract_flat': True} 
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        # download=False ensures we only grab the metadata
        info_dict = ydl.extract_info(url, download=False)
        
        title = info_dict.get('title')
        channel = info_dict.get('uploader') # 'uploader' usually holds the channel name
        
        # Cache for 24 hours (86400 seconds)
        cache.set(cache_key, {'title': title, 'channel': channel}, timeout=86400)
        
        return title, channel