# from uuid import uuid4
# import os
# import httpx
# from rest_framework.views import APIView
# from rest_framework.permissions import IsAuthenticated
# from rest_framework.parsers import MultiPartParser, FormParser
# from rest_framework.response import Response
# from rest_framework import status
# from accounts.authentication import CustomJWEAuthentication
# from ..models import FileObject, FileVersion
# from ..serializers import MultiFileUploadSerializer
# from sharing.models import FileAccessControl
 
 
# FASTAPI_UPLOAD_URL = "http://127.0.0.1:8081/upload"
 
# class MultiFileUploadAPIView(APIView):
#     parser_classes = [MultiPartParser, FormParser]
#     authentication_classes = [CustomJWEAuthentication]
#     permission_classes = [IsAuthenticated]
 
#     def post(self, request, *args, **kwargs):
 
#         # serializer = MultiFileUploadSerializer(data=request.data)
#         # if not serializer.is_valid():
#         #     return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
   
#         # user = request.user
#         # file_entries = serializer.validated_data['files']
 
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
#             access_token = request.auth
#             headers = {
#                 "Authorization": f"Bearer {access_token}"
#             }
#             fastapi_response = httpx.post(
#                 FASTAPI_UPLOAD_URL,
#                 files=multipart_files,
#                 headers=headers,
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
 
#             try:
#                 parent = self.ensure_folder_structure(user, folder_path)
#             except PermissionError as e:
#                 return Response({"error": str(e)}, status=status.HTTP_403_FORBIDDEN)
 
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
#             # Check if this folder already exists under current parent
#             try:
#                 folder = FileObject.objects.get(
#                     name=part,
#                     type="folder",
#                     parent=parent
#                 )
 
#                 if folder.owner != user:
#                     has_editor_access = FileAccessControl.objects.filter(
#                         file=folder,
#                         user=user,
#                         access_level="editor"
#                     ).exists()
 
#                     if not has_editor_access:
#                         raise PermissionError(f"No permission to upload into folder: {folder.name}")
#             except FileObject.DoesNotExist:
#                 # Creating a new folder – only allowed if parent is None (root) or user owns/is editor of parent
#                 if parent:
#                     if parent.owner != user:
#                         has_editor_access = FileAccessControl.objects.filter(
#                             file=parent,
#                             user=user,
#                             access_level="editor"
#                         ).exists()
 
#                         if not has_editor_access:
#                             raise PermissionError(f"No permission to create subfolder: {part} in {parent.name}")
 
#                 folder = FileObject.objects.create(
#                     uid=uuid4(),
#                     owner=user,
#                     name=part,
#                     type="folder",
#                     parent=parent
#                 )
 
#             parent = folder
 
#         return parent
# import httpx
# from rest_framework.views import APIView
# from rest_framework.response import Response
# from rest_framework import status
# from django.conf import settings

# from files.models import FileObject, FileVersion
# from sharing.models import FileAccessControl
# from accounts.authentication import CustomJWEAuthentication
# from rest_framework.permissions import IsAuthenticated


# class MultiFileUploadAPIView(APIView):
#     authentication_classes = [CustomJWEAuthentication]
#     permission_classes = [IsAuthenticated]

#     def post(self, request):
#         user = request.user
#         parent_uid = request.data.get("parent")
#         files = request.FILES.getlist("files")

#         if not files:
#             return Response({"error": "No files provided."}, status=status.HTTP_400_BAD_REQUEST)

#         parent = None
#         if parent_uid:
#             try:
#                 parent = FileObject.objects.get(uid=parent_uid, type="folder", owner=user)
#             except FileObject.DoesNotExist:
#                 return Response({"error": "Parent folder not found."}, status=status.HTTP_404_NOT_FOUND)

#         uploaded_files = []

#         for file in files:
#             try:
#                 file.seek(0)

#                 # Send to FastAPI upload endpoint
#                 fastapi_files = [("files", (file.name, file.read(), file.content_type))]

#                 with httpx.Client() as client:
#                     fastapi_response = client.post(
#                         "http://127.0.0.1:8081/upload",
#                         files=fastapi_files,
#                         headers={"Authorization": request.headers.get("Authorization", "")},
#                         timeout=60.0
#                     )

#                 if fastapi_response.status_code != 200:
#                     return Response({
#                         "error": "FastAPI upload failed.",
#                         "detail": fastapi_response.text
#                     }, status=status.HTTP_502_BAD_GATEWAY)

#                 upload_data_list = fastapi_response.json()

#                 for upload_data in upload_data_list:
#                     cdn_url = upload_data["cdn_url"]
#                     version_id = upload_data.get("version_id")
#                     metadata = {
#                         key: upload_data[key]
#                         for key in upload_data
#                         if key not in {"cdn_url", "version_id", "status", "message"}
#                     }

