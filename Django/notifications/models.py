from django.db import models
import uuid
from accounts.models import CustomUser
from files.models import FileObject

class Notification(models.Model):
    uid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recipient = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    type = models.CharField(max_length=50)
    title = models.CharField(max_length=255)
    message = models.TextField()
    related_file = models.ForeignKey(FileObject, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
    read = models.BooleanField(default=False)