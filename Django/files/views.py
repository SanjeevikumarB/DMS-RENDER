# import os
# import httpx
# from uuid import uuid4
# from django.conf import settings
# from django.utils.timezone import now
# from rest_framework.views import APIView
# from rest_framework.permissions import IsAuthenticated
# from rest_framework.parsers import MultiPartParser, FormParser
# from rest_framework.response import Response
# from rest_framework import status
# from accounts.authentication import JWEAuthentication
# # from .file_ops.ListFiles import ListUserFilesAPIView

# from .models import FileObject, FileVersion
# from .serializers import MultiFileUploadSerializer, CreateFolderSerializer

# FASTAPI_UPLOAD_URL = "http://127.0.0.1:8081/upload"

# # class MultiFileUploadAPIView(APIView):
# #     parser_classes = [MultiPartParser, FormParser]
# #     authentication_classes = [JWEAuthentication]
# #     permission_classes = [IsAuthenticated]

# #     def post(self, request, *args, **kwargs):
# #         serializer = MultiFileUploadSerializer(data=request.data)
# #         if not serializer.is_valid():
# #             return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# #         user = request.user
# #         file_entries = serializer.validated_data['files']

# #         multipart_files = [
# #             ("files", (entry["file"].name, entry["file"].read(), entry["file"].content_type))
# #             for entry in file_entries
# #         ]

# #         try:
# #             fastapi_response = httpx.post(
# #                 FASTAPI_UPLOAD_URL,
# #                 files=multipart_files,
# #                 timeout=60.0
# #             )
# #         except httpx.HTTPError as e:
# #             return Response({"error": f"FastAPI upload failed: {str(e)}"}, status=502)

# #         if fastapi_response.status_code != 200:
# #             return Response({"error": "Upload failed", "detail": fastapi_response.text}, status=502)

# #         uploaded_metadata_list = fastapi_response.json()
# #         response_data = []

# #         for entry, metadata in zip(file_entries, uploaded_metadata_list):
# #             relative_path = entry["relative_path"]
# #             file_name = os.path.basename(relative_path)
# #             folder_path = os.path.dirname(relative_path)

# #             parent = self.ensure_folder_structure(user, folder_path)
# #             file_obj = FileObject.objects.create(
# #                 uid=uuid4(),
# #                 owner=user,
# #                 name=file_name,
# #                 type="file",
# #                 extension=metadata.get("extension"),
# #                 size=metadata.get("size"),
# #                 metadata=metadata,
# #                 uploaded_url=metadata.get("cdn_url"),
# #                 parent=parent,
# #             )

# #             FileVersion.objects.create(
# #                 file=file_obj,
# #                 version_number=1,
# #                 action="upload",
# #                 metadata_snapshot=metadata,
# #                 created_by=user,
# #             )

# #             response_data.append({
# #                 "name": file_obj.name,
# #                 "url": file_obj.uploaded_url,
# #                 "uid": file_obj.uid,
# #                 "path": relative_path,
# #             })

# #         return Response({"message": "Files uploaded successfully!", "files": response_data}, status=201)

# #     def ensure_folder_structure(self, user, folder_path):
# #         if not folder_path:
# #             return None
# #         parent = None
# #         parts = folder_path.strip("/").split("/")
# #         for part in parts:
# #             folder, _ = FileObject.objects.get_or_create(
# #                 owner=user,
# #                 name=part,
# #                 type="folder",
# #                 parent=parent,
# #                 defaults={"uid": uuid4()}
# #             )
# #             parent = folder
# #         return parent

# class MultiFileUploadAPIView(APIView):
#     parser_classes = [MultiPartParser, FormParser]
#     authentication_classes = [JWEAuthentication]
#     permission_classes = [IsAuthenticated]

#     def post(self, request, *args, **kwargs):
#         file_entries = []

#         # Extract each file and its relative path from request.data
#         index = 0
#         while True:
#             file_key = f"files[{index}].file"
#             path_key = f"files[{index}].relative_path"

