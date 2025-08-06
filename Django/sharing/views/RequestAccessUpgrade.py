from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from accounts.authentication import CustomJWEAuthentication
from files.models import FileObject
from sharing.models import FileAccessControl, FileShareRequest
from notifications.models import Notification

class RequestAccessUpgradeAPIView(APIView):
    authentication_classes = [CustomJWEAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        file_uid = request.data.get("file_uid")
        requested_access = request.data.get("requested_access_level")

        if not file_uid or requested_access not in ["viewer", "editor"]:
            return Response({"error": "file_uid and a valid requested_access_level are required."}, status=400)

        try:
            file_obj = FileObject.objects.get(uid=file_uid, trashed_at__isnull=True)
        except FileObject.DoesNotExist:
            return Response({"error": "File not found."}, status=404)

        # Check current access level for user on this file/folder
        fac = FileAccessControl.objects.filter(file=file_obj, user=user).first()
        if not fac:
            return Response({"error": "You do not have access to this file/folder to request an upgrade."}, status=403)

        current_access = fac.access_level
        # If user already has requested or higher access, reject the request
        access_levels = {"viewer": 1, "editor": 2}
        if access_levels.get(requested_access) <= access_levels.get(current_access):
            return Response({"error": f"You already have {current_access} or higher access."}, status=400)

        # Only owner can grant approval, so identify owner
        owner = file_obj.owner

        # If user is owner (unlikely to request upgrade) - deny or say already full access
        if user == owner:
            return Response({"error": "Owner already has full access."}, status=400)

        # Check if there's already a pending request for this user and target access
        existing_request = FileShareRequest.objects.filter(
            file=file_obj,
            requester=user,
            target_user=user,
            access_type=requested_access,
            status='pending'
        ).first()

        if existing_request:
            return Response({"error": "You already have a pending access upgrade request for this file."}, status=400)

        # Create the access upgrade request
        access_request = FileShareRequest.objects.create(
            file=file_obj,
            requester=user,
            target_user=user,
            access_type=requested_access,
            status="pending"
        )

        # Notify owner about this request
        Notification.objects.create(
            recipient=owner,
            type="access_upgrade_requested",
            title=f"Access upgrade request for '{file_obj.name}'",
            message=f"{user.email} has requested '{requested_access}' access to '{file_obj.name}'.",
            related_file=file_obj
        )

        return Response({
            "message": "Access upgrade request submitted successfully and owner has been notified.",
            "request_id": str(access_request.uid)
        }, status=201)