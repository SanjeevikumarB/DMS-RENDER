from rest_framework import serializers
from accounts.models import CustomUser, JoinRequest

class CreateUserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = CustomUser
        fields = ['email', 'username', 'password', 'profile_picture']

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = CustomUser(**validated_data)
        user.set_password(password)
        user.is_active = True  # Directly activate users created by ClientAdmin
        user.save()
        return user

class CreateClientAdminSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = CustomUser
        fields = ['email', 'username', 'password', 'profile_picture']

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = CustomUser(**validated_data)
        user.set_password(password)
        user.is_active = True
        user.is_staff = True  # Allow access to Django admin panel
        user.save()

        # Add to "ClientAdmin" group
        from django.contrib.auth.models import Group
        client_admin_group, _ = Group.objects.get_or_create(name="ClientAdmin")
        user.groups.add(client_admin_group)

        return user

class JoinRequestSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source='user.email')
    username = serializers.CharField(source='user.username')

    class Meta:
        model = JoinRequest
        fields = [
            'uid',
            'email',
            'username',
            'message',
            'status',
            'created_at'
        ]

class JoinRequestReviewSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["approve", "reject"])