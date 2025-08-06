from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from accounts.serializers.auth import LoginSerializer, RegisterSerializer
from accounts.serializers.auth import LogoutSerializer, RefreshTokenSerializer
from accounts.models import JoinRequest, CustomUser
from accounts.tasks import send_registration_pending_email_async
from accounts.utils.jwe_utils import decrypt_jwe
from django.utils import timezone
from django.contrib.auth.models import Group
from notifications.models import Notification
import uuid
from django_ratelimit.decorators import ratelimit
from django.utils.decorators import method_decorator
from accounts.utils.ratelimit import custom_ratelimit, user_or_ip_key
from accounts.utils.security import check_lockout, record_failed_attempt, reset_failed_attempts
from django.conf import settings

@method_decorator(custom_ratelimit(key_func=user_or_ip_key, rate='3/m', block=True), name='dispatch')
class RegisterView(APIView):
    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()

            # Create a pending join request
            JoinRequest.objects.create(
                uid=uuid.uuid4(),
                user=user,
                message="Requesting access to join the organisation.",
                status="pending",
                created_at=timezone.now()
            )
            # ✅ Send registration pending approval email
            send_registration_pending_email_async(str(user.pk))
            try:
                # ✅ Notify all ClientAdmins
                client_admin_group = Group.objects.get(name="ClientAdmin")
                client_admins = client_admin_group.user_set.all()

                notifications = [
                    Notification(
                        type="alert",
                        title="New Join Request",
                        message=f"{user.email} has requested to join the organisation.",
                        recipient=admin
                    )
                    for admin in client_admins
                ]
                Notification.objects.bulk_create(notifications)
            except Group.DoesNotExist:
                pass

            return Response({
                "message": "Registration successful. Awaiting approval by ClientAdmin."
            }, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@method_decorator(custom_ratelimit(key_func=user_or_ip_key, rate='5/m', block=True), name='dispatch')
class LoginView(APIView):
    permission_classes = [AllowAny]
    
    def post(self, request):
        ip = request.META.get('REMOTE_ADDR')
        
        # ✅ Check lockout
        allowed, wait = check_lockout(None, ip, 'login')
        if not allowed:
            return Response(
                {"detail": f"Account temporarily locked. Retry after {wait} seconds."},
                status=status.HTTP_403_FORBIDDEN
            )
            
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            user = getattr(serializer, 'user', None)
            reset_failed_attempts(user, ip, 'login')
            return Response(serializer.validated_data, status=status.HTTP_200_OK)
        
        # ✅ Record failed attempt
        record_failed_attempt(None, ip, 'login')
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@method_decorator(custom_ratelimit(key_func=user_or_ip_key, rate='10/m', block=True), name='dispatch')
class RefreshTokenView(APIView):
    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = RefreshTokenSerializer(data=request.data)
        if serializer.is_valid():
            return Response(serializer.validated_data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
class AccessTokenVerifyView(APIView):
    permission_classes = [AllowAny]
    
    def post(self, request):
        token = request.data.get("access_token")
        if not token:
            return Response({"error": "Access token required"}, status=400)

        try:
            payload = decrypt_jwe(token)
        except Exception:
            return Response({"valid": False, "error": "Invalid or expired token"}, status=401)

        if payload.get("type") != "access":
            return Response({"valid": False, "error": "Not an access token"}, status=400)

        uid = payload.get("uid")
        token_version = payload.get("access_token_version")

        try:
            user = CustomUser.objects.get(uid=uid)
        except CustomUser.DoesNotExist:
            return Response({"valid": False, "error": "User not found"}, status=404)

        if user.access_token_version != token_version:
            return Response({"valid": False, "error": "Token is stale"}, status=403)

        return Response({
            "valid": True,
            "user_id": str(user.uid),
            "email": user.email
        }, status=200)
        
@method_decorator(custom_ratelimit(key_func=user_or_ip_key, rate='15/m', block=True), name='dispatch')
class LogoutView(APIView):
    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        if serializer.is_valid():
            return Response(serializer.validated_data, status=200)
        return Response(serializer.errors, status=400)