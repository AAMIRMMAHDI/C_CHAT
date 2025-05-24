from rest_framework import serializers
from .models import User, Group, Message, File

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'display_name', 'profile_image', 'is_online', 'description']

class FileSerializer(serializers.ModelSerializer):
    class Meta:
        model = File
        fields = ['id', 'file', 'file_type', 'uploaded_at']

class GroupSerializer(serializers.ModelSerializer):
    creator = UserSerializer(read_only=True)
    members = UserSerializer(many=True, read_only=True)
    creator_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), source='creator', write_only=True
    )
    image = serializers.ImageField(allow_null=True, required=False)

    class Meta:
        model = Group
        fields = ['id', 'name', 'description', 'creator', 'creator_id', 'members', 'image', 'created_at']

class MessageSerializer(serializers.ModelSerializer):
    sender = serializers.SerializerMethodField()
    recipient = serializers.SerializerMethodField()
    group = serializers.SerializerMethodField()
    sender_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), source='sender', write_only=True
    )
    recipient_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), source='recipient', write_only=True, required=False, allow_null=True
    )
    group_id = serializers.PrimaryKeyRelatedField(
        queryset=Group.objects.all(), source='group', write_only=True, required=False, allow_null=True
    )
    files = FileSerializer(many=True, read_only=True)
    file_ids = serializers.ListField(
        child=serializers.IntegerField(), write_only=True, required=False, default=[]
    )

    class Meta:
        model = Message
        fields = ['id', 'sender', 'recipient', 'group', 'sender_id', 'recipient_id', 'group_id', 'content', 'timestamp', 'delivered_at', 'read_at', 'files', 'file_ids']

    def get_sender(self, obj):
        return UserSerializer(obj.sender).data

    def get_recipient(self, obj):
        return UserSerializer(obj.recipient).data if obj.recipient else None

    def get_group(self, obj):
        return {'id': obj.group.id, 'name': obj.group.name} if obj.group else None

    def validate(self, data):
        if not data.get('content') and not data.get('file_ids'):
            raise serializers.ValidationError("محتوا یا فایل الزامی است")
        return data