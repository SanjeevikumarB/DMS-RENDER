from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from django.utils import timezone
from django.db import transaction
from accounts.authentication import CustomJWEAuthentication
from sharing.models import FileShareRequest, FileAccessControl
from files.models import FileObject
from notifications.models import Notification

class ProcessAccessUpgradeAPIView(APIView):
    authentication_classes = [CustomJWEAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        share_request_uid = request.data.get("share_request_uid")
        action = request.data.get("action")  # "approve" or "reject"
        reason = request.data.get("reason", "")

        if action not in ["approve", "reject"]:
            return Response({"error": "Action must be 'approve' or 'reject'."}, status=400)

        try:
            access_request = FileShareRequest.objects.select_related("file", "requester", "target_user").get(uid=share_request_uid)
        except FileShareRequest.DoesNotExist:
            return Response({"error": "Access request not found."}, status=404)

        file_obj = access_request.file
        owner = file_obj.owner

        if request.user != owner:
            return Response({"error": "Only the file owner can approve or reject this request."}, status=403)
        if access_request.status != "pending":
            return Response({"error": f"Request is already {access_request.status}."}, status=400)

        with transaction.atomic():
            if action == "approve":
                # Grant elevated access to target_user (requester)
                fac, _ = FileAccessControl.objects.update_or_create(
                    file=file_obj,
                    user=access_request.target_user,
                    defaults={
                        "access_level": access_request.access_type,
                        "granted_by": owner,
                        "granted_at": timezone.now(),
                        "inherited": False,
                        "inherited_from": None
                    }
                )
                # Inherit access for descendants (if folder)
                if file_obj.type == "folder":
                    descendants = self.get_all_descendants(file_obj)
                    for child in descendants:
                        if not FileAccessControl.objects.filter(
                            file=child, user=access_request.target_user, inherited=False
                        ).exists():
                            FileAccessControl.objects.update_or_create(
                                file=child,
                                user=access_request.target_user,
                                defaults={
                                    "access_level": access_request.access_type,
                                    "granted_by": owner,
                                    "granted_at": timezone.now(),
                                    "inherited": True,
                                    "inherited_from": file_obj
                                }
                            )
                access_request.status = "approved"
                access_request.reviewed_by = owner
                access_request.reviewed_at = timezone.now()
                access_request.reason = reason
                access_request.save()

                # Notify requester of approval
                Notification.objects.create(
                    recipient=access_request.requester,
                    type="access_upgrade_approved",
                    title=f"Access level raised for '{file_obj.name}'",
                    message=f"Your request for '{access_request.access_type}' access to '{file_obj.name}' has been approved.",
                    related_file=file_obj
                )
            else:
                access_request.status = "rejected"
                access_request.reviewed_by = owner
                access_request.reviewed_at = timezone.now()
                access_request.reason = reason
                access_request.save()
                # Notify requester of rejection
                Notification.objects.create(
                    recipient=access_request.requester,
                    type="access_upgrade_rejected",
                    title=f"Access upgrade request rejected",
                    message=f"Your request for '{access_request.access_type}' access to '{file_obj.name}' was rejected. {reason}",
                    related_file=file_obj
                )

        return Response({"message": f"Request {action}ed."}, status=200)

    def get_all_descendants(self, folder):
        descendants = []
        children = FileObject.objects.filter(parent=folder, trashed_at__isnull=True)
        for child in children:
            descendants.append(child)
            if child.type == "folder":
                descendants.extend(self.get_all_descendants(child))
        return descendants