#             if file_key not in request.FILES or path_key not in request.data:
#                 break  # Stop if no more entries

#             file = request.FILES[file_key]
#             relative_path = request.data[path_key]

#             file_entries.append({
#                 "file": file,
#                 "relative_path": relative_path
#             })

#             index += 1

#         if not file_entries:
#             return Response({"error": "No files found"}, status=400)

#         user = request.user

#         multipart_files = [
#             ("files", (entry["file"].name, entry["file"].read(), entry["file"].content_type))
#             for entry in file_entries
#         ]

#         try:
#             fastapi_response = httpx.post(
#                 FASTAPI_UPLOAD_URL,
#                 files=multipart_files,
#                 timeout=60.0
#             )
#         except httpx.HTTPError as e:
#             return Response({"error": f"FastAPI upload failed: {str(e)}"}, status=502)

#         if fastapi_response.status_code != 200:
#             return Response({"error": "Upload failed", "detail": fastapi_response.text}, status=502)

#         uploaded_metadata_list = fastapi_response.json()
#         response_data = []

#         for entry, metadata in zip(file_entries, uploaded_metadata_list):
#             relative_path = entry["relative_path"]
#             file_name = os.path.basename(relative_path)
#             folder_path = os.path.dirname(relative_path)

#             parent = self.ensure_folder_structure(user, folder_path)
#             # Check if file already exists at the same location
#             file_obj = FileObject.objects.filter(
#                 owner=user,
#                 name=file_name,
#                 type="file",
#                 parent=parent
#             ).first()

#             # Extract version_id from metadata
#             s3_version_id = metadata.get("version_id")

#             if file_obj:
#                 # Existing file: create a new version, update metadata
#                 latest_version = FileVersion.objects.filter(file=file_obj).order_by('-version_number').first()
#                 new_version_number = latest_version.version_number + 1 if latest_version else 2

#                 # Update file content and latest version id
#                 file_obj.extension = metadata.get("extension")
#                 file_obj.size = metadata.get("size")
#                 file_obj.metadata = metadata
#                 file_obj.uploaded_url = metadata.get("cdn_url")
#                 file_obj.latest_version_id = s3_version_id
#                 file_obj.save()

#                 FileVersion.objects.create(
#                     file=file_obj,
#                     version_number=new_version_number,
#                     action="upload",
#                     metadata_snapshot=metadata,
#                     s3_version_id=s3_version_id,
#                     created_by=user,
#                 )

#             else:
#                 # New file in this folder
#                 file_obj = FileObject.objects.create(
#                     uid=uuid4(),
#                     owner=user,
#                     name=file_name,
#                     type="file",
#                     extension=metadata.get("extension"),
#                     size=metadata.get("size"),
#                     metadata=metadata,
#                     uploaded_url=metadata.get("cdn_url"),
#                     latest_version_id=s3_version_id,
#                     parent=parent,
#                 )

#                 FileVersion.objects.create(
#                     file=file_obj,
#                     version_number=1,
#                     action="upload",
#                     metadata_snapshot=metadata,
#                     s3_version_id=s3_version_id,
#                     created_by=user,
#                 )

#             response_data.append({
#                 "name": file_obj.name,
#                 "url": file_obj.uploaded_url,
#                 "uid": file_obj.uid,
#                 "path": relative_path,
#             })

#         return Response({"message": "Files uploaded successfully!", "files": response_data}, status=201)

#     def ensure_folder_structure(self, user, folder_path):
#         if not folder_path:
#             return None
#         parent = None
#         parts = folder_path.strip("/").split("/")
#         for part in parts:
#             folder, _ = FileObject.objects.get_or_create(
#                 owner=user,
#                 name=part,
#                 type="folder",
#                 parent=parent,
#                 defaults={"uid": uuid4()}
#             )
#             parent = folder
#         return parent