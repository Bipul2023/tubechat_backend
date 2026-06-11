import json
import asyncio
from channels.generic.websocket import AsyncWebsocketConsumer
from django.core.cache import cache
import chatbot.yt_chatbot as yt_chatbot
from utils.db_utils import get_or_create_chat, save_message, get_chat_history
import traceback

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope.get('user')
        if not self.user or self.user.is_anonymous:
            await self.close()
            return
            
        self.group_name = f"user_{self.user.id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def chat_status(self, event):
        """Handler for Celery task status updates"""
        await self.send(text_data=json.dumps({
            "type": "status",
            "chat_id": event["chat_id"],
            "status": event["status"],
            "message": event.get("message", "")
        }))

    async def receive(self, text_data):
        try:
            # --- Throttling Logic ---
            # Limit user to 15 requests per minute
            user_id = self.user.id
            cache_key = f"ws_throttle_{user_id}"
            
            requests = await cache.aget(cache_key, 0)
            if requests >= 15:
                await self.send(text_data=json.dumps({"error": "Rate limit exceeded. Please wait before sending more messages."}))
                return
                
            if requests == 0:
                await cache.aset(cache_key, 1, timeout=60)
            else:
                await cache.aincr(cache_key)
            # ------------------------

            text_data_json = json.loads(text_data)
            url = text_data_json.get('url')
            query = text_data_json.get('query')
            chat_id = text_data_json.get('chat_id')
            if not url or not query:
                await self.send(text_data=json.dumps({"error": "Both 'url' and 'query' fields are required."}))
                return

            # Database Logic
            chat = await get_or_create_chat(self.user, url, chat_id)
            
            # Fetch history from Redis/DB instead of frontend payload
            raw_history = await get_chat_history(chat.id)
            
            await save_message(chat, "user", query)

            ai_response_chunks = []
            async for chunk in yt_chatbot.stream_chat_request(url, query, raw_history):
                ai_response_chunks.append(chunk)
                await self.send(text_data=json.dumps({"chunk": chunk}))
                
            full_ai_response = "".join(ai_response_chunks)
            await save_message(chat, "assistant", full_ai_response)

            await self.send(text_data=json.dumps({
                "done": True, 
                "chat_id": str(chat.id)
            }))

        except Exception as e:
            # 3. FORCE THE ERROR INTO THE TERMINAL
            print("\n" + "="*50)
            print(f"🔥 WEBSOCKET CRASHED: {e}")
            traceback.print_exc() # This prints the exact file and line number!
            print("="*50 + "\n")
            
            # 4. Optional: Send the error back to the frontend so your UI doesn't hang
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': f"Server Error: {str(e)}"
            }))
