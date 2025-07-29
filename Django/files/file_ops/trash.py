# from rest_framework.views import APIView
# from rest_framework.response import Response
# from rest_framework import status, permissions
# from django.utils import timezone
# from django.db import transaction

# from files.models import FileObject, TrashAutoCleanQueue
# from datetime import timedelta


# class TrashFileOrFolderAPIView(APIView):
#     permission_classes = [permissions.IsAuthenticated]

#     def post(self, request):
#         uid = request.data.get("uid")
#         if not uid:
#             return Response({"error": "Missing file/folder UID"}, status=status.HTTP_400_BAD_REQUEST)

#         try:
#             file_obj = FileObject.objects.get(uid=uid, owner=request.user)
#         except FileObject.DoesNotExist:
#             return Response({"error": "File or folder not found or access denied."}, status=status.HTTP_404_NOT_FOUND)

#         if file_obj.trashed_at:
#             return Response({"message": "Item is already in trash."}, status=status.HTTP_200_OK)

#         trashed_at = timezone.now()
#         auto_delete_at = trashed_at + timedelta(days=30)  # Auto-delete in 30 days

#         with transaction.atomic():
#             # Soft-delete the selected item
#             file_obj.trashed_at = trashed_at
#             file_obj.save()

#             # Recursively trash children (if folder)
#             if file_obj.type == "folder":
#                 self._trash_children(file_obj, trashed_at)

#             # Create cleanup entry
#             TrashAutoCleanQueue.objects.create(
#                 file=file_obj,
#                 scheduled_delete_at=auto_delete_at,
#                 status="scheduled"
#             )

#         return Response({"message": "Moved to trash successfully."}, status=status.HTTP_200_OK)

#     def _trash_children(self, folder, trashed_at):
#         for child in folder.children.all():
#             if not child.trashed_at:
#                 child.trashed_at = trashed_at
#                 child.save()
#                 if child.type == "folder":
#                     self._trash_children(child, trashed_at)
