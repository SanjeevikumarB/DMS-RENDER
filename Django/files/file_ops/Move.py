from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q
from files.models import FileObject
from accounts.authentication import CustomJWEAuthentication
from sharing.models import FileAccessControl

class MoveFileOrFolderAPIView(APIView):
    authentication_classes = [CustomJWEAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        file_uid = request.data.get("file_uid")
        target_folder_uid = request.data.get("target_folder_uid")

        if not file_uid:
            return Response({"error": "Missing 'file_uid'."}, status=status.HTTP_400_BAD_REQUEST)

        # Fetch source
        try:
            source = FileObject.objects.get(uid=file_uid, trashed_at__isnull=True)
        except FileObject.DoesNotExist:
            return Response({"error": "File/folder not found or is trashed."}, status=status.HTTP_404_NOT_FOUND)

        if not has_editor_access(user, source):
            return Response({"error": "You do not have permission to move this file/folder."}, status=status.HTTP_403_FORBIDDEN)

        # Prevent self move
        if str(file_uid) == str(target_folder_uid):
            return Response({"error": "Cannot move into itself."}, status=status.HTTP_400_BAD_REQUEST)

        # Target folder
        target_folder = None
        if target_folder_uid:
            try:
                target_folder = FileObject.objects.get(uid=target_folder_uid, type="folder", trashed_at__isnull=True)
            except FileObject.DoesNotExist:
                return Response({"error": "Target folder not found or is trashed."}, status=status.HTTP_404_NOT_FOUND)

            if not has_editor_access(user, target_folder):
                return Response({"error": "You do not have permission to move files into this folder."}, status=status.HTTP_403_FORBIDDEN)

        # No-op move
        if source.parent == target_folder:
            return Response({"message": "Already in the target folder."}, status=status.HTTP_200_OK)

        # Prevent move into descendant
        if source.type == "folder" and target_folder:
            if is_descendant(target_folder, source):
                return Response({"error": "Cannot move a folder into its own subfolder."}, status=status.HTTP_400_BAD_REQUEST)

        # Name conflict check
        name_conflict = FileObject.objects.filter(
            owner=source.owner,
            parent=target_folder,
            name=source.name,
            type=source.type,
            trashed_at__isnull=True
        ).exclude(uid=source.uid).exists()

        if name_conflict:
            return Response({"error": "A file/folder with the same name already exists in the target folder."},
                            status=status.HTTP_409_CONFLICT)

        # Perform the move
        source.parent = target_folder
        source.save(update_fields=["parent", "modified_at"])

        # Inherit editor access from target folder
        if target_folder:
            editors = FileAccessControl.objects.filter(
                file=target_folder,
                access_level="editor"
            ).exclude(user=source.owner)  # Avoid adding owner redundantly

            for editor in editors:
                FileAccessControl.objects.get_or_create(
                    file=source,
                    user=editor.user,
                    defaults={"access_level": "editor"}
                )

            if target_folder.owner != source.owner:
                FileAccessControl.objects.get_or_create(
                    file=source,
                    user=target_folder.owner,
                    defaults={"access_level": "editor"}  # or "viewer", based on your logic
                )

        return Response({"message": "Moved successfully."}, status=status.HTTP_200_OK)


def has_editor_access(user, file_obj):
    return (
        file_obj.owner == user or
        FileAccessControl.objects.filter(file=file_obj, user=user, access_level="editor").exists()
    )


def is_descendant(child_candidate, ancestor):
    """
    Check if `child_candidate` is a descendant of `ancestor`
    """
    current = child_candidate.parent
    while current:
        if current.uid == ancestor.uid:
            return True
        current = current.parent
    return False
