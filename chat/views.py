from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import User, Group, Message, File
from .serializers import UserSerializer, GroupSerializer, MessageSerializer, FileSerializer
import os
from django.conf import settings
from django.core.files.storage import default_storage
import django.db.models as models
from django.utils import timezone
from django.core.cache import cache
from PIL import Image
import logging
import random

logger = logging.getLogger(__name__)

def index(request):
    return render(request, 'index.html')

class UserView(APIView):
    def post(self, request):
        data = request.data
        username = data.get('username')
        display_name = data.get('display_name')
        password = data.get('password')

        if not username or not password:
            return Response(
                {'status': 'error', 'message': 'نام کاربری و رمز عبور الزامی است'},
                status=status.HTTP_400_BAD_REQUEST
            )

        user = User.objects.filter(username=username).first()
        if user:
            if user.check_password(password):
                request.session['user_id'] = user.id
                user.is_online = True
                user.last_login = timezone.now()
                user.save()
                return Response({
                    'status': 'success',
                    'user_id': user.id,
                    'username': user.username,
                    'display_name': user.display_name,
                    'profile_image': user.profile_image.url if user.profile_image else None,
                    'description': user.description or ''
                })
            else:
                return Response(
                    {'status': 'error', 'message': 'رمز عبور اشتباه است'},
                    status=status.HTTP_401_UNAUTHORIZED
                )

        user = User(username=username, display_name=display_name or username)
        user.set_password(password)
        user.is_online = True
        user.save()
        request.session['user_id'] = user.id
        return Response({
            'status': 'success',
            'user_id': user.id,
            'username': user.username,
            'display_name': user.display_name,
            'profile_image': user.profile_image.url if user.profile_image else None,
            'description': user.description or ''
        })

    def get(self, request):
        query = request.GET.get('search', '')
        users = User.objects.filter(username__icontains=query).exclude(id=request.session.get('user_id'))
        serializer = UserSerializer(users, many=True)
        return Response({'users': serializer.data})

