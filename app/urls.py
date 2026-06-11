
from django.urls import path
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenBlacklistView
)

from . import views
urlpatterns = [
    path('auth/login/', views.CustomTokenObtainPairView.as_view(), name='login'),
    # Google OAuth2
    path('auth/google/', views.GoogleLogin.as_view(), name='google_login'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('auth/register/', views.RegisterView.as_view(), name='register'),
    path('auth/logout/', TokenBlacklistView.as_view(), name='logout'),
    path('chat/create/', views.CreateChatView.as_view(), name='chat_create'),
    path('chat/', views.ChatBotView.as_view(), name='chat'),
    path('chat/<uuid:chat_id>/messages/', views.ChatMessagesAPIView.as_view(), name='chat_messages'),
    path('chat/<uuid:chat_id>/status/', views.ChatStatusAPIView.as_view(), name='chat_status'),
    path('chat/<uuid:chat_id>/', views.ChatDeleteAPIView.as_view(), name='chat_delete'),
    path('chat/knowledge-graph/', views.KnowledgeGraphView.as_view(), name='knowledge_graph'),
    path('chat/knowledge-graph/status/<str:task_id>/', views.KnowledgeGraphStatusView.as_view(), name='knowledge_graph_status'),
]
