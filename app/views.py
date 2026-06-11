from django.shortcuts import render

# Create your views here.

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from asgiref.sync import async_to_sync
from rest_framework.pagination import PageNumberPagination
from .models import CustomUser, Chat, Message
from .serializers import CustomUserSerializer, ChatSerializer, MessageSerializer
from .tasks import generate_knowledge_graph_task, process_video_task

from django.core.cache import cache

# Chatbot imports
import chatbot.yt_chatbot as yt_chatbot
from chatbot.chatbot_utils import extract_video_id
from chatbot.knowledge_graph import generate_knowledge_graph
from utils.db_utils import get_chat_history
from utils.yt_utils import get_youtube_info


from rest_framework.throttling import UserRateThrottle, AnonRateThrottle
from rest_framework_simplejwt.views import TokenObtainPairView

# For Google OAuth2
from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter
from allauth.socialaccount.providers.oauth2.client import OAuth2Client
from dj_rest_auth.registration.views import SocialLoginView


class CustomTokenObtainPairView(TokenObtainPairView):
    throttle_classes = [AnonRateThrottle]

class RegisterView(APIView):
    def post(self, request):
        serializer = CustomUserSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            return Response({"message": "User created successfully"}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# Google Login View
class GoogleLogin(SocialLoginView):
    adapter_class = GoogleOAuth2Adapter
    callback_url = "http://localhost:5173" # Your React app URL
    client_class = OAuth2Client

class CreateChatView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        chats = Chat.objects.filter(user=request.user)
        serializer = ChatSerializer(chats, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = ChatSerializer(data=request.data)
        if serializer.is_valid():
            url = serializer.validated_data.get("yt_video_url")
            video_id = extract_video_id(url)
            title = "New chat"
            channel = ""
            try:
                title, channel = get_youtube_info(url)
            except Exception as e:
                return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
                
            title = f"{title} | {channel}"
            
            # Save the chat with 'processing' status
            chat = serializer.save(user=request.user, title=title, yt_video_url=url, yt_video_id=video_id, status='processing')
            
            # Trigger background Celery task
            
            process_video_task.delay(str(chat.id), video_id)
            
            return Response({
                "chat_id": str(chat.id), 
                "message": "Chat created and processing in background",
                "status": "processing"
            }, status=status.HTTP_201_CREATED)
            
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ChatMessagePagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100

class ChatMessagesAPIView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]

    def get(self, request, chat_id):
        messages = Message.objects.filter(
            chat_id=chat_id,
            chat__user=request.user
        ).order_by("-created_at")

        paginator = ChatMessagePagination()
        result_page = paginator.paginate_queryset(messages, request)
        serializer = MessageSerializer(result_page, many=True)
        return paginator.get_paginated_response(serializer.data)


class ChatBotView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        url = request.data.get("url")
        query = request.data.get("query")
        chat_id = request.data.get("chat_id")
        if not url or not query:
            return Response(
                {"error": "Both 'url' and 'query' fields are required."}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        video_id = extract_video_id(url)
        if chat_id:
            try:
                chat = Chat.objects.get(id=chat_id, user=request.user)
            except Chat.DoesNotExist:
                chat = Chat.objects.create(user=request.user, title="New Chat", yt_video_url=url, yt_video_id=video_id)
        else:
            chat = Chat.objects.create(user=request.user, title="New Chat", yt_video_url=url, yt_video_id=video_id)

        # Get history from DB (or we can use db_utils but we are in a synchronous view here)
        # Using async_to_sync with get_chat_history from db_utils is perfect since it handles Redis.
        
        raw_history = async_to_sync(get_chat_history)(chat.id)

        Message.objects.create(chat=chat, role="user", content=query)
        # Also append the user message to cache manually since save_message from db_utils isn't used here
        from django.core.cache import cache
        cache_key = f"chat_history_{chat.id}"
        history_in_cache = cache.get(cache_key)
        if history_in_cache is not None:
            history_in_cache.append({"role": "user", "content": query})
            cache.set(cache_key, history_in_cache, timeout=86400)

        try:
            result = async_to_sync(yt_chatbot.process_chat_request)(url, query, raw_history)
            
            Message.objects.create(chat=chat, role="assistant", content=result)
            if history_in_cache is not None:
                history_in_cache.append({"role": "assistant", "content": result})
                cache.set(cache_key, history_in_cache, timeout=86400)

            return Response({"answer": result, "chat_id": str(chat.id)}, status=status.HTTP_200_OK)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"error": "An internal error occurred: " + str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class ChatStatusAPIView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request, chat_id):
        try:
            chat = Chat.objects.get(id=chat_id, user=request.user)
            return Response({"status": chat.status})
        except Chat.DoesNotExist:
            return Response({"error": "Chat not found"}, status=status.HTTP_404_NOT_FOUND)


class ChatDeleteAPIView(APIView):
    permission_classes = [IsAuthenticated]
    
    def delete(self, request, chat_id):
        try:
            chat = Chat.objects.get(id=chat_id, user=request.user)
            chat.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Chat.DoesNotExist:
            return Response({"error": "Chat not found"}, status=status.HTTP_404_NOT_FOUND)

class KnowledgeGraphView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        url = request.data.get("url")
        if not url:
            return Response({"error": "URL is required."}, status=status.HTTP_400_BAD_REQUEST)

        video_id = extract_video_id(url)
        if not video_id:
            return Response({"error": "Invalid YouTube URL."}, status=status.HTTP_400_BAD_REQUEST)
        
        cache_key = "kg_"+video_id
        kg_data = cache.get(cache_key)
        
        if kg_data:
            if isinstance(kg_data, dict) and 'status' in kg_data:
                if kg_data['status'] == 'completed':
                    return Response(kg_data['data'], status=status.HTTP_200_OK)
                elif kg_data['status'] in ['processing', 'error']:
                    return Response({"task_id": cache_key, "status": kg_data['status']}, status=status.HTTP_202_ACCEPTED)
            else:
                # Legacy cache format
                return Response(kg_data, status=status.HTTP_200_OK)
                
        # Start celery task
        cache.set(cache_key, {'status': 'processing'}, timeout=86400)
        
        generate_knowledge_graph_task.delay(video_id, cache_key)
        
        return Response({"task_id": cache_key, "status": "processing"}, status=status.HTTP_202_ACCEPTED)


class KnowledgeGraphStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, task_id):
        data = cache.get(task_id)
        if not data:
            return Response({"error": "Task not found or expired"}, status=status.HTTP_404_NOT_FOUND)
            
        if isinstance(data, dict):
            if data.get('status') == 'completed':
                return Response({"status": "completed", "data": data['data']}, status=status.HTTP_200_OK)
            elif data.get('status') == 'error':
                return Response({"status": "error", "error": data.get('error', 'Unknown error')}, status=status.HTTP_400_BAD_REQUEST)
            else:
                return Response({"status": data.get('status', 'processing')}, status=status.HTTP_200_OK)
        else:
            # Legacy cache
            return Response({"status": "completed", "data": data}, status=status.HTTP_200_OK)