class UserDetailView(APIView):
    def get(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        serializer = UserSerializer(user)
        return Response(serializer.data)

class UserCurrentView(APIView):
    def get(self, request):
        user_id = request.session.get('user_id')
        if not user_id:
            return Response(
                {'status': 'error', 'message': 'کاربر وارد نشده است'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        user = get_object_or_404(User, id=user_id)
        serializer = UserSerializer(user)
        return Response(serializer.data)

    def patch(self, request):
        user_id = request.session.get('user_id')
        if not user_id:
            return Response(
                {'status': 'error', 'message': 'کاربر وارد نشده است'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        user = get_object_or_404(User, id=user_id)

        if 'profile_image' in request.FILES:
            if user.profile_image:
                default_storage.delete(user.profile_image.name)
            user.profile_image = request.FILES['profile_image']
            user.save()
            return Response({
                'status': 'success',
                'profile_image': user.profile_image.url if user.profile_image else None
            })

        data = request.data
        username = data.get('username')
        display_name = data.get('display_name')
        password = data.get('password')
        description = data.get('description', '')

        if username:
            user.username = username
        if display_name:
            user.display_name = display_name
        if password:
            user.set_password(password)
        if description:
            user.description = description
        user.save()
        return Response({
            'status': 'success',
            'username': user.username,
            'display_name': user.display_name,
            'profile_image': user.profile_image.url if user.profile_image else None,
            'description': user.description
        })

class UserChattedView(APIView):
    def get(self, request):
        user_id = request.session.get('user_id')
        if not user_id:
            return Response(
                {'status': 'error', 'message': 'کاربر وارد نشده است'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        cache_key = f'chatted_users_{user_id}'
        cached_users = cache.get(cache_key)
        if cached_users:
            return Response({'users': cached_users})

        sent_messages = Message.objects.filter(sender_id=user_id).values('recipient_id').distinct()
        received_messages = Message.objects.filter(recipient_id=user_id).values('sender_id').distinct()

        user_ids = set()
        for msg in sent_messages:
            if msg['recipient_id']:
                user_ids.add(msg['recipient_id'])
        for msg in received_messages:
            if msg['sender_id']:
                user_ids.add(msg['sender_id'])

        users = User.objects.filter(id__in=user_ids)
        serializer = UserSerializer(users, many=True)
        cache.set(cache_key, serializer.data, timeout=60*15)
        return Response({'users': serializer.data})

class GroupView(APIView):
    def get(self, request):
        user_id = request.session.get('user_id')
        if not user_id:
            return Response(
                {'status': 'error', 'message': 'کاربر وارد نشده است'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        cache_key = f'groups_{user_id}'
        cached_groups = cache.get(cache_key)
        if cached_groups:
            return Response(cached_groups)

        groups = Group.objects.filter(members__id=user_id)
        serializer = GroupSerializer(groups, many=True)
        cache.set(cache_key, serializer.data, timeout=60*15)
        return Response(serializer.data)

    def post(self, request):
        user_id = request.session.get('user_id')
        if not user_id:
            return Response(
                {'status': 'error', 'message': 'کاربر وارد نشده است'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        data = request.data
        name = data.get('name')
        description = data.get('description', '')
        password = data.get('password', '')
        image = request.FILES.get('image')

        if not name:
            return Response(
                {'status': 'error', 'message': 'نام گروه الزامی است'},
                status=status.HTTP_400_BAD_REQUEST
            )

        group = Group(name=name, description=description, password=password, creator_id=user_id)
        if image:
            group.image = image
        group.save()
        group.members.add(user_id)
        cache.delete(f'groups_{user_id}')
        return Response({'status': 'success', 'group_id': group.id})

class GroupDetailView(APIView):
    def get(self, request, pk):
        user_id = request.session.get('user_id')
        if not user_id:
            return Response(
                {'status': 'error', 'message': 'کاربر وارد نشده است'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        group = get_object_or_404(Group, pk=pk, members__id=user_id)
        serializer = GroupSerializer(group)
        return Response(serializer.data)

class GroupSearchView(APIView):
    def get(self, request):
        query = request.GET.get('search', '')
        groups = Group.objects.filter(name__icontains=query)
        serializer = GroupSerializer(groups, many=True)
        return Response({'groups': serializer.data})

class GroupJoinView(APIView):
    def post(self, request):
        user_id = request.session.get('user_id')
        if not user_id:
            return Response(
                {'status': 'error', 'message': 'کاربر وارد نشده است'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        group_id = request.data.get('group_id')
        password = request.data.get('password', '')

        group = get_object_or_404(Group, id=group_id)
        if group.password and not group.check_password(password):
            return Response(
                {'status': 'error', 'message': 'رمز عبور اشتباه است'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        if group.members.filter(id=user_id).exists():
            return Response(
                {'status': 'error', 'message': 'شما قبلاً عضو این گروه هستید'},
                status=status.HTTP_400_BAD_REQUEST
            )

        group.members.add(user_id)
        cache.delete(f'groups_{user_id}')
        return Response({'status': 'success', 'group_id': group.id})

class MessageView(APIView):
    def get(self, request):
        user_id = request.session.get('user_id')
        if not user_id:
            return Response(
                {'status': 'error', 'message': 'کاربر وارد نشده است'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        last_message_id = request.GET.get('last_message_id', '0')
        group_id = request.GET.get('group_id')
        recipient_id = request.GET.get('recipient_id')

        try:
            last_message_id = int(last_message_id)
        except ValueError:
            return Response(
                {'status': 'error', 'message': 'شناسه پیام نامعتبر است'},
                status=status.HTTP_400_BAD_REQUEST
            )

        messages = Message.objects.filter(id__gt=last_message_id).select_related('sender', 'recipient', 'group').prefetch_related('files').order_by('timestamp')

        if group_id:
            try:
                group_id = int(group_id)
                if not Group.objects.filter(id=group_id, members__id=user_id).exists():
                    return Response(
                        {'status': 'error', 'message': 'شما عضو این گروه نیستید'},
                        status=status.HTTP_403_FORBIDDEN
                    )
                messages = messages.filter(group_id=group_id)
            except ValueError:
                return Response(
                    {'status': 'error', 'message': 'شناسه گروه نامعتبر است'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        elif recipient_id:
            try:
                recipient_id = int(recipient_id)
                messages = messages.filter(
                    (models.Q(sender_id=user_id) & models.Q(recipient_id=recipient_id)) |
                    (models.Q(sender_id=recipient_id) & models.Q(recipient_id=user_id))
                )
            except ValueError:
                return Response(
                    {'status': 'error', 'message': 'شناسه گیرنده نامعتبر است'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            messages = messages.filter(
                models.Q(sender_id=user_id) |
                models.Q(recipient_id=user_id) |
                models.Q(group__members__id=user_id)
            )

        serializer = MessageSerializer(messages, many=True)
        return Response(serializer.data)

    def post(self, request):
        user_id = request.session.get('user_id')
        if not user_id:
            return Response(
                {'status': 'error', 'message': 'کاربر وارد نشده است'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        data = request.data
        content = data.get('content', '').strip()
        group_id = data.get('group_id')
        recipient_id = data.get('recipient_id')
        file_ids = data.get('file_ids', [])

        if not content and not file_ids:
            return Response(
                {'status': 'error', 'message': 'محتوا یا فایل الزامی است'},
                status=status.HTTP_400_BAD_REQUEST
            )

        message_data = {'sender_id': user_id, 'content': content}
        if group_id:
            try:
                group_id = int(group_id)
                if not Group.objects.filter(id=group_id, members__id=user_id).exists():
                    return Response(
                        {'status': 'error', 'message': 'شما عضو این گروه نیستید'},
                        status=status.HTTP_403_FORBIDDEN
                    )
                message_data['group_id'] = group_id
            except ValueError:
                return Response(
                    {'status': 'error', 'message': 'شناسه گروه نامعتبر است'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        if recipient_id:
            try:
                recipient_id = int(recipient_id)
                if not User.objects.filter(id=recipient_id).exists():
                    return Response(
                        {'status': 'error', 'message': 'گیرنده وجود ندارد'},
                        status=status.HTTP_404_NOT_FOUND
                    )
                message_data['recipient_id'] = recipient_id
            except ValueError:
                return Response(
                    {'status': 'error', 'message': 'شناسه گیرنده نامعتبر است'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        message = Message.objects.create(**message_data, delivered_at=timezone.now())
        for file_id in file_ids:
            file_obj = get_object_or_404(File, id=file_id)
            file_obj.message = message
            file_obj.save()
        if recipient_id:
            message.read_at = timezone.now()
            message.save()

        serializer = MessageSerializer(message)
        return Response({'status': 'success', 'message_id': serializer.data['id'], 'message': serializer.data})

class MessageDetailView(APIView):
    def patch(self, request, pk):
        user_id = request.session.get('user_id')
        if not user_id:
            return Response(
                {'status': 'error', 'message': 'کاربر وارد نشده است'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        message = get_object_or_404(Message, pk=pk)
        if message.sender_id != user_id:
            return Response(
                {'status': 'error', 'message': 'فقط صاحب پیام می‌تواند آن را ویرایش کند'},
                status=status.HTTP_403_FORBIDDEN
            )

        data = request.data
        content = data.get('content', '').strip()
        if not content:
            return Response(
                {'status': 'error', 'message': 'پیام نمی‌تواند خالی باشد'},
                status=status.HTTP_400_BAD_REQUEST
            )

        message.content = content
        message.save()
        serializer = MessageSerializer(message)
        return Response({'status': 'success', 'message': serializer.data})

    def delete(self, request, pk):
        user_id = request.session.get('user_id')
        if not user_id:
            return Response(
                {'status': 'error', 'message': 'کاربر وارد نشده است'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        message = get_object_or_404(Message, pk=pk)
        if message.sender_id != user_id:
            return Response(
                {'status': 'error', 'message': 'فقط صاحب پیام می‌تواند آن را حذف کند'},
                status=status.HTTP_403_FORBIDDEN
            )

        message.delete()
        return Response({'status': 'success'})

class UploadView(APIView):
    def post(self, request):
        user_id = request.session.get('user_id')
        if not user_id:
            return Response(
                {'status': 'error', 'message': 'کاربر وارد نشده است'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        files = request.FILES.getlist('files')
        if not files:
            return Response(
                {'status': 'error', 'message': 'هیچ فایلی انتخاب نشده است'},
                status=status.HTTP_400_BAD_REQUEST
            )

        max_size = 20 * 1024 * 1024 * 1024
        file_ids = []
        for file in files:
            if file.size > max_size:
                return Response(
                    {'status': 'error', 'message': f'فایل {file.name} بیش از 20 گیگابایت است'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            file_extension = os.path.splitext(file.name)[1]
            unique_filename = f"{timezone.now().strftime('%Y%m%d_%H%M%S')}_{random.randint(1000, 9999)}{file_extension}"
            file_path = os.path.join('uploads', unique_filename)

            try:
                saved_path = default_storage.save(file_path, file)
                file_url = default_storage.url(saved_path)
                full_path = os.path.join(settings.MEDIA_ROOT, saved_path)
            except Exception as e:
                logger.error(f"Error saving file {file.name}: {str(e)}")
                return Response(
                    {'status': 'error', 'message': f'خطا در ذخیره فایل {file.name}: {str(e)}'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            file_type = 'other'
            if file.content_type.startswith('image'):
                file_type = 'image'
                try:
                    with Image.open(full_path) as img:
                        img = img.convert('RGB')
                        output_path = full_path.replace(unique_filename, f"compressed_{unique_filename}")
                        img.save(output_path, quality=60, optimize=True)
                        saved_path = saved_path.replace(unique_filename, f"compressed_{unique_filename}")
                        if default_storage.exists(full_path):
                            default_storage.delete(full_path)
                except Exception as e:
                    logger.error(f"Error compressing image {file.name}: {str(e)}")
                    if default_storage.exists(saved_path):
                        default_storage.delete(saved_path)
                    return Response(
                        {'status': 'error', 'message': f'خطا در فشرده‌سازی تصویر {file.name}: {str(e)}'},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )
            elif file.content_type.startswith('video'):
                file_type = 'video'
            elif file.content_type.startswith('audio'):
                file_type = 'audio'

            try:
                file_obj = File.objects.create(file=saved_path, file_type=file_type)
                file_ids.append(file_obj.id)
            except Exception as e:
                logger.error(f"Error creating File object for {saved_path}: {str(e)}")
                if default_storage.exists(saved_path):
                    default_storage.delete(saved_path)
                return Response(
                    {'status': 'error', 'message': f'خطا در ثبت فایل {file.name}: {str(e)}'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

        return Response({'status': 'success', 'file_ids': file_ids})

class MessageSeenView(APIView):
    def post(self, request):
        user_id = request.session.get('user_id')
        if not user_id:
            return Response(
                {'status': 'error', 'message': 'کاربر وارد نشده است'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        recipient_id = request.data.get('recipient_id')
        group_id = request.data.get('group_id')

        if recipient_id:
            try:
                recipient_id = int(recipient_id)
                messages = Message.objects.filter(
                    recipient_id=user_id, sender_id=recipient_id, read_at__isnull=True
                )
                for message in messages:
                    if not message.delivered_at:
                        message.delivered_at = timezone.now()
                    message.read_at = timezone.now()
                    message.save()
                return Response({'status': 'success'})
            except ValueError:
                return Response(
                    {'status': 'error', 'message': 'شناسه گیرنده نامعتبر است'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        elif group_id:
            try:
                group_id = int(group_id)
                if not Group.objects.filter(id=group_id, members__id=user_id).exists():
                    return Response(
                        {'status': 'error', 'message': 'شما عضو این گروه نیستید'},
                        status=status.HTTP_403_FORBIDDEN
                    )
                messages = Message.objects.filter(
                    group_id=group_id, read_at__isnull=True
                ).exclude(sender_id=user_id)
                for message in messages:
                    if not message.delivered_at:
                        message.delivered_at = timezone.now()
                    message.read_at = timezone.now()
                    message.save()
                return Response({'status': 'success'})
            except ValueError:
                return Response(
                    {'status': 'error', 'message': 'شناسه گروه نامعتبر است'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        return Response(
            {'status': 'error', 'message': 'شناسه گیرنده یا گروه الزامی است'},
            status=status.HTTP_400_BAD_REQUEST
        )

class LogoutView(APIView):
    def post(self, request):
        user_id = request.session.get('user_id')
        if user_id:
            user = get_object_or_404(User, id=user_id)
            user.is_online = False
            user.save()
            request.session.flush()
        return Response({'status': 'success'})