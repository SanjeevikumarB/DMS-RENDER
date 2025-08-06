import random
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import NotFound, PermissionDenied
from accounts.permissions import IsRegularUser, IsSuperAdmin
from accounts.permissions import IsClientAdmin
from rest_framework import status
import uuid
from django.utils.timezone import now
from rest_framework.permissions import AllowAny
from django.contrib.auth.models import Group
from accounts.tasks import send_account_deleted_email_async, send_account_deletion_email_async, send_password_reset_status_email_async, send_set_password_status_email_async
from notifications.models import Notification
from accounts.models import CustomUser, PasswordResetOTP
from accounts.serializers.user_management import ChangePasswordSerializer, DeleteAccountOTPRequestSerializer, DeleteAccountSerializer, PasswordResetConfirmSerializer, PasswordResetOTPRequestSerializer, PasswordResetOTPVerifySerializer, RoleEditRequestCreateSerializer, SetPasswordConfirmSerializer, SetPasswordOTPRequestSerializer, UserProfileSerializer, UserProfileUpdateSerializer
from accounts.serializers.user_management import RoleEditRequestListSerializer
from accounts.serializers.user_management import RoleEditRequestReviewSerializer
from accounts.models import RoleEditRequest
from notifications.models import Notification
from accounts.utils.ratelimit import custom_ratelimit, user_or_ip_key
from django.utils.decorators import method_decorator
from accounts.utils.security import check_lockout, record_failed_attempt, reset_failed_attempts
from accounts.utils.ratelimit import custom_ratelimit, user_or_ip_key

class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserProfileSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)
    def put(self, request):
        serializer = UserProfileUpdateSerializer(request.user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Profile updated successfully."}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@method_decorator(custom_ratelimit(key_func=user_or_ip_key, rate='5/m', block=True), name='dispatch')
class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        ip = request.META.get('REMOTE_ADDR')
        endpoint = 'change_password'  # ✅ unique identifier for config

        # Check lockout before processing
        allowed, wait = check_lockout(request.user, ip, endpoint)
        if not allowed:
            return Response(
                {"detail": f"Too many failed attempts. Retry after {wait} seconds."},
                status=status.HTTP_403_FORBIDDEN
            )
            
        serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
        if serializer.is_valid():
            serializer.save()
            # ✅ Optionally: Invalidate tokens here if you're using token versioning
            request.user.access_token_version += 1
            request.user.save()
            # ✅ Reset failed attempts after success
            reset_failed_attempts(request.user, ip, endpoint)
            return Response({"message": "Password changed successfully."}, status=status.HTTP_200_OK)
        
        # ✅ Record failure if validation fails (wrong old password)
        record_failed_attempt(request.user, ip, endpoint)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@method_decorator(custom_ratelimit(key_func=user_or_ip_key, rate='3/m', block=True), name='dispatch')
class PasswordResetRequestOTPView(APIView):
    permission_classes = [AllowAny]
    def post(self, request):
        serializer = PasswordResetOTPRequestSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "OTP sent to your email."})
        return Response(serializer.errors, status=400)

@method_decorator(custom_ratelimit(key_func=user_or_ip_key, rate='5/m', block=True), name='dispatch')
class PasswordResetVerifyOTPView(APIView):
    permission_classes = [AllowAny]
    def post(self, request):
        ip = request.META.get('REMOTE_ADDR')
        endpoint = 'password_reset_verify'

        # Check lockout
        allowed, wait = check_lockout(None, ip, endpoint)
        if not allowed:
            return Response(
                {"detail": f"Too many failed attempts. Retry after {wait} seconds."},
                status=status.HTTP_403_FORBIDDEN
            )
            
        serializer = PasswordResetOTPVerifySerializer(data=request.data)
        if serializer.is_valid():
            reset_failed_attempts(None, ip, endpoint)
            return Response({"message": "OTP verified successfully."})
        record_failed_attempt(None, ip, endpoint)
        return Response(serializer.errors, status=400)

