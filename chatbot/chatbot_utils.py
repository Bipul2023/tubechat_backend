
from urllib.parse import urlparse, parse_qs
from youtube_transcript_api import YouTubeTranscriptApi
from django.core.cache import cache
import asyncio

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
    try:
        transcript_list = await asyncio.to_thread(
            lambda: YouTubeTranscriptApi().fetch(video_id, languages=['en', "hi", 'bn'])
        )
        
        transcript = "\n ".join([snippet.text for snippet in transcript_list])
        
        cache.set(cache_key, transcript, timeout=86400)
        return transcript
    except Exception as e:
        raise ValueError(f"Could not fetch transcript: {e}")