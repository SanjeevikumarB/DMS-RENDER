from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from files.models import FileObject, FileVersion
from accounts.authentication import CustomJWEAuthentication


class ListFilesVersionView(APIView):
    authentication_classes = [CustomJWEAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        file_uid = request.data.get('file_uid')
        if not file_uid:
            return Response({"error": "file_uid is required."}, status=status.HTTP_400_BAD_REQUEST)

        # Ensure only the file owner can see its versions
        try:
            file_obj = FileObject.objects.get(uid=file_uid, owner=request.user)
        except FileObject.DoesNotExist:
            return Response({"error": "File not found or unauthorized."}, status=status.HTTP_404_NOT_FOUND)

        versions = FileVersion.objects.filter(file=file_obj).order_by('-created_at')

        data = [
            {
                "version_id": str(version.uid),
                "version_number": version.version_number,
                "action": version.action,
                "created_at": version.created_at,
                "metadata": version.metadata_snapshot,
            }
            for version in versions
        ]

        return Response(data, status=status.HTTP_200_OK)
