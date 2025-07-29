from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from django.shortcuts import get_object_or_404
from accounts.authentication import CustomJWEAuthentication
from files.models import FileObject
from sharing.models import FileAccessControl
from files.models import FileObject
from sharing.models import FileAccessControl
from ...serializers import AccessInfoSerializer, SharedUserSerializer  # We'll define these below

class FileInfoAPIView(APIView):
    authentication_classes = [CustomJWEAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, file_uid):
        user = request.user

        file = get_object_or_404(FileObject, uid=file_uid, trashed_at__isnull=True)

        # 1. Check access
        is_owner = file.owner == user
        access_control = FileAccessControl.objects.filter(file=file, user=user).first()

        if not is_owner and not access_control:
            return Response({"error": "You do not have access to this file/folder."}, status=403)

        # 2. Path
        path = []
        curr = file.parent
        while curr:
            path.insert(0, curr.name)
            curr = curr.parent
        if file.type == "file":
            path.append(file.name)

        # 3. Starred check
        is_starred = file.starred_by.filter(uid=user.uid).exists()

        # 4. Access Info (your level)
        if is_owner:
            access_info = {
                "your_level": "owner",
                "shared_by": None,
                "inherited": False,
                "inherited_from": None,
            }
        else:
            access_info = AccessInfoSerializer(access_control).data

        # 5. Shared users (exclude inherited)
        shared_users_qs = FileAccessControl.objects.filter(file=file, inherited=False).select_related('user', 'granted_by')
        shared_users = SharedUserSerializer(shared_users_qs, many=True).data

        # 6. Build response
        response_data = {
            "uid": str(file.uid),
            "name": file.name,
            "type": file.type,
            "description": file.description,
            "extension": file.extension,
            "size": file.size,
            "path": path,
            "is_starred": is_starred,
            "uploaded_url": file.metadata.get("cdn_url") if file.metadata else None,
            "presigned_url": file.metadata.get("presigned_url") if file.metadata else None,
            "latest_version_id": file.metadata.get("version_id") if file.metadata else None,
            "owner": {
                "id": str(file.owner.uid),
                "email": file.owner.email,
                "full_name": file.owner.username,
            },
            "created_at": file.created_at,
            "modified_at": file.modified_at,
            "accessed_at": file.accessed_at,
            "trashed_at": file.trashed_at,
            "tags": file.tags or [],
            "access_info": access_info,
            "shared_users": shared_users,
        }

        return Response(response_data, status=200)