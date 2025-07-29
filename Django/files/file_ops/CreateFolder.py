# from uuid import uuid4
# from rest_framework.views import APIView
# from rest_framework.permissions import IsAuthenticated
# from rest_framework.response import Response
# from rest_framework import status
# from accounts.authentication import CustomJWEAuthentication
# from ..models import FileObject
# from ..serializers import CreateFolderSerializer
# from sharing.models import FileAccessControl

# class CreateFolderAPIView(APIView):
#     authentication_classes = [CustomJWEAuthentication]
#     permission_classes = [IsAuthenticated]

#     def post(self, request):
#         serializer = CreateFolderSerializer(data=request.data)
#         if not serializer.is_valid():
#             return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

#         user = request.user
#         folder_name = serializer.validated_data['name']
#         parent_uid = serializer.validated_data.get('parent_uid')

#         parent = None
#         if parent_uid:
#             try:
#                 parent = FileObject.objects.get(uid=parent_uid, type="folder", trashed_at__isnull=True)
#             except FileObject.DoesNotExist:
#                 return Response({"error": "Invalid parent folder UID."}, status=404)

#             # Access check
#             if parent.owner != user:
#                 has_editor_access = FileAccessControl.objects.filter(
#                     file=parent,
#                     user=user,
#                     access_level="editor"
#                 ).exists()
#                 if not has_editor_access:
#                     return Response({"error": "No permission to create folder here."}, status=403)

#         # ✅ Create folder
#         new_folder = FileObject.objects.create(
#             uid=uuid4(),
#             owner=user,
#             name=folder_name,
#             type="folder",
#             parent=parent
#         )

#         return Response({
#             "message": "Folder created successfully.",
#             "folder": {
#                 "uid": str(new_folder.uid),
#                 "name": new_folder.name,
#                 "parent_id": str(parent.uid) if parent else None
#             }
#         }, status=201)

from uuid import uuid4
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from accounts.authentication import CustomJWEAuthentication
from ..models import FileObject
from ..serializers import CreateFolderSerializer
from sharing.models import FileAccessControl

class CreateFolderAPIView(APIView):
    authentication_classes = [CustomJWEAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = CreateFolderSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user = request.user
        folder_name = serializer.validated_data['name']
        parent_uid = serializer.validated_data.get('parent_uid')

        parent = None
        if parent_uid:
            try:
                parent = FileObject.objects.get(uid=parent_uid, type="folder", trashed_at__isnull=True)
            except FileObject.DoesNotExist:
                return Response({"error": "Invalid parent folder UID."}, status=404)

            # Access check
            if parent.owner != user:
                has_editor_access = FileAccessControl.objects.filter(
                    file=parent,
                    user=user,
                    access_level="editor"
                ).exists()
                if not has_editor_access:
                    return Response({"error": "No permission to create folder here."}, status=403)

        # ✅ Create folder
        new_folder = FileObject.objects.create(
            uid=uuid4(),
            owner=user,
            name=folder_name,
            type="folder",
            parent=parent
        )

        # ✅ Inherit access from parent
        if parent:
            parent_access_controls = FileAccessControl.objects.filter(file=parent)
            access_entries = [
                FileAccessControl(
                    file=new_folder,
                    user=access.user,
                    access_level=access.access_level
                )
                for access in parent_access_controls
            ]
            FileAccessControl.objects.bulk_create(access_entries)

        return Response({
            "message": "Folder created successfully.",
            "folder": {
                "uid": str(new_folder.uid),
                "name": new_folder.name,
                "parent_id": str(parent.uid) if parent else None
            }
        }, status=201)