@method_decorator(custom_ratelimit(key_func=user_or_ip_key, rate='5/m', block=True), name='dispatch')
class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]
    def post(self, request):
        ip = request.META.get('REMOTE_ADDR')
        endpoint = 'password_reset_confirm'
        email = request.data.get("email")

        # Check lockout
        allowed, wait = check_lockout(None, ip, endpoint)
        if not allowed:
            return Response(
                {"detail": f"Too many failed attempts. Retry after {wait} seconds."},
                status=status.HTTP_403_FORBIDDEN
            )
            
        serializer = PasswordResetConfirmSerializer(data=request.data)
        email = request.data.get("email")  # Capture early for async
        if serializer.is_valid():
            serializer.save()
            reset_failed_attempts(None, ip, endpoint)
            # ✅ Send success email asynchronously
            send_password_reset_status_email_async(email, success=True)
            return Response({"message": "Password reset successful."})
        # ✅ Send failure email asynchronously
        record_failed_attempt(None, ip, endpoint)
        if email:
            send_password_reset_status_email_async(email, success=False)
        return Response(serializer.errors, status=400)

@method_decorator(custom_ratelimit(key_func=user_or_ip_key, rate='3/m', block=True), name='dispatch')
class SetPasswordRequestOTPView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = SetPasswordOTPRequestSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "OTP sent to your email."})
        return Response(serializer.errors, status=400)

@method_decorator(custom_ratelimit(key_func=user_or_ip_key, rate='5/m', block=True), name='dispatch')
class SetPasswordVerifyOTPView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        ip = request.META.get('REMOTE_ADDR')
        endpoint = 'password_reset_verify'
        email = request.data.get("email")

        # Check lockout
        allowed, wait = check_lockout(None, ip, endpoint)
        if not allowed:
            return Response(
                {"detail": f"Too many failed attempts. Retry after {wait} seconds."},
                status=status.HTTP_403_FORBIDDEN
            )
            
        serializer = PasswordResetOTPVerifySerializer(data=request.data)
        if serializer.is_valid():
            reset_failed_attempts(None, ip, endpoint)
            return Response({"message": "OTP verified successfully."})
        record_failed_attempt(None, ip, endpoint)
        return Response(serializer.errors, status=400)

@method_decorator(custom_ratelimit(key_func=user_or_ip_key, rate='5/m', block=True), name='dispatch')
class SetPasswordConfirmView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        ip = request.META.get('REMOTE_ADDR')
        endpoint = 'password_reset_confirm'
        email = request.data.get("email")

        # Check lockout
        allowed, wait = check_lockout(None, ip, endpoint)
        if not allowed:
            return Response(
                {"detail": f"Too many failed attempts. Retry after {wait} seconds."},
                status=status.HTTP_403_FORBIDDEN
            )
            
        serializer = SetPasswordConfirmSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            # ✅ Notify user about success
            user_email = serializer.validated_data["email"]
            user = CustomUser.objects.get(email=user_email)

            Notification.objects.create(
                type="success",
                title="Password Set Successfully",
                message="Your password has been set successfully. You can now log in using email/password.",
                recipient=user
            )
            # ✅ Send success email asynchronously
            send_set_password_status_email_async(user_email, "success")
            reset_failed_attempts(None, ip, endpoint)
            return Response({"message": "Password set successfully. You can now log in using email/password."})
        
        # ✅ If validation failed, check if email exists to send failure notification
        email = request.data.get("email")
        if email and CustomUser.objects.filter(email=email).exists():
            user = CustomUser.objects.get(email=email)
            Notification.objects.create(
                type="error",
                title="Password Set Failed",
                message="We couldn't set your password. Please try again after verifying the OTP.",
                recipient=user
            )
            # ✅ Send failure email asynchronously
            send_set_password_status_email_async(email, "failed")
        record_failed_attempt(None, ip, endpoint)
        return Response(serializer.errors, status=400)