#                 file_obj = FileObject.objects.create(
#                     owner=user,
#                     parent=parent,
#                     name=upload_data.get("filename", file.name),
#                     type="file",
#                     extension=upload_data.get("extension", "").lstrip("."),
#                     size=upload_data.get("size", file.size),
#                     uploaded_url=cdn_url,
#                     latest_version_id=version_id,
#                     metadata=metadata,
#                 )

#                 version_number = FileVersion.objects.filter(file=file_obj).count() + 1
#                 FileVersion.objects.create(
#                     file=file_obj,
#                     version_number=version_number,
#                     action="upload",
#                     metadata_snapshot=metadata,
#                     s3_version_id=version_id,
#                     created_by=user
#                 )

#                 self.apply_inherited_access(file_obj, user)

#                 uploaded_files.append({
#                     "uid": str(file_obj.uid),
#                     "name": file_obj.name,
#                     "cdn_url": file_obj.uploaded_url,
#                     "version_id": version_id,
#                 })

#             except Exception as e:
#                 return Response({"error": f"Upload failed: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

#         return Response({"uploaded_files": uploaded_files}, status=status.HTTP_201_CREATED)

#     def apply_inherited_access(self, file_obj, uploader_user):
#         """
#         Traverse parent chain and apply inherited access for all relevant users.
#         """
#         parent = file_obj.parent
#         visited_users = set()

#         while parent:
#             inherited_from = parent
#             inherited_acls = FileAccessControl.objects.filter(file=parent, inherited=False)

#             for acl in inherited_acls:
#                 if acl.user == uploader_user or acl.user_id in visited_users:
#                     continue

#                 if not FileAccessControl.objects.filter(file=file_obj, user=acl.user).exists():
#                     FileAccessControl.objects.create(
#                         file=file_obj,
#                         user=acl.user,
#                         access_level=acl.access_level,
#                         inherited=True,
#                         inherited_from=inherited_from
#                     )
#                     visited_users.add(acl.user_id)

#             parent = parent.parent

import httpx
import os
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from django.db.models import Q
from django.utils.text import slugify

from files.models import FileObject, FileVersion
from sharing.models import FileAccessControl
from accounts.authentication import CustomJWEAuthentication
import json

