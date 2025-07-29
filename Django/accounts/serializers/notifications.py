# accounts/serializers/notifications.py

from rest_framework import serializers
from notifications.models import Notification  # Adjust if your model is elsewhere

class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = [
            "uid", "type", "title", "message",
            "created_at", "read", "related_file_id"
        ]
