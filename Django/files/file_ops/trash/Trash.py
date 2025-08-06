from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from django.utils import timezone
from django.db import transaction
from uuid import UUID
import requests
from accounts.authentication import CustomJWEAuthentication
from files.models import FileObject, FileVersion, TrashAutoCleanQueue, FileActionLog
from sharing.models import FileAccessControl


FASTAPI_TRASH_URL = "http://127.0.0.1:8081/trash_files_bulk"
FASTAPI_DELETE_FILE_URL = "http://127.0.0.1:8081/delete_file"


class TrashFileAPIView(APIView):
    authentication_classes = [CustomJWEAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        file_uid = request.data.get("file_uid")
        if not file_uid:
            return Response({"error": "file_uid is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            file_uuid = UUID(file_uid)
        except Exception:
            return Response({"error": "Invalid file_uid."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            file_obj = FileObject.objects.get(uid=file_uuid, trashed_at__isnull=True)
        except FileObject.DoesNotExist:
            return Response({"error": "File or folder not found or already trashed."}, status=status.HTTP_404_NOT_FOUND)

        user = request.user

        # Permission check: owner or editor can trash
        if file_obj.owner != user:
            has_editor_access = FileAccessControl.objects.filter(
                file=file_obj, user=user, access_level="editor"
            ).exists()
            if not has_editor_access:
                return Response({"error": "No permission to trash this file or folder."}, status=status.HTTP_403_FORBIDDEN)

        # Gather all files to trash (including descendants if folder)
        if file_obj.type == "folder":
            files_to_trash = self.get_all_descendant_files(file_obj)
        else:
            files_to_trash = [file_obj]

        if not files_to_trash:
            return Response({"error": "No files found to trash."}, status=status.HTTP_400_BAD_REQUEST)

        trash_payload = []
        older_versions_payload = []

        for fobj in files_to_trash:
            versions = list(FileVersion.objects.filter(file=fobj).order_by('version_number'))
            if not versions:
                continue
            latest_version = versions[-1]
            older_versions = versions[:-1]

            initial_filename = latest_version.initial_filename_snapshot or fobj.name

            # Prepare trash payload for latest version
            trash_payload.append({
                "file_uid": str(fobj.uid),
                "filename": initial_filename,
                "latest_version_id": latest_version.s3_version_id
            })

            # Prepare delete payload for older versions
            for v in older_versions:
                if v.s3_version_id:
                    older_versions_payload.append({
                        "filename": initial_filename,
                        "version_id": v.s3_version_id,
                        "file_version_uid": str(v.uid)  # optional for later DB update
                    })

        if not trash_payload:
            return Response({"error": "No eligible file versions found to trash."}, status=status.HTTP_400_BAD_REQUEST)

        headers = {"Authorization": f"Bearer {request.auth}"}

        # Step 1: Trash (Move latest versions to Glacier)
        try:
            resp = requests.post(FASTAPI_TRASH_URL, json={"files": trash_payload}, headers=headers, timeout=120)
            if resp.status_code != 200:
                return Response({"error": f"FastAPI trash error: {resp.text}"}, status=resp.status_code)
            trash_results = resp.json()  # List of dicts with file_uid and new_version_id
        except requests.RequestException as e:
            return Response({"error": f"FastAPI trash request failed: {str(e)}"}, status=status.HTTP_502_BAD_GATEWAY)

        with transaction.atomic():
            # Update latest versions and FileObjects
            for result in trash_results:
                uid = result.get("file_uid")
                new_version_id = result.get("new_version_id")
                if not uid or not new_version_id:
                    continue
                # Update latest version and FileObject latest_version_id and trashed_at
                try:
                    latest_version = FileVersion.objects.filter(file__uid=uid).order_by("-version_number").first()
                    latest_version.s3_version_id = new_version_id
                    latest_version.storage_class = "GLACIER"
                    latest_version.restore_status = "available"
                    latest_version.save()

                    file_obj_update = FileObject.objects.get(uid=uid)
                    file_obj_update.latest_version_id = new_version_id
                    file_obj_update.trashed_at = timezone.now()
                    file_obj_update.save()

                    # Log trash action per file
                    FileActionLog.objects.create(
                        file=file_obj_update,
                        action="trashed",
                        performed_by=user,
                        performed_at=timezone.now(),
                        reason="File trashed and moved to glacier storage."
                    )
                except FileObject.DoesNotExist:
                    continue

            # Step 2: Delete older versions from S3 and DB
            for old_ver in older_versions_payload:
                try:
                    del_resp = requests.delete(
                        f"{FASTAPI_DELETE_FILE_URL}/{old_ver['filename']}",
                        params={"version_id": old_ver['version_id']},
                        headers=headers
                    )
                    if del_resp.status_code == 200:
                        # Remove FileVersion record permanently
                        FileVersion.objects.filter(uid=old_ver["file_version_uid"]).delete()
                except requests.RequestException:
                    # Optionally log failure and continue
                    pass

            # Mark trashed folders' trashed_at recursively
            if file_obj.type == "folder":
                self.mark_folders_trashed(file_obj, timezone.now())
            else:
                if file_obj.parent and file_obj.parent.trashed_at is None:
                    self.mark_folders_trashed(file_obj.parent, timezone.now())

        return Response({
            "message": f"Trash process completed for {len(trash_payload)} file(s) and related folders."
        }, status=status.HTTP_200_OK)

    def get_all_descendant_files(self, folder):
        descendants = []
        children = FileObject.objects.filter(parent=folder, trashed_at__isnull=True)
        for child in children:
            if child.type == "folder":
                descendants.extend(self.get_all_descendant_files(child))
            else:
                descendants.append(child)
        return descendants

    def mark_folders_trashed(self, folder, trashed_time):
        folder.trashed_at = trashed_time
        folder.save(update_fields=["trashed_at"])
        if folder.parent and folder.parent.trashed_at is None:
            self.mark_folders_trashed(folder.parent, trashed_time)
