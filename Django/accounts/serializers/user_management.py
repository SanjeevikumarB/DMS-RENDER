from datetime import timedelta
from rest_framework import serializers
from accounts.models import CustomUser, RoleEditRequest
from django.contrib.auth.models import Group
# from django.contrib.auth.password_validation import validate_password
import random
from accounts.models import PasswordResetOTP
from django.utils import timezone
from accounts.tasks import send_account_delete_otp_email_async, send_otp_email_async, send_set_password_otp_email_async

class UserProfileSerializer(serializers.ModelSerializer):
    role = serializers.SerializerMethodField()

    class Meta:
        model = CustomUser
        fields = ["email", "first_name", "last_name", "username", "profile_picture", "role"]

    def get_role(self, obj):
        groups = obj.groups.all()
        return groups[0].name if groups.exists() else "Unassigned"

class UserProfileUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ["first_name", "last_name", "username", "profile_picture"]

class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)

    def validate_old_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Old password is incorrect.")
        return value

    def validate_new_password(self, value):
        user = self.context["request"].user
        if user.check_password(value):
            raise serializers.ValidationError("New password cannot be the same as the old password.")
        # validate_password(value)  # uses Django's built-in validators
        return value

    def save(self, **kwargs):
        user = self.context["request"].user
        user.set_password(self.validated_data["new_password"])
        user.save()
        return user

class PasswordResetOTPRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        try:
            self.user = CustomUser.objects.get(email=value)
        except CustomUser.DoesNotExist:
            raise serializers.ValidationError("User with this email does not exist.")
        return value

    def create(self, validated_data):
        user = self.user
        existing_otp = PasswordResetOTP.objects.filter(user=user).order_by("-created_at").first()

        # ✅ If OTP exists and cannot resend yet, show remaining seconds
        if existing_otp and not existing_otp.can_resend():
            remaining_seconds = int(
                (existing_otp.created_at + timedelta(minutes=1.5) - timezone.now()).total_seconds()
            )
            raise serializers.ValidationError(
                {"message": f"Please wait {remaining_seconds} seconds before requesting a new OTP."}
            )

        otp = f"{random.randint(100000, 999999)}"

        PasswordResetOTP.objects.create(
            user=user,
            otp=otp
        )
        
        send_otp_email_async(str(user.pk), otp)

        return {"message": "OTP sent successfully."}
    
class PasswordResetOTPVerifySerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField(max_length=6)

    def validate(self, data):
        try:
            user = CustomUser.objects.get(email=data["email"])
        except CustomUser.DoesNotExist:
            raise serializers.ValidationError("No user found with this email.")

        try:
            record = PasswordResetOTP.objects.filter(
                user=user,
                otp=data["otp"],
            ).latest("created_at")
        except PasswordResetOTP.DoesNotExist:
            raise serializers.ValidationError("Invalid OTP.")

        if record.is_expired():
            raise serializers.ValidationError("OTP has expired.")
        
        if record.is_verified:
            raise serializers.ValidationError("OTP already verified.")
        
        # Mark OTP as verified
        record.is_verified = True
        record.save()

        return {
        "otp_record": record  # ← Add this!
        }

class PasswordResetConfirmSerializer(serializers.Serializer):
    email = serializers.EmailField()
    new_password = serializers.CharField(write_only=True)

    def validate_email(self, value):
        try:
            self.user = CustomUser.objects.get(email=value)
        except CustomUser.DoesNotExist:
            raise serializers.ValidationError("No user found with this email.")
        return value

    def validate(self, data):
        user = self.user

        record = PasswordResetOTP.objects.filter(
            user=user,
            is_verified=True,
            consumed=False
        ).order_by("-created_at").first()

        if not record:
            raise serializers.ValidationError("OTP not verified yet.")

        if record.is_expired():
            raise serializers.ValidationError("OTP has expired.")

        self.record = record
        return data

    def save(self):
        self.user.set_password(self.validated_data["new_password"])
        self.user.save()
        
        # ✅ Consume the OTP (so it cannot be reused)
        self.record.consumed = True
        self.record.save()
        
class SetPasswordOTPRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        try:
            self.user = CustomUser.objects.get(email=value)
        except CustomUser.DoesNotExist:
            raise serializers.ValidationError("User with this email does not exist.")
        
        if self.user.password not in [None, ""] and self.user.has_usable_password():
            raise serializers.ValidationError("Password already set for this account.")

        
        return value

    def create(self, validated_data):
        user = self.user
        existing_otp = PasswordResetOTP.objects.filter(user=user).order_by("-created_at").first()

        # ✅ If OTP exists and cannot resend yet, show remaining seconds
        if existing_otp and not existing_otp.can_resend():
            remaining_seconds = int(
                (existing_otp.created_at + timedelta(minutes=1.5) - timezone.now()).total_seconds()
            )
            raise serializers.ValidationError(
                {"message": f"Please wait {remaining_seconds} seconds before requesting a new OTP."}
            )

        otp = f"{random.randint(100000, 999999)}"

        PasswordResetOTP.objects.create(
            user=user,
            otp=otp
        )

        send_set_password_otp_email_async(str(user.pk), otp)

        return {"message": "OTP sent successfully."}


