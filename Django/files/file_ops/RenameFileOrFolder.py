from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from accounts.authentication import CustomJWEAuthentication
from files.models import FileObject, FileVersion
from sharing.models import FileAccessControl

class RenameFileOrFolderAPIView(APIView):
    authentication_classes = [CustomJWEAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        file_uid = request.data.get("file_uid")
        new_name = request.data.get("new_name")

        if not file_uid or not new_name:
            return Response({"error": "Missing file_uid or new_name"}, status=400)

        try:
            obj = FileObject.objects.get(uid=file_uid, trashed_at__isnull=True)
        except FileObject.DoesNotExist:
            return Response({"error": "File or folder not found"}, status=404)

        user = request.user

        # Access control check: owner or editor
        if not (obj.owner == user or FileAccessControl.objects.filter(file=obj, user=user, access_level="editor").exists()):
            return Response({"error": "You do not have permission to rename this file/folder."}, status=403)

        # Duplicate name check in same parent/type
        duplicate = FileObject.objects.filter(
            owner=obj.owner,
            parent=obj.parent,
            name=new_name,
            type=obj.type,
            trashed_at__isnull=True
        ).exclude(uid=obj.uid).exists()

        if duplicate:
            return Response({
                "error": f"A {obj.type} with the name '{new_name}' already exists in this folder."
            }, status=409)

        # Rename logic
        old_name = obj.name
        obj.name = new_name
        obj.save(update_fields=["name", "modified_at"])

        # File versioning metadata
        metadata_snapshot = {
            "old_name": old_name,
            "new_name": new_name,
        }

        if obj.type == "file" and obj.metadata:
            metadata_snapshot.update({
                "s3_key": obj.metadata.get("s3_key"),
                "version_id": obj.metadata.get("version_id"),
            })

        latest_version = FileVersion.objects.filter(file=obj).order_by('-version_number').first()
        initial_filename = latest_version.initial_filename_snapshot if latest_version else obj.name

        FileVersion.objects.create(
            file=obj,
            version_number=obj.versions.count() + 1,
            action="rename",
            metadata_snapshot=metadata_snapshot,
            created_by=user,
            s3_version_id=obj.metadata.get("latest_version_id") if obj.metadata else None,
            initial_filename_snapshot=initial_filename,
        )

        return Response({"message": f"{obj.type.title()} renamed successfully."}, status=200)
