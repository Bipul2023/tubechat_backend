from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
import uuid
from .managers import CustomUserManager
from app.baseModel import BaseModel

class CustomUser(AbstractBaseUser, PermissionsMixin, BaseModel):
    
    email = models.EmailField(_("email address"), unique=True)
    first_name = models.CharField(_("first name"), max_length=150, blank=True)
    last_name = models.CharField(_("last name"), max_length=150, blank=True)
    phone_number = models.CharField(_("phone number"), max_length=15, blank=True)
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    date_joined = models.DateTimeField(default=timezone.now)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = CustomUserManager()

    def __str__(self):
        return self.email


class Chat(BaseModel):

    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="chats"
    )

    title = models.CharField(max_length=255, blank=True)
    yt_video_url = models.CharField(max_length=255)
    yt_video_id = models.CharField(max_length=255)
    status = models.CharField(
        max_length=20, 
        choices=[('processing', 'Processing'), ('ready', 'Ready'), ('error', 'Error')],
        default='processing'
    )

    def __str__(self):
        return f"Chat {self.id} - {self.user}"

class Message(models.Model):
    ROLE_CHOICES = (
        ("user", "User"),
        ("assistant", "Assistant"),
    )
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    chat = models.ForeignKey(
        Chat,
        on_delete=models.CASCADE,
        related_name="messages"
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.role}: {self.content[:30]}"