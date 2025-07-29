# files/serializers.py
from rest_framework import serializers
from sharing.models import FileAccessControl

class SingleFileUploadData(serializers.Serializer):
    file = serializers.FileField()
    relative_path = serializers.CharField()

class MultiFileUploadSerializer(serializers.Serializer):
    files = SingleFileUploadData(many=True)

class CreateFolderSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    parent_uid = serializers.UUIDField(required=False, allow_null=True)

class AccessInfoSerializer(serializers.ModelSerializer):
    shared_by = serializers.EmailField(source="granted_by.email", default=None)
    inherited_from = serializers.SerializerMethodField()

    class Meta:
        model = FileAccessControl
        fields = ("your_level", "shared_by", "inherited", "inherited_from")

    def get_your_level(self, obj):
        return obj.access_level

    def get_inherited_from(self, obj):
        if obj.inherited and obj.inherited_from:
            return {
                "uid": str(obj.inherited_from.uid),
                "name": obj.inherited_from.name
            }
        return None

    your_level = serializers.SerializerMethodField()

class SharedUserSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source="user.email")
    granted_by = serializers.EmailField(source="granted_by.email", default=None)

    class Meta:
        model = FileAccessControl
        fields = ("email", "access_level", "granted_by", "inherited")
