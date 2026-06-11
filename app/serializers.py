
from .models import *
from rest_framework import serializers

class CustomUserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    class Meta:
        model = CustomUser
        fields = "__all__"

    def create(self, validated_data):
        return CustomUser.objects.create_user(**validated_data)

class ChatSerializer(serializers.ModelSerializer):
    # url = serializers.CharField(source='yt_video_url')

    class Meta:
        model = Chat
        fields = ["id", "title", "yt_video_url", "yt_video_id", "status"]
        read_only_fields = ["id", "yt_video_id", "status"]

class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = ['id', 'role', 'content', 'created_at']