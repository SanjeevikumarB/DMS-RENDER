from django.db import models
import uuid
from accounts.models import CustomUser
 
class FileObject(models.Model):
    uid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='files')
    name = models.CharField(max_length=255)
    type = models.CharField(max_length=10, choices=[("file", "File"), ("folder", "Folder")])
    description = models.TextField(blank=True, null=True)
    extension = models.CharField(max_length=20, blank=True, null=True)
    size = models.BigIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)
    accessed_at = models.DateTimeField(auto_now=True)
    metadata = models.JSONField(null=True, blank=True)
    uploaded_url = models.URLField(blank=True, null=True)
    presigned_url = models.URLField(blank=True, null=True)
    latest_version_id = models.CharField(max_length=255, blank=True, null=True)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children')
    tags = models.TextField(blank=True, null=True)
    trashed_at = models.DateTimeField(null=True, blank=True)
 
    class Meta:
        indexes = [
            models.Index(fields=["owner", "parent", "trashed_at"]),
            models.Index(fields=["parent", "name", "type"]),
            models.Index(fields=["owner", "name", "type", "parent"]),
            models.Index(fields=["parent", "type", "name"]),
        ]
 
    # class Meta:
    #     unique_together = ('owner', 'parent', 'name', 'type')
 
class FileVersion(models.Model):
    uid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    file = models.ForeignKey(FileObject, on_delete=models.CASCADE, related_name='versions')
    version_number = models.IntegerField()
    action = models.CharField(max_length=50)
    metadata_snapshot = models.JSONField()
    s3_version_id = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True)
    storage_class = models.CharField(max_length=50, default="STANDARD")
    restore_status = models.CharField(max_length=20, default="available")
    initial_filename_snapshot = models.CharField(max_length=255, blank=True, null=True)
 
    class Meta:
        indexes = [
            models.Index(fields=["file", "version_number"]),
            models.Index(fields=["s3_version_id"]),
        ]
 
class TrashAutoCleanQueue(models.Model):
    uid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    file = models.ForeignKey(FileObject, on_delete=models.CASCADE)
    scheduled_delete_at = models.DateTimeField()
    status = models.CharField(max_length=50)
    deleted_at = models.DateTimeField(null=True, blank=True)
    restored_at = models.DateTimeField(null=True, blank=True)
 
class StarredFile(models.Model):
    uid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='starred_files')
    file = models.ForeignKey(FileObject, on_delete=models.CASCADE, related_name='starred_by')
    starred_at = models.DateTimeField(auto_now_add=True)
 
    class Meta:
        unique_together = ('user', 'file')  
        ordering = ['-starred_at']          
 
class FileActionLog(models.Model):
    ACTION_CHOICES = [
        ("trashed", "Trashed"),
        ("restored", "Restored"),
        ("deleted", "Permanently deleted"),
        ("created", "Created"),
        ("modified", "Modified"),
        ("shared", "Shared"),
        ("unshared", "Unshared"),
        # We can expand this list as needed
    ]
    uid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    file = models.ForeignKey(FileObject, on_delete=models.CASCADE)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    performed_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True)
    performed_at = models.DateTimeField(auto_now_add=True)
    reason = models.TextField(blank=True)
    detail = models.JSONField(null=True, blank=True)  # To save extra structured info if needed

    class Meta:
        indexes = [
            models.Index(fields=["file", "performed_at"]),
            models.Index(fields=["performed_by", "performed_at"]),
        ]
        ordering = ['-performed_at']