class SetPasswordConfirmSerializer(serializers.Serializer):
    email = serializers.EmailField()
    new_password = serializers.CharField(write_only=True)

    def validate_email(self, value):
        try:
            self.user = CustomUser.objects.get(email=value)
        except CustomUser.DoesNotExist:
            raise serializers.ValidationError("No user found with this email.")
        return value

    def validate(self, data):
        user = self.user

        # Ensure user signed up via Google (no usable password yet)
        if self.user.password not in [None, ""] and self.user.has_usable_password():
            raise serializers.ValidationError("Password already set for this account.")

        # Check latest verified and unused OTP
        record = PasswordResetOTP.objects.filter(
            user=user,
            is_verified=True,
            consumed=False
        ).order_by("-created_at").first()

        if not record:
            raise serializers.ValidationError("OTP not verified yet or already used.")

        if record.is_expired():
            raise serializers.ValidationError("OTP has expired.")
        
        self.record = record
        return data

    def save(self):
        self.user.set_password(self.validated_data["new_password"])
        self.user.save()
        # ✅ Mark OTP as consumed (one-time use)
        self.record.consumed = True
        self.record.save()

class RoleEditRequestCreateSerializer(serializers.ModelSerializer):
    requested_role = serializers.SlugRelatedField(
        slug_field='name',
        queryset=Group.objects.exclude(name__in=["ClientAdmin", "SuperAdmin"])
    )

    class Meta:
        model = RoleEditRequest
        fields = ['requested_role', 'reason']

    def validate(self, data):
        user = self.context['request'].user
        requested_role = data.get('requested_role')
        
        #check for existing pending request
        if RoleEditRequest.objects.filter(user=user, status='pending').exists():
            raise serializers.ValidationError("You already have a pending role request.")
        # Check if the user already has this role
        if user.groups.filter(name=requested_role.name).exists():
            raise serializers.ValidationError(f"You already have the '{requested_role.name}' role.")
        
        return data

    def create(self, validated_data):
        return RoleEditRequest.objects.create(
            user=self.context['request'].user,
            status='pending',
            **validated_data
        )

class RoleEditRequestListSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source="user.email", read_only=True)
    requested_role = serializers.CharField(source="requested_role.name", read_only=True)

    class Meta:
        model = RoleEditRequest
        fields = ["uid", "user_email", "requested_role", "reason", "created_at"]
        
class RoleEditRequestReviewSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["approve", "reject"])
    reason = serializers.CharField(required=False, allow_blank=True)
    
class DeleteAccountOTPRequestSerializer(serializers.Serializer):
    def create(self, validated_data):
        user = self.context['request'].user

        # ✅ Check for recent OTP (within resend cooldown)
        latest_otp = PasswordResetOTP.objects.filter(user=user).order_by('-created_at').first()
        if latest_otp and not latest_otp.can_resend():
            remaining_seconds = int((latest_otp.created_at + timedelta(minutes=1.5) - timezone.now()).total_seconds())
            raise serializers.ValidationError(
                {"message": f"Please wait {remaining_seconds} seconds before requesting a new OTP."}
            )

        # ✅ Generate new OTP
        otp = str(random.randint(100000, 999999))

        # ✅ Save OTP record
        PasswordResetOTP.objects.create(user=user, otp=otp)

        # ✅ Send OTP email asynchronously
        send_account_delete_otp_email_async(user.email, user.username or user.email, otp)

        return {"message": "OTP sent to your email."}



class DeleteAccountSerializer(serializers.Serializer):
    method = serializers.ChoiceField(choices=["password", "otp"])
    password = serializers.CharField(write_only=True, required=False)
    otp = serializers.CharField(write_only=True, required=False)

    def validate(self, data):
        user = self.context["request"].user
        method = data.get("method")
        password = data.get("password")
        otp = data.get("otp")

        if method == "password":
            if not password:
                raise serializers.ValidationError({"password": "Password is required for password method."})

            if not user.has_usable_password() or not user.password:
                raise serializers.ValidationError(
                    "Your account does not have a password. Use OTP verification or set a password first."
                )

            if not user.check_password(password):
                raise serializers.ValidationError({"password": "Incorrect password."})

        elif method == "otp":
            if not otp:
                raise serializers.ValidationError({"otp": "OTP is required for OTP method."})

            record = PasswordResetOTP.objects.filter(
                user=user,
                otp=otp,
                consumed=False
            ).order_by("-created_at").first()
            if not record or record.is_expired():
                raise serializers.ValidationError({"otp": "Invalid or expired OTP."})
            record.is_verified = True
            # ✅ Store OTP record for later consumption
            self.record = record

        return data

    def consume_otp(self):
        """Mark OTP as consumed after account deletion"""
        if hasattr(self, "record"):
            self.record.consumed = True
            self.record.save()