class RoleEditRequestCreateView(APIView):
    permission_classes = [IsAuthenticated, IsRegularUser]

    def post(self, request):
        serializer = RoleEditRequestCreateSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            role_request = serializer.save()
            # ✅ Notify all ClientAdmins
            try:
                client_admin_group = Group.objects.get(name="ClientAdmin")
                client_admins = client_admin_group.user_set.all()

                notifications = [
                    Notification(
                        type="alert",
                        title="New Role Edit Request",
                        message=f"{request.user.email} has requested a role change.",
                        recipient=admin
                    )
                    for admin in client_admins
                ]
                Notification.objects.bulk_create(notifications)
            except Group.DoesNotExist:
                # If the group doesn't exist yet, skip notifications silently
                pass
            return Response({
                "message": "Role request submitted successfully.",
                "uid": role_request.uid
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
class RoleEditRequestListView(APIView):
    permission_classes = [IsAuthenticated, IsClientAdmin]

    def get(self, request):
        pending_requests = RoleEditRequest.objects.filter(status="pending").order_by("-created_at")
        serializer = RoleEditRequestListSerializer(pending_requests, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
class RoleEditRequestReviewView(APIView):
    permission_classes = [IsAuthenticated, IsClientAdmin]

    def post(self, request, uid):
        try:
            role_request = RoleEditRequest.objects.get(uid=uid, status="pending")
        except RoleEditRequest.DoesNotExist:
            return Response({"detail": "Role request not found or already reviewed."}, status=404)

        serializer = RoleEditRequestReviewSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        action = serializer.validated_data["action"]
        reason = serializer.validated_data.get("reason", "")
        user = role_request.user

        if action == "approve":
            requested_group = role_request.requested_role
            user.groups.clear()  # Optional: remove previous roles
            user.groups.add(requested_group)

        role_request.status = "approved" if action == "approve" else "rejected"
        role_request.reason = reason
        role_request.reviewed_by = request.user
        role_request.reviewed_at = now()
        role_request.save()
        # ✅ Create Notification
        Notification.objects.create(
            uid=uuid.uuid4(),
            type="role_request",
            title="Role Request Reviewed",
            message=f"Your role request was {role_request.status}.",
            created_at=now(),
            read=False,
            recipient=user,
            related_file_id=None  # or set this if applicable
        )
        
        past_tense = {
            "approve": "approved",
            "reject": "rejected"
        }
        
        return Response({
            "message": f"Role request {past_tense[action]} successfully.",
            "new_role": requested_group.name if action == "approve" else None
        })

class DeleteRegularUserView(APIView):
    permission_classes = [IsAuthenticated, IsClientAdmin]

    def delete(self, request, uid):
        try:
            user = CustomUser.objects.get(uid=uid)
        except CustomUser.DoesNotExist:
            raise NotFound("User not found.")

        # ✅ Use your custom property for regular user check
        if not user.is_regular_user:
            raise PermissionDenied("You can only delete regular users.")

        # Optional: Prevent self-deletion
        if user == request.user:
            raise PermissionDenied("You cannot delete yourself.")
        
        # ✅ Capture details before deletion
        email = user.email
        name = user.username or user.first_name or user.email
        role = "Regular User"

        # ✅ Schedule email
        send_account_deletion_email_async(email, name, role)

        # Option 1: Soft delete  (uncomment below if needed)
        # user.is_active = False
        # user.save()

        # Option 2: Hard delete
        user.delete()

        return Response({"detail": "User deleted successfully."})

class DeleteClientAdminView(APIView):
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def delete(self, request, uid):
        try:
            user = CustomUser.objects.get(uid=uid)
        except CustomUser.DoesNotExist:
            raise NotFound("User not found.")

        if not user.is_client_admin:
            raise PermissionDenied("You can only delete ClientAdmin users.")

        if user == request.user:
            raise PermissionDenied("You cannot delete yourself.")
        
        # ✅ Capture details before deletion
        email = user.email
        name = user.username or user.first_name or user.email
        role = "Client Admin"

        # ✅ Schedule email
        send_account_deletion_email_async(email, name, role)

        user.delete()
        return Response({"detail": "ClientAdmin deleted successfully."}, status=status.HTTP_200_OK)

@method_decorator(custom_ratelimit(key_func=user_or_ip_key, rate='3/m', block=True), name='dispatch')
class DeleteAccountOTPRequestView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = DeleteAccountOTPRequestSerializer(data={}, context={'request': request})
        if serializer.is_valid():
            response_data = serializer.save()
            return Response(response_data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)  

@method_decorator(custom_ratelimit(key_func=user_or_ip_key, rate='2/m', block=True), name='dispatch')
class DeleteAccountView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request):
        ip = request.META.get('REMOTE_ADDR')
        endpoint = 'delete_account'
        email = request.data.get("email")

        # Check lockout
        allowed, wait = check_lockout(None, ip, endpoint)
        if not allowed:
            return Response(
                {"detail": f"Too many failed attempts. Retry after {wait} seconds."},
                status=status.HTTP_403_FORBIDDEN
            )
        serializer = DeleteAccountSerializer(data=request.data, context={"request": request})
        if serializer.is_valid():
            user = request.user
            user_email = user.email  # Store before deleting
            name = user.username or user_email
            
            # ✅ Consume OTP if applicable
            serializer.consume_otp()
            
            user.delete()

            # Send deletion confirmation email asynchronously
            send_account_deleted_email_async(user_email, name)
            reset_failed_attempts(None, ip, endpoint)
            return Response({"message": "Your account has been deleted successfully."}, status=status.HTTP_200_OK)
        record_failed_attempt(None, ip, endpoint)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)