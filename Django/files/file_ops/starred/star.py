from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from accounts.authentication import CustomJWEAuthentication

from files.models import FileObject, StarredFile
from sharing.models import FileAccessControl
from django.shortcuts import get_object_or_404

class ToggleStarAPIView(APIView):
    authentication_classes = [CustomJWEAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        file_uid = request.data.get('file_uid')
        if not file_uid:
            return Response({"error": "file_uid is required."}, status=status.HTTP_400_BAD_REQUEST)

        file = get_object_or_404(FileObject, uid=file_uid)

        user = request.user

        # ✅ Check access: owner or has access control entry
        if file.owner != user and not FileAccessControl.objects.filter(file=file, user=user).exists():
            return Response({"error": "You do not have permission to star this file or folder."},
                            status=status.HTTP_403_FORBIDDEN)

        starred_entry, created = StarredFile.objects.get_or_create(user=user, file=file)

        if not created:
            # Already starred — toggle to unstar
            starred_entry.delete()
            return Response({
                "message": "File unstarred.",
                "file_uid": str(file.uid),
                "is_starred": False
            }, status=status.HTTP_200_OK)

        # File is now starred
        return Response({
            "message": "File starred.",
            "file_uid": str(file.uid),
            "is_starred": True
        }, status=status.HTTP_201_CREATED)
