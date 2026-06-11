from celery import shared_task
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from .models import Chat
import chatbot.yt_chatbot as yt_chatbot
from chatbot.knowledge_graph import generate_knowledge_graph
from django.core.cache import cache

@shared_task
def process_video_task(chat_id, video_id):
    """
    Background task to process YouTube video transcript and create embeddings.
    Notifies the frontend via WebSocket when complete.
    """
    try:
        chat = Chat.objects.get(id=chat_id)
        
        # 1. Generate embeddings synchronously using async_to_sync
        async_to_sync(yt_chatbot.aget_or_create_vectorstore)(video_id)
        
        # 2. Update database status
        chat.status = 'ready'
        chat.save()
        
    except Exception as e:
        # On failure, mark status as error and notify
        try:
            chat = Chat.objects.get(id=chat_id)
            chat.status = 'error'
            chat.save()
        except Exception:
            pass
        raise e

@shared_task
def generate_knowledge_graph_task(video_id, cache_key):
    
    try:
        graph_data = async_to_sync(generate_knowledge_graph)(video_id)
        cache.set(cache_key, {'status': 'completed', 'data': graph_data}, timeout=86400)
    except Exception as e:
        cache.set(cache_key, {'status': 'error', 'error': str(e)}, timeout=86400)
        print(f"Error generating knowledge graph in background: {str(e)}")
