import io
from urllib.parse import quote
from uuid import UUID
import requests
import json
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions

from django.db import transaction

from accounts.authentication import CustomJWEAuthentication
from files.models import FileObject, FileVersion
from sharing.models import FileAccessControl


FASTAPI_DOWNLOAD_URL = "http://127.0.0.1:8081/download_file"
FASTAPI_UPLOAD_URL = "http://127.0.0.1:8081/upload"


class SaveAsCopyAPIView(APIView):
    authentication_classes = [CustomJWEAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        file_uid = request.data.get("file_uid")
        version_id = request.data.get("s3_version_id")
        new_name = request.data.get("new_name", None)
        target_parent_uid = request.data.get("target_parent_uid", None)

        if not file_uid or not version_id:
            return Response({"error": "file_uid and version_id are required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            file_uuid = UUID(file_uid)
        except ValueError:
            return Response({"error": "Invalid file_uid."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            file_obj = FileObject.objects.get(uid=file_uuid, trashed_at__isnull=True)
        except FileObject.DoesNotExist:
            return Response({"error": "Source file not found."}, status=status.HTTP_404_NOT_FOUND)

        # Permission check: Only owner or editor can duplicate
        if file_obj.owner != user:
            has_editor_access = FileAccessControl.objects.filter(
                file=file_obj,
                user=user,
                access_level='editor'
            ).exists()
            if not has_editor_access:
                return Response({"error": "Permission denied to duplicate this file."}, status=status.HTTP_403_FORBIDDEN)

        # Validate requested version exists
        version = FileVersion.objects.filter(file=file_obj, s3_version_id=version_id).first()
        if not version:
            return Response({"error": "Specified version not found."}, status=status.HTTP_404_NOT_FOUND)

        # Default new filename if not specified
        # initial_version = FileVersion.objects.filter(file=file_obj, version_number=1).first()
        # original_filename = initial_version.metadata_snapshot.get("filename")
        original_filename = version.initial_filename_snapshot or file_obj.name
        name, extension = original_filename.rsplit('.', 1) if '.' in original_filename else (original_filename, None)
        upload_filename = new_name or f"{name} (copy).{extension}"

        # Validate target parent folder if specified
        target_parent = None
        if target_parent_uid:
            try:
                target_parent_uuid = UUID(target_parent_uid)
                target_parent = FileObject.objects.get(uid=target_parent_uuid, type="folder", trashed_at__isnull=True)
            except (ValueError, FileObject.DoesNotExist):
                return Response({"error": "Invalid target_parent_uid."}, status=status.HTTP_400_BAD_REQUEST)

            # Permission check on target folder for upload: owner or editor required
            if target_parent.owner != user:
                has_editor_access = FileAccessControl.objects.filter(
                    file=target_parent,
                    user=user,
                    access_level='editor'
                ).exists()
                if not has_editor_access:
                    return Response({"error": "No permission to upload in target folder."}, status=status.HTTP_403_FORBIDDEN)

        else:
            # If no target_parent specified, place in root (parent=None) owned by user
            target_parent = None

        # Prohibit restoration of version on same path by non-owner
        # Restoration here means uploading with same name and parent as original file's
        is_restore = (
            (upload_filename == file_obj.name) and
            ((target_parent is None and file_obj.parent is None) or
             (target_parent and file_obj.parent and target_parent.uid == file_obj.parent.uid))
        )
        if is_restore and (file_obj.owner != user):
            return Response({"error": "Only owner can restore older versions to the original location."}, status=status.HTTP_403_FORBIDDEN)

        # Download file from FastAPI download endpoint
        filename_encoded = quote(original_filename)

        headers = {
            "Authorization": f"Bearer {request.auth}"
        }
        download_url = f"{FASTAPI_DOWNLOAD_URL}/{filename_encoded}"
        params = {"version_id": version_id}

        try:
            download_resp = requests.get(download_url, headers=headers, params=params, timeout=60)
            if download_resp.status_code != 200:
                return Response({"error": f"Failed to download file: {download_resp.text}"}, status=download_resp.status_code)
        except requests.RequestException as e:
            return Response({"error": f"Download failed: {str(e)}"}, status=status.HTTP_502_BAD_GATEWAY)

        file_content = io.BytesIO(download_resp.content)
        file_content.seek(0)
        
        # Prepare files payload for FastAPI upload endpoint
        content_type = download_resp.headers.get("Content-Type", "application/octet-stream")
        files = {
            "files": (upload_filename, file_content, content_type)
        }

        # Upload file to FastAPI upload endpoint
        try:
            upload_resp = requests.post(FASTAPI_UPLOAD_URL, files=files, headers=headers, timeout=60)
            if upload_resp.status_code != 200:
                return Response({"error": f"Upload failed: {upload_resp.text}"}, status=upload_resp.status_code)
            upload_resp_data = upload_resp.json()
        except requests.RequestException as e:
            return Response({"error": f"Upload failed: {str(e)}"}, status=status.HTTP_502_BAD_GATEWAY)

        if not upload_resp_data or not isinstance(upload_resp_data, list):
            return Response({"error": "Invalid upload response."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        upload_info = upload_resp_data[0]

        # Extract upload metadata
        cdn_url = upload_info.get("cdn_url")
        new_version_id = upload_info.get("version_id")
        size = upload_info.get("size", 0)
        extension = upload_info.get("extension", None)
        metadata_snapshot = {k: upload_info.get(k) for k in upload_info if k not in (
            "cdn_url", "version_id", "status", "message"
        )}

        if not cdn_url or not new_version_id:
            return Response({"error": "Upload response missing critical data."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        with transaction.atomic():
            # Create new FileObject record
            new_file = FileObject.objects.create(
                owner=user,
                parent=target_parent,
                name=upload_filename,
                type="file",
                extension=extension or file_obj.extension,
                size=size,
                metadata=metadata_snapshot,
                uploaded_url=cdn_url,
                latest_version_id=new_version_id
            )

            # Create initial FileVersion entry
            FileVersion.objects.create(
                file=new_file,
                version_number=1,
                action="duplicate",
                metadata_snapshot=metadata_snapshot,
                s3_version_id=new_version_id,
                created_by=user,
                initial_filename_snapshot=upload_filename
            )

            # Copy over access controls (ACLs) from original file
            source_acls = FileAccessControl.objects.filter(file=file_obj)
            for acl in source_acls:
                FileAccessControl.objects.create(
                    file=new_file,
                    user=acl.user,
                    access_level=acl.access_level,
                    granted_by=acl.granted_by,
                    inherited=acl.inherited,
                    inherited_from=acl.inherited_from
                )

        return Response({
            "message": "File duplicated successfully",
            "file": {
                "uid": str(new_file.uid),
                "name": new_file.name,
                "uploaded_url": new_file.uploaded_url,
                "latest_version_id": new_file.latest_version_id,
                "parent_uid": str(target_parent.uid) if target_parent else None,
            }
        }, status=status.HTTP_201_CREATED)
