from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.db import models
from files.models import FileObject, FileVersion
from accounts.authentication import CustomJWEAuthentication


class RestoreVersionAPIView(APIView):
    authentication_classes = [CustomJWEAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        file_uid = request.data.get("file_uid")
        version_uid = request.data.get("version_uid")

        if not file_uid or not version_uid:
            return Response({"error": "file_uid and version_uid are required."}, status=400)

        file_obj = get_object_or_404(FileObject, uid=file_uid)

        # Ensure only owner can restore
        if file_obj.owner != user:
            return Response({"error": "Only the owner can restore a version."}, status=403)

        version_to_restore = get_object_or_404(FileVersion, uid=version_uid, file=file_obj)

        # Determine next version number
        latest_version_num = file_obj.versions.aggregate(max_num=models.Max('version_number'))['max_num'] or 0
        new_version_number = latest_version_num + 1

        # Create new FileVersion
        restored_version = FileVersion.objects.create(
            file=file_obj,
            version_number=new_version_number,
            action="restored",
            metadata_snapshot=version_to_restore.metadata_snapshot,
            s3_version_id=version_to_restore.s3_version_id,
            created_by=user,
            initial_filename_snapshot=version_to_restore.initial_filename_snapshot,
        )

        # Extract metadata snapshot
        snapshot = version_to_restore.metadata_snapshot or {}

        # Update FileObject to reflect restored version
        file_obj.name = snapshot.get("name", file_obj.name)
        file_obj.uploaded_url = snapshot.get("uploaded_url", file_obj.uploaded_url)
        file_obj.latest_version_id = str(version_to_restore.s3_version_id)
        file_obj.size = snapshot.get("size", file_obj.size)
        file_obj.extension = snapshot.get("extension", file_obj.extension)
        file_obj.metadata = snapshot  # full snapshot

        file_obj.save(update_fields=[
            "name", "uploaded_url", "latest_version_id", "size", "extension", "metadata"
        ])

        return Response({"message": "Version restored successfully."}, status=200)
