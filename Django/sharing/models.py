from django.db import models
import uuid
from accounts.models import CustomUser
from files.models import FileObject

class FileAccessControl(models.Model):
    uid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    file = models.ForeignKey(FileObject, on_delete=models.CASCADE, related_name='access_controls')
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    access_level = models.CharField(max_length=20, choices=[("viewer", "Viewer"), ("editor", "Editor")])
    granted_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, related_name='granted_permissions')
    granted_at = models.DateTimeField(auto_now_add=True)
    inherited = models.BooleanField(default=False)
    inherited_from = models.ForeignKey(
        "files.FileObject", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="inherited_shares"
    )

class FileShareRequest(models.Model):
    uid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    file = models.ForeignKey(FileObject, on_delete=models.CASCADE)
    requester = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='share_requests')
    target_user = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE,
        related_name='incoming_share_requests', null=True, blank=True
    )
    access_type = models.CharField(max_length=20, choices=[("viewer", "Viewer"), ("editor", "Editor")])
    status = models.CharField(max_length=20, choices=[("pending", "Pending"), ("approved", "Approved"), ("rejected", "Rejected")])
    reason = models.TextField(blank=True, null=True)
    reviewed_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_share_requests')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

class ShareableLink(models.Model):
    uid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    file = models.ForeignKey(FileObject, on_delete=models.CASCADE)
    link_type = models.CharField(max_length=20, choices=[("public", "Public"), ("private", "Private")])
    created_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    url_token = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
