from datetime import timedelta
import requests
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.utils.timezone import now
from accounts.models import CustomUser, JoinRequest, UserSessions
from accounts.utils.token_utils import create_access_token, create_refresh_token
from accounts.utils.ratelimit import custom_ratelimit, user_or_ip_key
from django.utils.decorators import method_decorator
import uuid

@method_decorator(custom_ratelimit(key_func=user_or_ip_key, rate='5/m', block=True), name='dispatch')
class GoogleOAuthView(APIView):
    permission_classes = [AllowAny]
    
    def post(self, request):
        # code = request.data.get("code")  # For production (React Native)
        google_access_token = request.data.get("google_access_token")  # For Postman testing

        # # ✅ Method 1: Exchange code for token (commented for now)
        # if code:
        #     token_url = "https://oauth2.googleapis.com/token"
        #     token_data = {
        #         "code": code,
        #         "client_id": settings.GOOGLE_CLIENT_ID,
        #         "client_secret": settings.GOOGLE_CLIENT_SECRET,
        #         "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        #         "grant_type": "authorization_code"
        #     }
        #     token_response = requests.post(token_url, data=token_data)
        #     token_json = token_response.json()

        #     if "access_token" not in token_json:
        #         return Response({"error": "Failed to get token", "details": token_json}, status=400)
              
        #     google_access_token = token_json["access_token"]

        # ✅ Method 2: If token provided (Postman)
        if not google_access_token:
            return Response({"error": "Missing code or Google access token"}, status=400)




        # ✅ Fetch user info from Google - SAME FOR BOTH METHODS
        user_info = requests.get(
            "https://www.googleapis.com/oauth2/v1/userinfo",
            params={"access_token": google_access_token}
        ).json()

        email = user_info.get("email")
        name = user_info.get("name", "")
        picture = user_info.get("picture", "")

        if not email:
            return Response({"error": "Email not found in Google account"}, status=400)

        # ✅ Check user existence or create
        user, created = CustomUser.objects.get_or_create(email=email, defaults={
            "username": name or None,
            "profile_picture": picture or None,
            "is_active": False  # New users need admin approval
        })

        if created:
            JoinRequest.objects.create(
                uid=uuid.uuid4(),
                user=user,
                message="Requesting access to join the organisation.",
                status="pending",
                created_at=now()
            )
            return Response({"message": "Account created successfully. Waiting for admin approval."}, status=201)

        if not user.is_active:
            return Response({"error": "Account inactive. Waiting for admin approval."}, status=403)

        # ✅ Generate tokens
        current_time = now()
        user.last_login = current_time
        user.access_token_version += 1
        user.save()

        # Invalidate old sessions
        UserSessions.objects.filter(user_id=user.uid).update(is_active=False)

        access_token = create_access_token(user)
        refresh_token = create_refresh_token(user)

        # Save new session
        UserSessions.objects.create(
            id=uuid.uuid4(),
            user=user,
            refresh_token=refresh_token,
            created_at=current_time,
            expires_at=current_time + timedelta(days=7),
            is_active=True
        )

        return Response({
            "message": "Login successful",
            "user_id": str(user.uid),
            "email": user.email,
            "access_token": access_token,
            "refresh_token": refresh_token
        }, status=200)
