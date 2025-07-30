from django.contrib import admin
from .models import User, Group, File, Message, GroupJoinRequest

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ['username', 'display_name', 'is_online', 'last_login']
    search_fields = ['username', 'display_name']
    list_filter = ['is_online']

@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ['name', 'creator', 'show_members', 'show_info', 'allow_join_requests', 'created_at']
    search_fields = ['name']
    list_filter = ['show_members', 'show_info', 'allow_join_requests']
    filter_horizontal = ['members', 'admins']

@admin.register(File)
class FileAdmin(admin.ModelAdmin):
    list_display = ['file', 'file_type', 'uploaded_at']
    list_filter = ['file_type']

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ['sender', 'recipient', 'group', 'content', 'timestamp', 'delivered_at', 'read_at']
    search_fields = ['content']
    list_filter = ['timestamp', 'delivered_at', 'read_at']

@admin.register(GroupJoinRequest)
class GroupJoinRequestAdmin(admin.ModelAdmin):
    list_display = ['group', 'user', 'status', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['group__name', 'user__username']