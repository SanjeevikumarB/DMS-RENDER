from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from accounts.authentication import CustomJWEAuthentication
from files.models import FileObject, StarredFile
from sharing.models import FileAccessControl
from django.db.models import Prefetch
from collections import defaultdict

class SharedWithMeAPIView(APIView):
    authentication_classes = [CustomJWEAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        # Prefetch all FileObject entries shared with this user
        access_entries = FileAccessControl.objects.filter(user=user).select_related(
            "file", "file__parent", "file__owner", "granted_by"
        )
        shared_file_uids = [entry.file.uid for entry in access_entries]
        starred_uids = set(
            str(sid) for sid in StarredFile.objects.filter(user=user, file_id__in=shared_file_uids).values_list("file__uid", flat=True)
        )

        shared = []
        for access in access_entries:
            file_obj = access.file
            path = self.build_path(file_obj)

            shared.append({
                "uid": str(file_obj.uid),
                "name": file_obj.name,
                "type": file_obj.type,
                "path": path,
                "extension": file_obj.extension,
                "size": file_obj.size,
                "uploaded_url": file_obj.uploaded_url,
                "is_starred": str(file_obj.uid) in starred_uids,
                "access_level": access.access_level,
                "owner_email": file_obj.owner.email,
                "shared_by": access.granted_by.full_name if access.granted_by and hasattr(access.granted_by, 'full_name') else (access.granted_by.email if access.granted_by else None),
                "modified_at": file_obj.modified_at,
                "inherited": access.inherited,
                "inherited_from": str(access.inherited_from.uid) if access.inherited and access.inherited_from else None
            })

        return Response({"shared": shared})

    def build_path(self, file_obj):
        path = []
        current = file_obj
        while current:
            path.insert(0, current.name)
            current = current.parent
        return path
