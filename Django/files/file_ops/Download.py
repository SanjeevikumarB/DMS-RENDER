from uuid import UUID
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from django.http import HttpResponse
from accounts.authentication import CustomJWEAuthentication
from files.models import FileObject
from sharing.models import FileAccessControl
from files.models import FileVersion
import requests
from urllib.parse import quote
FASTAPI_DOWNLOAD_URL = "http://127.0.0.1:8081/download_file"

class DownloadFileAPIView(APIView):
    authentication_classes = [CustomJWEAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        file_uid = request.data.get('file_uid')
        # if file_uid is str:
        #     file_uid = UUID(str(file_uid))
        version_id = request.data.get('version_id')  # Optional

        if not file_uid:
            return Response({"error": "file_uid is required."}, status=status.HTTP_400_BAD_REQUEST)

        user = request.user
        file_obj = FileObject.objects.filter(uid=file_uid,trashed_at__isnull=True).first()
        if not file_obj:
            return Response({"error": "File not found or access denied."}, status=status.HTTP_404_NOT_FOUND)
        
        if file_obj.owner != user:
            has_editor_access = FileAccessControl.objects.filter(
                file=file_obj, user=user, access_level='editor'
            ).exists()
            if not has_editor_access:
                return Response(
                    {"error": "You do not have permission to download this file."},
                    status=status.HTTP_403_FORBIDDEN
                )

        # Fetch the first version (version_number = 1) for the given file
        initial_version = FileVersion.objects.filter(file=file_obj, version_number=1).first()

        if not initial_version:
            return Response({"error": "Initial version not found."}, status=status.HTTP_404_NOT_FOUND)

        # Retrieve the initial name from metadata_snapshot
        file_name =initial_version.metadata_snapshot.get("filename")
        file_name = quote(file_name)  # URL encode the file name
        version_id = version_id or file_obj.latest_version_id

        try:
            fastapi_url = f"{FASTAPI_DOWNLOAD_URL}/{file_name}"
            params = {"version_id": version_id} if version_id else {}
            access_token = request.auth
            headers = {
                "Authorization": f"Bearer {access_token}"
            }

            response = requests.get(
                fastapi_url,
                params=params,
                stream=True,
                headers=headers,
                timeout=30
            )

            if response.status_code == 200:
                django_response = HttpResponse(
                    response.raw,
                    content_type=response.headers.get("Content-Type", "application/octet-stream")
                )
                django_response["Content-Disposition"] = f'attachment; filename="{file_name}"'
                return django_response
            else:
                return Response(
                    {"error": "Failed to download file from FastAPI."},
                    status=response.status_code
                )

        except requests.exceptions.RequestException as e:
            return Response({"error": str(e)}, status=status.HTTP_502_BAD_GATEWAY)

# api/files/download_file/