class MultiFileUploadAPIView(APIView):
    authentication_classes = [CustomJWEAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        files_data = request.FILES.getlist("files")
        relative_paths= request.data.getlist("relative_paths")  # match index with files
        root_folder_uid = request.data.get("root_folder_uid")

        try:
            relative_paths = json.loads(request.data.get('relative_paths', '[]'))
        except Exception:
            return Response({"error": "Invalid JSON for relative_paths"}, status=400)

        if not files_data or not relative_paths or len(files_data) != len(relative_paths):
            return Response({"error": "Files and relative_paths mismatch."}, status=status.HTTP_400_BAD_REQUEST)

        # Validate root folder access
        root = None
        if root_folder_uid:
            try:
                root = FileObject.objects.get(uid=root_folder_uid, type="folder")
                if root.owner != user:
                    # Must have editor access
                    if not FileAccessControl.objects.filter(file=root, user=user, access_level="editor").exists():
                        return Response({"error": "You don't have editor access to this folder."}, status=status.HTTP_403_FORBIDDEN)
            except FileObject.DoesNotExist:
                return Response({"error": "Invalid root folder UID."}, status=status.HTTP_404_NOT_FOUND)

        uploaded_files = []

        try:
            with transaction.atomic():
                for file, rel_path in zip(files_data, relative_paths):
                    cleaned_path = os.path.normpath(rel_path).replace("\\", "/")
                    parts = cleaned_path.split("/")

                    parent = root
                    for folder_name in parts[:-1]:  # all except the file
                        folder_name = folder_name.strip()
                        folder, created = FileObject.objects.get_or_create(
                            owner=root.owner if root else user,
                            parent=parent,
                            name=folder_name,
                            type="folder",
                            defaults={
                                "extension": "",
                                "size": 0,
                                "uploaded_url": None,
                                "metadata": {},
                            }
                        )
                        parent = folder
                        if created:
                            # Apply inherited access from parent
                            self.apply_inherited_access(folder, user)
                            # Ensure owner gets access if editor is uploading
                            if root and user != root.owner:
                                self.ensure_owner_access(folder, root.owner)

                    file.seek(0)
                    fastapi_files = [("files", (file.name, file.read(), file.content_type))]

                    access_token = request.auth
                    headers = {
                        "Authorization": f"Bearer {access_token}"
                    }

                    # auth_header = request.META.get("HTTP_AUTHORIZATION")
                    # if not auth_header:
                    #     return Response({"error": "Authorization header missing"}, status=401)

                    # headers = {"Authorization": auth_header}

                    with httpx.Client() as client:
                        fastapi_response = client.post(
                            "http://127.0.0.1:8081/upload",
                            files=fastapi_files,
                            headers=headers,
                            timeout=60.0,
                        )

                    if fastapi_response.status_code != 200:
                        raise Exception(f"FastAPI upload failed: {fastapi_response.text}")

                    upload_data_list = fastapi_response.json()

                    for upload_data in upload_data_list:
                        cdn_url = upload_data["cdn_url"]
                        version_id = upload_data.get("version_id")
                        metadata = {
                            key: upload_data[key]
                            for key in upload_data
                            if key not in {"cdn_url", "version_id", "status", "message"}
                        }

                        existing_file = FileObject.objects.filter(
                        owner=root.owner if root else user,
                        parent=parent,
                        name=upload_data.get("filename", file.name),
                        type="file"
                    ).first()

                    if existing_file:
                        if existing_file.owner != user:
                            has_editor_access = FileAccessControl.objects.filter(
                                file=existing_file,
                                user=user,
                                access_level="editor"
                            ).exists()
                            if not has_editor_access:
                                raise Exception(f"You don't have editor access to overwrite {existing_file.name}.")

                        existing_file.extension = upload_data.get("extension", "").lstrip(".")
                        existing_file.size = upload_data.get("size", file.size)
                        existing_file.uploaded_url = cdn_url
                        existing_file.latest_version_id = version_id
                        existing_file.metadata = metadata
                        existing_file.save()

                        latest_version = FileVersion.objects.filter(file=existing_file).order_by('-version_number').first()
                        new_version_number = latest_version.version_number + 1 if latest_version else 2
                        initial_filename = latest_version.initial_filename_snapshot or existing_file.name

                        FileVersion.objects.create(
                            file=existing_file,
                            version_number=new_version_number,
                            action="upload",
                            metadata_snapshot=metadata,
                            s3_version_id=version_id,
                            created_by=user,
                            initial_filename_snapshot=initial_filename,
                        )

                        uploaded_files.append({
                            "uid": str(existing_file.uid),
                            "name": existing_file.name,
                            "cdn_url": existing_file.uploaded_url,
                            "version_id": version_id,
                            "path": cleaned_path,
                        })

                    else:
                        # Create new file
                        file_obj = FileObject.objects.create(
                            owner=root.owner if root else user,
                            parent=parent,
                            name=upload_data.get("filename", file.name),
                            type="file",
                            extension=upload_data.get("extension", "").lstrip("."),
                            size=upload_data.get("size", file.size),
                            uploaded_url=cdn_url,
                            latest_version_id=version_id,
                            metadata=metadata,
                        )

                        version_number = FileVersion.objects.filter(file=file_obj).count() + 1
                        FileVersion.objects.create(
                            file=file_obj,
                            version_number=version_number,
                            action="upload",
                            metadata_snapshot=metadata,
                            s3_version_id=version_id,
                            created_by=user,
                            initial_filename_snapshot=upload_data.get("filename", file.name), 
                        )

                        self.apply_inherited_access(file_obj, user)
                        if root and user != root.owner:
                            self.ensure_owner_access(file_obj, root.owner)

                        uploaded_files.append({
                            "uid": str(file_obj.uid),
                            "name": file_obj.name,
                            "cdn_url": file_obj.uploaded_url,
                            "version_id": version_id,
                            "path": cleaned_path,
                        })

        except Exception as e:
            return Response({"error": f"Upload failed: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({"uploaded_files": uploaded_files}, status=status.HTTP_201_CREATED)

    def apply_inherited_access(self, file_obj, uploader_user):
        """
        Apply inherited access from parent folders, excluding uploader and already-existing ACLs.
        """
        parent = file_obj.parent
        visited_users = set()

        while parent:
            inherited_acls = FileAccessControl.objects.filter(file=parent, inherited=False)
            for acl in inherited_acls:
                if acl.user == uploader_user or acl.user_id in visited_users:
                    continue
                if not FileAccessControl.objects.filter(file=file_obj, user=acl.user).exists():
                    FileAccessControl.objects.create(
                        file=file_obj,
                        user=acl.user,
                        access_level=acl.access_level,
                        inherited=True,
                        inherited_from=parent
                    )
                    visited_users.add(acl.user_id)
            parent = parent.parent

    def ensure_owner_access(self, file_obj, owner_user):
        """
        Ensures the owner of the shared folder gets 'editor' access to uploaded content by an editor.
        """
        if not FileAccessControl.objects.filter(file=file_obj, user=owner_user).exists():
            FileAccessControl.objects.create(
                file=file_obj,
                user=owner_user,
                access_level="editor",
                inherited=True,
                inherited_from=file_obj.parent
            )