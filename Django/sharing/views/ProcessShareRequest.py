from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from django.utils import timezone
from django.db import transaction
from accounts.authentication import CustomJWEAuthentication
from sharing.models import FileShareRequest, FileAccessControl
from files.models import FileObject
from notifications.models import Notification

class ProcessShareRequestAPIView(APIView):
    authentication_classes = [CustomJWEAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        share_request_uid = request.data.get("share_request_uid")
        action = request.data.get("action")  # "approve" or "reject"
        reason = request.data.get("reason", "")

        # Validation
        if action not in ["approve", "reject"]:
            return Response({"error": "Action must be 'approve' or 'reject'."}, status=400)

        try:
            share_request = FileShareRequest.objects.select_related("file", "requester", "target_user").get(uid=share_request_uid)
        except FileShareRequest.DoesNotExist:
            return Response({"error": "Share request not found."}, status=404)

        file_obj = share_request.file
        owner = file_obj.owner

        # Only owner can process
        if request.user != owner:
            return Response({"error": "Only file owner can process this request."}, status=403)
        if share_request.status != "pending":
            return Response({"error": f"Request is already {share_request.status}."}, status=400)

        with transaction.atomic():
            # Approval flow
            if action == "approve":
                # Grant access to target_user
                fac, _ = FileAccessControl.objects.update_or_create(
                    file=file_obj,
                    user=share_request.target_user,
                    defaults={
                        "access_level": share_request.access_type,
                        "granted_by": owner,
                        "granted_at": timezone.now(),
                        "inherited": False,
                        "inherited_from": None
                    }
                )
                # Inherit to children if folder
                if file_obj.type == "folder":
                    descendants = self.get_all_descendants(file_obj)
                    for child in descendants:
                        if not FileAccessControl.objects.filter(file=child, user=share_request.target_user, inherited=False).exists():
                            FileAccessControl.objects.update_or_create(
                                file=child,
                                user=share_request.target_user,
                                defaults={
                                    "access_level": share_request.access_type,
                                    "granted_by": owner,
                                    "granted_at": timezone.now(),
                                    "inherited": True,
                                    "inherited_from": file_obj
                                }
                            )
                share_request.status = "approved"
                share_request.reviewed_by = owner
                share_request.reviewed_at = timezone.now()
                share_request.reason = reason
                share_request.save()

                # Notify target user
                Notification.objects.create(
                    recipient=share_request.target_user,
                    type="share_granted",
                    title=f"Access granted to '{file_obj.name}'",
                    message=f"You have been granted {share_request.access_type} access to '{file_obj.name}'.",
                    related_file=file_obj
                )
                # Notify editor (requester)
                Notification.objects.create(
                    recipient=share_request.requester,
                    type="request_approved",
                    title=f"Share request approved",
                    message=f"Your share request for '{file_obj.name}' with {share_request.target_user.email} has been approved.",
                    related_file=file_obj
                )

            else:  # action == reject
                share_request.status = "rejected"
                share_request.reviewed_by = owner
                share_request.reviewed_at = timezone.now()
                share_request.reason = reason
                share_request.save()
                # Notify editor (requester)
                Notification.objects.create(
                    recipient=share_request.requester,
                    type="request_rejected",
                    title=f"Share request rejected",
                    message=f"Your request to share '{file_obj.name}' with {share_request.target_user.email} was rejected. {reason}",
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
