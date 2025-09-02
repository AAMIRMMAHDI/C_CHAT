from rest_framework import serializers
from .models import User, Group, Message, File, GroupJoinRequest

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
    admins = UserSerializer(many=True, read_only=True)
    creator_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), source='creator', write_only=True
    )
    image = serializers.ImageField(allow_null=True, required=False)
    is_admin = serializers.SerializerMethodField()

    class Meta:
        model = Group
        fields = ['id', 'name', 'description', 'creator', 'creator_id', 'members', 
                 'admins', 'image', 'created_at', 'show_members', 'show_info', 
                 'allow_join_requests', 'is_admin']

    def get_is_admin(self, obj):
        request = self.context.get('request')
        if request and hasattr(request, 'session'):
            user_id = request.session.get('user_id')
            if user_id:
                return obj.is_admin(User.objects.get(id=user_id))
        return False

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
        fields = ['id', 'sender', 'recipient', 'group', 'sender_id', 'recipient_id', 
                 'group_id', 'content', 'timestamp', 'delivered_at', 'read_at', 
                 'files', 'file_ids']

    def get_sender(self, obj):
        return UserSerializer(obj.sender).data

    def get_recipient(self, obj):
        return UserSerializer(obj.recipient).data if obj.recipient else None

    def get_group(self, obj):
        if obj.group:
            return {
                'id': obj.group.id,
                'name': obj.group.name,
                'image': obj.group.image.url if obj.group.image else None
            }
        return None

    def validate(self, data):
        if not data.get('content') and not data.get('file_ids'):
            raise serializers.ValidationError("Content or file is required")
        return data

class GroupJoinRequestSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    group = GroupSerializer(read_only=True)
    user_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), source='user', write_only=True
    )
    group_id = serializers.PrimaryKeyRelatedField(
        queryset=Group.objects.all(), source='group', write_only=True
    )

    class Meta:
        model = GroupJoinRequest
        fields = ['id', 'group', 'user', 'group_id', 'user_id', 'created_at', 'status']