from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth.hashers import make_password
from datetime import timedelta
from django.utils.timezone import now
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password
from accounts.utils.jwe_utils import encrypt_jwe, decrypt_jwe
from accounts.utils.token_utils import create_access_token
from accounts.models import CustomUser, UserSessions
import uuid

class RegisterSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ['email', 'password']
        extra_kwargs = {
            'password': {'write_only': True}
        }

    def validate_email(self, value):
        if CustomUser.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email already exists.")
        return value

    def create(self, validated_data):
        validated_data['password'] = make_password(validated_data['password'])
        validated_data['is_active'] = False  # ClientAdmin will approve later
        return CustomUser.objects.create(**validated_data)


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        email = data.get('email')
        password = data.get('password')

        User = get_user_model()
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise serializers.ValidationError("Invalid email or password.")
        
        if not user.password:
            raise serializers.ValidationError("Password not set. Please use Google Sign-In.")
        
        if not check_password(password, user.password):
            raise serializers.ValidationError("Invalid email or password.")

        if not user.is_active:
            raise serializers.ValidationError("Account inactive. Contact your admin.")

        # Invalidate old access tokens
        current_time = now()
        user.last_login = current_time
        user.access_token_version += 1
        user.save()

        access_payload = {
            "uid": str(user.uid),
            "type": "access",
            "access_token_version": user.access_token_version,
            "exp": (current_time + timedelta(minutes=180)).isoformat()
        }

        refresh_payload = {
            "uid": str(user.uid),
            "type": "refresh",
            "access_token_version": user.access_token_version,
            "exp": (current_time + timedelta(days=7)).isoformat()
        }

        access_token = encrypt_jwe(access_payload)
        refresh_token = encrypt_jwe(refresh_payload)

        # Invalidate previous sessions
        UserSessions.objects.filter(user_id=user.uid).update(is_active=False)

        # Create new session
        UserSessions.objects.create(
            id=uuid.uuid4(),
            user_id=user.uid,
            refresh_token=refresh_token,
            created_at=current_time,
            expires_at=current_time + timedelta(days=7),
            is_active=True
        )

        return {
            "message": "Login successful",
            "user_id": str(user.uid),
            "email": user.email,
            "access_token": access_token,
            "refresh_token": refresh_token
        }




class RefreshTokenSerializer(serializers.Serializer):
    refresh_token = serializers.CharField()

    def validate(self, data):
        token = data['refresh_token']
        
        # 1. Decrypt and validate JWE
        try:
            payload = decrypt_jwe(token)
        except Exception:
            raise serializers.ValidationError("Invalid or expired refresh token.")

        if payload.get("type") != "refresh":
            raise serializers.ValidationError("Invalid token type.")

        user_id = payload.get("uid")
        token_version = payload.get("access_token_version")

        # 2. Fetch user and check token version
        try:
            user = CustomUser.objects.get(uid=user_id)
        except CustomUser.DoesNotExist:
            raise serializers.ValidationError("User not found.")

        if token_version != user.access_token_version:
            raise serializers.ValidationError("Token version mismatch. Please login again.")

        # 3. Find the matching active session
        try:
            session = UserSessions.objects.get(refresh_token=token, is_active=True, user_id=user.uid)
        except UserSessions.DoesNotExist:
            raise serializers.ValidationError("Session expired. Please login again.")
        current_time = now()
        # 4. Create new access and refresh tokens
        new_access_payload = {
            "uid": str(user.uid),
            "type": "access",
            "access_token_version": user.access_token_version,
            "exp": (current_time + timedelta(minutes=180)).isoformat()
        }
        new_refresh_payload = {
            "uid": str(user.uid),
            "type": "refresh",
            "access_token_version": user.access_token_version,
            "exp": (current_time + timedelta(days=7)).isoformat()
        }

        new_access_token = encrypt_jwe(new_access_payload)
        new_refresh_token = encrypt_jwe(new_refresh_payload)

        # 5. Update the existing UserSessions record
        session.refresh_token = new_refresh_token
        session.expires_at = current_time + timedelta(days=7)
        session.save()

        return {
            "access_token": new_access_token,
            "refresh_token": new_refresh_token
        }

class LogoutSerializer(serializers.Serializer):
    refresh_token = serializers.CharField()

    def validate(self, data):
        token = data['refresh_token']
        from accounts.utils.jwe_utils import decrypt_jwe

        try:
            payload = decrypt_jwe(token)
        except Exception:
            raise serializers.ValidationError("Invalid refresh token")

        if payload.get("type") != "refresh":
            raise serializers.ValidationError("Invalid token type")

        user_id = payload.get("uid")

        from accounts.models import CustomUser, UserSessions
        try:
            user = CustomUser.objects.get(uid=user_id)
        except CustomUser.DoesNotExist:
            raise serializers.ValidationError("User not found")

        # Mark session inactive
        updated = UserSessions.objects.filter(user_id=user.uid, refresh_token=token, is_active=True).update(is_active=False)
        if updated == 0:
            raise serializers.ValidationError("Session already invalid or not found")

        # Optional: Invalidate access token too
        user.access_token_version += 1
        user.save()

        return {"message": "Logged out successfully"}