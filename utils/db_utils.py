from channels.db import database_sync_to_async
from django.core.cache import cache
from app.models import Chat, Message
import sys
import os

# Ensure we can import yt_chatbot
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from chatbot.yt_chatbot import extract_video_id

@database_sync_to_async
def get_or_create_chat(user, url, chat_id=None, title="New Chat"):
    video_id = extract_video_id(url)
    if chat_id:
        try:
            return Chat.objects.get(id=chat_id, user=user)
        except Chat.DoesNotExist:
            pass # fallback to creating new if invalid
    
    return Chat.objects.create(
        user=user,
        title=title,
        yt_video_url=url,
        yt_video_id=video_id
    )

@database_sync_to_async
def get_chat_history(chat_id):
    if not chat_id:
        return []
        
    cache_key = f"chat_history_{chat_id}"
    history = cache.get(cache_key)
    
    if history is not None:
        return history
        
    # Cache miss: fetch from PostgreSQL
    messages = Message.objects.filter(chat_id=chat_id).order_by("created_at")
    history = [{"role": msg.role, "content": msg.content} for msg in messages]
    
    # Save to Redis
    cache.set(cache_key, history, timeout=86400) # cache for 1 day
    return history

@database_sync_to_async
def save_message(chat, role, content):
    msg = Message.objects.create(
        chat=chat,
        role=role,
        content=content
    )
    
    # Update Redis Cache
    cache_key = f"chat_history_{chat.id}"
    history = cache.get(cache_key)
    if history is not None:
        history.append({"role": role, "content": content})
        cache.set(cache_key, history, timeout=86400)
        
    return msg
