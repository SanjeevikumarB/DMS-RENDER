from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from accounts.utils.jwe_utils import decrypt_jwe
from accounts.models import CustomUser
from django.utils.timezone import now
from django.utils.dateparse import parse_datetime
 
class CustomJWEAuthentication(BaseAuthentication):
    def authenticate(self, request):
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith("Bearer "):
            return None
 
        token = auth_header.split("Bearer ")[1]
        try:
            payload = decrypt_jwe(token)
        except Exception:
            raise AuthenticationFailed("Invalid or expired token.")
 
        if payload.get("type") != "access":
            raise AuthenticationFailed("Expected access token.")
 
        exp_timestamp = payload.get("exp")
        if not exp_timestamp:
            raise AuthenticationFailed("Token missing expiration claim.")
 
        exp_datetime = parse_datetime(exp_timestamp)
        if not exp_datetime:
            raise AuthenticationFailed("Invalid expiration timestamp format.")
 
        if now() > exp_datetime:
            raise AuthenticationFailed("Access token has expired.")
 
        uid = payload.get("uid")
        token_version = payload.get("access_token_version")

        try:
            user = CustomUser.objects.get(uid=uid)
        except CustomUser.DoesNotExist:
            raise AuthenticationFailed("User not found.")
        
        if user.access_token_version != token_version:
            raise AuthenticationFailed("Token is stale or revoked.")
 
        return (user, token)
 
 