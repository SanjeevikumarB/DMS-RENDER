from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework.generics import ListAPIView

from django.shortcuts import get_object_or_404
from django.utils import timezone
from accounts.tasks import send_join_request_status_email_async, send_welcome_email_async
from notifications.models import Notification
from accounts.models import JoinRequest
from accounts.permissions import IsClientAdmin, IsSuperAdmin
from accounts.serializers.admin import CreateUserSerializer
from accounts.serializers.admin import CreateClientAdminSerializer
from accounts.serializers.admin import JoinRequestSerializer
from accounts.serializers.admin import JoinRequestReviewSerializer

from notifications.models import Notification

class CreateUserByAdminView(APIView):
    permission_classes = [IsAuthenticated, IsClientAdmin]

    def post(self, request):
        serializer = CreateUserSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            # ✅ Send notification to the created user
            Notification.objects.create(
                type="info",
                title="Account Created",
                message="Your account has been successfully created by the Client Admin.",
                recipient=user
            )
            # ✅ Send Welcome Email
            send_welcome_email_async(str(user.uid), is_client_admin=False)
            return Response({"message": "User created successfully", "uid": user.uid}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class CreateClientAdminView(APIView):
    permission_classes = [IsAuthenticated, IsClientAdmin | IsSuperAdmin]

    def post(self, request):
        serializer = CreateClientAdminSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            # ✅ Send notification to the new ClientAdmin
            Notification.objects.create(
                type="success",
                title="Client Admin Access Granted",
                message="You have been granted Client Admin access.",
                recipient=user
            )
            # ✅ Send Client Admin Welcome Email
            send_welcome_email_async(str(user.uid), is_client_admin=True)
            return Response({
                "message": "ClientAdmin created successfully",
                "uid": user.uid
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class JoinRequestListView(ListAPIView):
    queryset = JoinRequest.objects.filter(status='pending').select_related('user')
    serializer_class = JoinRequestSerializer
    permission_classes = [IsAuthenticated, IsClientAdmin | IsSuperAdmin]
    
class JoinRequestReviewView(APIView):
    permission_classes = [IsAuthenticated, IsClientAdmin | IsSuperAdmin]

    def post(self, request, uid):
        join_request = get_object_or_404(JoinRequest, uid=uid, status="pending")
        serializer = JoinRequestReviewSerializer(data=request.data)

        if serializer.is_valid():
            action = serializer.validated_data['action']
            user = join_request.user
            # ✅ Capture details before any deletion
            email = user.email
            name = user.username or user.first_name or user.email

            if action == "approve":
                join_request.status = "approved"
                user.is_active = True
                user.save()
                # ✅ Send notification to the user
                Notification.objects.create(
                    type="success",
                    title="Access Approved",
                    message="Your request to join the organisation has been approved. You can now log in.",
                    recipient=user
                )
                # ✅ Send email in background
                send_join_request_status_email_async(email, name, "approved")

            elif action == "reject":
                send_join_request_status_email_async(email, name, "rejected")  # ✅ Send rejection email
                # No need to update join_request since it will be deleted
                user.delete()  # CASCADE will remove join_request
                return Response({"message": "JoinRequest rejected and user deleted."}, status=status.HTTP_200_OK)


            join_request.reviewed_by = request.user
            join_request.reviewed_at = timezone.now()
            join_request.save()

            return Response({
                "message": f"JoinRequest has been {join_request.status}."
            }, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)