# accounts/views/notifications_views.py

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, NotFound
from django.shortcuts import get_object_or_404
from uuid import UUID
from notifications.models import Notification
from accounts.serializers.notifications import NotificationSerializer
from accounts.permissions import IsRegularUser
from accounts.permissions import IsClientAdmin

class NotificationListView(APIView):
    permission_classes = [IsAuthenticated, IsClientAdmin | IsRegularUser]

    def get(self, request):
        notifications = Notification.objects.filter(
            recipient=request.user
        ).order_by("-created_at")

        serializer = NotificationSerializer(notifications, many=True)
        return Response(serializer.data)
    
class UnreadNotificationListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        notifications = Notification.objects.filter(recipient=request.user, read=False).order_by("-created_at")
        serializer = NotificationSerializer(notifications, many=True)
        return Response(serializer.data)

class MarkNotificationReadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, uid):
        try:
            uid = UUID(str(uid))  # validate UID format
        except ValueError:
            return Response({"detail": "Invalid UID."}, status=400)

        # Step 1: Try to get the notification by UID
        try:
            notification = Notification.objects.get(uid=uid)
        except Notification.DoesNotExist:
            raise NotFound("Notification not found.")

        # Step 2: Check ownership
        if notification.recipient != request.user:
            raise PermissionDenied("You are not authorized to mark this notification.")

        if notification.read:
            return Response({"detail": "Notification already marked as read."})

        notification.read = True
        notification.save()

        return Response({"detail": "Notification marked as read."})
    
class MarkAllNotificationsReadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        unread_qs = Notification.objects.filter(recipient=request.user, read=False)
        updated_count = unread_qs.update(read=True)
        return Response({
            "detail": f"{updated_count} notifications marked as read."
        })

class MarkNotificationUnreadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, uid):
        try:
            uid = UUID(str(uid))  # Validate UID format
        except ValueError:
            return Response({"detail": "Invalid UID."}, status=400)

        try:
            notification = Notification.objects.get(uid=uid)
        except Notification.DoesNotExist:
            raise NotFound("Notification not found.")

        if notification.recipient != request.user:
            raise PermissionDenied("You are not authorized to modify this notification.")

        if not notification.read:
            return Response({"detail": "Notification is already unread."})

        notification.read = False
        notification.save()

        return Response({"detail": "Notification marked as unread."})

class DeleteNotificationView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, uid):
        try:
            uid = UUID(str(uid))  # Validate UID
        except ValueError:
            return Response({"detail": "Invalid UID."}, status=400)

        try:
            notification = Notification.objects.get(uid=uid)
        except Notification.DoesNotExist:
            raise NotFound("Notification not found.")

        if notification.recipient != request.user:
            raise PermissionDenied("You are not authorized to delete this notification.")

        notification.delete()

        return Response({"detail": "Notification deleted successfully."}, status=204)

class ClearAllNotificationsView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request):
        deleted_count, _ = Notification.objects.filter(recipient=request.user).delete()

        return Response({
            "detail": f"Deleted {deleted_count} notifications."
        }, status=200)