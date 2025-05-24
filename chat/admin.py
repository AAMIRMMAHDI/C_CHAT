from django.contrib import admin
from .models import User, Group, File, Message

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ['username', 'display_name', 'is_online']
    search_fields = ['username', 'display_name']

@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ['name', 'creator', 'created_at']
    search_fields = ['name']

@admin.register(File)
class FileAdmin(admin.ModelAdmin):
    list_display = ['file', 'file_type', 'uploaded_at']

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ['sender', 'recipient', 'group', 'content', 'timestamp']
    search_fields = ['content']