
from urllib.parse import urlparse, parse_qs
# from youtube_transcript_api import YouTubeTranscriptApi
# from youtube_transcript_api.proxies import GenericProxyConfig
from django.core.cache import cache
import asyncio
import yt_dlp
import httpx
import aiohttp
import os
from dotenv import load_dotenv
load_dotenv()

def extract_video_id(url: str) -> str:
    parsed_url = urlparse(url)
    if parsed_url.query:
        query_params = parse_qs(parsed_url.query)
        if "v" in query_params:
            return query_params["v"][0]
    path_parts = parsed_url.path.strip("/").split("/")
    if path_parts:
        return path_parts[-1]
    return None



async def get_youtube_transcript(video_id):
    cache_key = f"transcript_{video_id}"
    transcript = cache.get(cache_key)
    
    if transcript:
        return transcript

    # It's best practice to store API keys in environment variables
    api_key = os.getenv("TRANSCRIPT_API_KEY")
    
    # Constructing the endpoint. 
    # Note: The parameter is called 'video_url', so we pass the full YouTube URL.
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    api_endpoint = f"https://transcriptapi.com/api/v2/youtube/transcript?video_url={video_url}"
    
    headers = {
        "Authorization": f"Bearer {api_key}"
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(api_endpoint, headers=headers) as response:
                # Raise an exception if the API returns a 4xx or 5xx error
                response.raise_for_status() 
                
                # Parse the JSON response
                data = await response.json()
                
                # Validate that the expected data is in the response
                if "transcript" not in data:
                    raise ValueError("Unexpected API response structure: 'transcript' key missing.")

                # Extract the 'text' from each dictionary in the transcript list
                # and join them together, maintaining your original format
                transcript_text = "\n ".join([snippet["text"] for snippet in data["transcript"]])
                
                # Set in cache and return
                cache.set(cache_key, transcript_text, timeout=86400)
                return transcript_text

    except aiohttp.ClientError as e:
        # Handles network issues, bad requests, etc.
        raise ValueError(f"Network error while fetching transcript: {e}")
    except Exception as e:
        # Fallback for any other parsing or unexpected errors
        raise ValueError(f"Could not fetch transcript: {e}")

# async def get_youtube_transcript(video_id):
#     cache_key = f"transcript_{video_id}"
#     transcript = cache.get(cache_key)
#     if transcript:
#         return transcript
#     try:
#         transcript_list = await asyncio.to_thread(
#             lambda: YouTubeTranscriptApi().fetch(video_id, languages=['en', "hi", 'bn'])
#         )
        
#         transcript = "\n ".join([snippet.text for snippet in transcript_list])
        
#         cache.set(cache_key, transcript, timeout=86400)
#         return transcript
#     except Exception as e:
#         raise ValueError(f"Could not fetch transcript: {e}")



# async def get_youtube_transcript(video_id):
#     cache_key = f"transcript_{video_id}"
#     transcript = cache.get(cache_key)
#     if transcript:
#         return transcript

#     # 1. Define the local Tor daemon as the proxy gateway
#     tor_proxy = GenericProxyConfig(
#         http_url="socks5://127.0.0.1:9050",
#         https_url="socks5://127.0.0.1:9050"
#     )

#     # 2. Implement a retry loop for Tor stability
#     for attempt in range(3):
#         try:
#             # 3. Pass the proxy config into the API instance
#             transcript_list = await asyncio.to_thread(
#                 lambda: YouTubeTranscriptApi(proxy_config=tor_proxy).fetch(
#                     video_id, 
#                     languages=['en', "hi", 'bn']
#                 )
#             )
            
#             transcript = "\n ".join([snippet.text for snippet in transcript_list])
            
#             cache.set(cache_key, transcript, timeout=86400)
#             return transcript
            
#         except Exception as e:
#             if attempt == 2:  # If the 3rd attempt fails, raise the error
#                 raise ValueError(f"Could not fetch transcript after 3 attempts: {e}")
            
#             # Wait 2 seconds before trying again to allow the connection to reset
#             await asyncio.sleep(2)




# async def get_youtube_transcript(video_id):
#     cache_key = f"transcript_{video_id}"
#     transcript = cache.get(cache_key)
#     if transcript:
#         return transcript

#     def extract_subtitle_info():
#         ydl_opts = {
#             'skip_download': True,
#             'writesubtitles': True,
#             'writeautomaticsub': True,
#             'subtitleslangs': ['en', 'hi', 'bn'],
#             'quiet': True,
#         }
#         with yt_dlp.YoutubeDL(ydl_opts) as ydl:
#             return ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)

#     try:
#         # Run the synchronous yt-dlp extraction in a thread
#         info = await asyncio.to_thread(extract_subtitle_info)
        
#         # Check if requested subtitles exist
#         if 'requested_subtitles' in info and info['requested_subtitles']:
#             # Grab the English track (or fallback to whatever is available)
#             sub_track = info['requested_subtitles'].get('en') or list(info['requested_subtitles'].values())[0]
#             sub_url = sub_track['url']
            
#             # Fetch the raw .vtt or .json3 subtitle file directly from Google's CDN
#             async with httpx.AsyncClient() as client:
#                 response = await client.get(sub_url)
#                 transcript_raw = response.text
                
#                 # Note: You may need a quick regex or parser here to strip out 
#                 # the timestamps from the raw VTT format to get clean text for your RAG.
                
#                 return transcript_raw
#         else:
#             raise ValueError("No subtitles found for this video.")
            
#     except Exception as e:
#         raise ValueError(f"yt-dlp extraction failed: {e}")