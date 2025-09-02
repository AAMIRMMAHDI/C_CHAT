from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import User, Group, Message, File, GroupJoinRequest
from .serializers import UserSerializer, GroupSerializer, MessageSerializer, FileSerializer, GroupJoinRequestSerializer
import os
from django.conf import settings
from django.core.files.storage import default_storage
import django.db.models as models
from django.utils import timezone
from django.core.cache import cache
from PIL import Image
import logging
import random
import threading
import time

logger = logging.getLogger(__name__)

# IN-MEMORY LIST FOR TEMPORARILY STORING MESSAGES
message_cache = []

# FUNCTION TO FLUSH MESSAGES FROM CACHE TO DATABASE
def flush_messages_to_db():
    global message_cache
    while True:
        time.sleep(300)  # WAIT 5 MINUTES
        if message_cache:
            logger.info(f"FLUSHING {len(message_cache)} MESSAGES TO DATABASE")
            try:
                # SAVE MESSAGES TO DATABASE
                for msg_data in message_cache:
                    message = Message.objects.create(
                        sender_id=msg_data['sender_id'],
                        content=msg_data['content'],
                        group_id=msg_data.get('group_id'),
                        recipient_id=msg_data.get('recipient_id'),
                        delivered_at=msg_data['delivered_at']
                    )
                    # ATTACH FILES TO MESSAGE
                    for file_id in msg_data.get('file_ids', []):
                        file_obj = get_object_or_404(File, id=file_id)
                        file_obj.message = message
                        file_obj.save()
                    # IF PRIVATE MESSAGE, SET READ_AT
                    if msg_data.get('recipient_id'):
                        message.read_at = timezone.now()
                        message.save()
                # CLEAR CACHE
                message_cache = []
                logger.info("MESSAGES FLUSHED TO DATABASE AND CACHE CLEARED")
            except Exception as e:
                logger.error(f"ERROR FLUSHING MESSAGES TO DATABASE: {str(e)}")

# REST OF YOUR CODE UNCHANGED
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
                {'status': 'ERROR', 'message': 'USERNAME AND PASSWORD ARE REQUIRED'},
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
                    'status': 'SUCCESS',
                    'user_id': user.id,
                    'username': user.username,
                    'display_name': user.display_name,
                    'profile_image': user.profile_image.url if user.profile_image else None,
                    'description': user.description or ''
                })
            else:
                return Response(
                    {'status': 'ERROR', 'message': 'INCORRECT PASSWORD'},
                    status=status.HTTP_401_UNAUTHORIZED
                )

        user = User(username=username, display_name=display_name or username)
        user.set_password(password)
        user.is_online = True
        user.save()
        request.session['user_id'] = user.id
        return Response({
            'status': 'SUCCESS',
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
                {'status': 'ERROR', 'message': 'USER NOT LOGGED IN'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        user = get_object_or_404(User, id=user_id)
        serializer = UserSerializer(user)
        return Response(serializer.data)

    def patch(self, request):
        user_id = request.session.get('user_id')
        if not user_id:
            return Response(
                {'status': 'ERROR', 'message': 'USER NOT LOGGED IN'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        user = get_object_or_404(User, id=user_id)

        if 'profile_image' in request.FILES:
            if user.profile_image:
                default_storage.delete(user.profile_image.name)
            user.profile_image = request.FILES['profile_image']
            user.save()
            return Response({
                'status': 'SUCCESS',
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
            'status': 'SUCCESS',
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
                {'status': 'ERROR', 'message': 'USER NOT LOGGED IN'},
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
                {'status': 'ERROR', 'message': 'USER NOT LOGGED IN'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        cache_key = f'groups_{user_id}'
        cached_groups = cache.get(cache_key)
        if cached_groups:
            return Response(cached_groups)

        groups = Group.objects.filter(members__id=user_id)
        serializer = GroupSerializer(groups, many=True, context={'request': request})
        cache.set(cache_key, serializer.data, timeout=60*15)
        return Response(serializer.data)

    def post(self, request):
        user_id = request.session.get('user_id')
        if not user_id:
            return Response(
                {'status': 'ERROR', 'message': 'USER NOT LOGGED IN'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        data = request.data
        name = data.get('name')
        description = data.get('description', '')
        password = data.get('password', '')
        image = request.FILES.get('image')
        
        # CONVERT BOOLEAN VALUES PROPERLY
        show_members = data.get('show_members', 'true').lower() == 'true'
        show_info = data.get('show_info', 'true').lower() == 'true'
        allow_join_requests = data.get('allow_join_requests', 'true').lower() == 'true'

        if not name:
            return Response(
                {'status': 'ERROR', 'message': 'GROUP NAME IS REQUIRED'},
                status=status.HTTP_400_BAD_REQUEST
            )

        group = Group(
            name=name, 
            description=description, 
            password=password, 
            creator_id=user_id,
            show_members=show_members,
            show_info=show_info,
            allow_join_requests=allow_join_requests
        )
        if image:
            group.image = image
        group.save()
        group.members.add(user_id)
        group.admins.add(user_id)
        cache.delete(f'groups_{user_id}')
        return Response({'status': 'SUCCESS', 'group_id': group.id})

class GroupDetailView(APIView):
    def get(self, request, pk):
        user_id = request.session.get('user_id')
        if not user_id:
            return Response(
                {'status': 'ERROR', 'message': 'USER NOT LOGGED IN'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        group = get_object_or_404(Group, pk=pk)
        if not group.members.filter(id=user_id).exists() and not group.allow_join_requests:
            return Response(
                {'status': 'ERROR', 'message': 'YOU ARE NOT A MEMBER OF THIS GROUP AND JOIN REQUESTS ARE DISABLED'},
                status=status.HTTP_403_FORBIDDEN
            )
            
        serializer = GroupSerializer(group, context={'request': request})
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
                {'status': 'ERROR', 'message': 'USER NOT LOGGED IN'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        group_id = request.data.get('group_id')
        password = request.data.get('password', '')

        group = get_object_or_404(Group, id=group_id)
        
        if group.members.filter(id=user_id).exists():
            return Response(
                {'status': 'ERROR', 'message': 'YOU ARE ALREADY A MEMBER OF THIS GROUP'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if group.password and not group.check_password(password):
            if not group.allow_join_requests:
                return Response(
                    {'status': 'ERROR', 'message': 'INCORRECT PASSWORD AND JOIN REQUESTS ARE DISABLED'},
                    status=status.HTTP_401_UNAUTHORIZED
                )
            
            # CREATE JOIN REQUEST
            request, created = GroupJoinRequest.objects.get_or_create(
                group=group,
                user_id=user_id,
                defaults={'status': 'PENDING'}
            )
            
            if created:
                return Response({
                    'status': 'SUCCESS', 
                    'message': 'YOUR JOIN REQUEST HAS BEEN SENT AND IS PENDING APPROVAL'
                })
            else:
                return Response({
                    'status': 'ERROR',
                    'message': 'YOU HAVE ALREADY REQUESTED TO JOIN'
                })

        group.members.add(user_id)
        cache.delete(f'groups_{user_id}')
        return Response({'status': 'SUCCESS', 'group_id': group.id})

class GroupAdminsView(APIView):
    def post(self, request, pk):
        user_id = request.session.get('user_id')
        if not user_id:
            return Response(
                {'status': 'ERROR', 'message': 'USER NOT LOGGED IN'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        group = get_object_or_404(Group, pk=pk)
        if group.creator_id != user_id:
            return Response(
                {'status': 'ERROR', 'message': 'ONLY THE GROUP CREATOR CAN MANAGE ADMINS'},
                status=status.HTTP_403_FORBIDDEN
            )

        member_id = request.data.get('member_id')
        action = request.data.get('action')  # 'add' or 'remove'
        
        if not member_id:
            return Response(
                {'status': 'ERROR', 'message': 'USER ID IS REQUIRED'},
                status=status.HTTP_400_BAD_REQUEST
            )

        member = get_object_or_404(User, pk=member_id)
        
        if not group.members.filter(id=member_id).exists():
            return Response(
                {'status': 'ERROR', 'message': 'USER IS NOT A GROUP MEMBER'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if action == 'add':
            if group.admins.filter(id=member_id).exists():
                return Response(
                    {'status': 'ERROR', 'message': 'USER IS ALREADY AN ADMIN'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            group.admins.add(member_id)
            return Response({
                'status': 'SUCCESS',
                'message': 'USER SUCCESSFULLY ADDED TO ADMINS'
            })
        elif action == 'remove':
            if not group.admins.filter(id=member_id).exists():
                return Response(
                    {'status': 'ERROR', 'message': 'USER IS NOT AN ADMIN'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            group.admins.remove(member_id)
            return Response({
                'status': 'SUCCESS',
                'message': 'USER SUCCESSFULLY REMOVED FROM ADMINS'
            })
        else:
            return Response(
                {'status': 'ERROR', 'message': 'INVALID ACTION'},
                status=status.HTTP_400_BAD_REQUEST
            )

class GroupSettingsView(APIView):
    def patch(self, request, pk):
        user_id = request.session.get('user_id')
        if not user_id:
            return Response(
                {'status': 'ERROR', 'message': 'USER NOT LOGGED IN'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        group = get_object_or_404(Group, pk=pk)
        if not group.is_admin(User.objects.get(id=user_id)):
            return Response(
                {'status': 'ERROR', 'message': 'ONLY ADMINS CAN CHANGE GROUP SETTINGS'},
                status=status.HTTP_403_FORBIDDEN
            )

        data = request.data
        if 'show_members' in data:
            group.show_members = str(data['show_members']).lower() == 'true'
        if 'show_info' in data:
            group.show_info = str(data['show_info']).lower() == 'true'
        if 'allow_join_requests' in data:
            group.allow_join_requests = str(data['allow_join_requests']).lower() == 'true'
        
        group.save()
        cache.delete(f'groups_{user_id}')
        return Response({
            'status': 'SUCCESS',
            'message': 'GROUP SETTINGS SUCCESSFULLY UPDATED'
        })

class GroupJoinRequestView(APIView):
    def get(self, request, pk):
        user_id = request.session.get('user_id')
        if not user_id:
            return Response(
                {'status': 'ERROR', 'message': 'USER NOT LOGGED IN'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        group = get_object_or_404(Group, pk=pk)
        if not group.is_admin(User.objects.get(id=user_id)):
            return Response(
                {'status': 'ERROR', 'message': 'ONLY ADMINS CAN VIEW JOIN REQUESTS'},
                status=status.HTTP_403_FORBIDDEN
            )

        requests = GroupJoinRequest.objects.filter(group=group, status='PENDING')
        serializer = GroupJoinRequestSerializer(requests, many=True)
        return Response({'requests': serializer.data})

    def post(self, request, pk):
        user_id = request.session.get('user_id')
        if not user_id:
            return Response(
                {'status': 'ERROR', 'message': 'USER NOT LOGGED IN'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        group = get_object_or_404(Group, pk=pk)
        if not group.is_admin(User.objects.get(id=user_id)):
            return Response(
                {'status': 'ERROR', 'message': 'ONLY ADMINS CAN APPROVE JOIN REQUESTS'},
                status=status.HTTP_403_FORBIDDEN
            )

        request_id = request.data.get('request_id')
        action = request.data.get('action')  # 'approve' or 'reject'

        join_request = get_object_or_404(GroupJoinRequest, id=request_id, group=group)
        
        if action == 'approve':
            group.members.add(join_request.user)
            join_request.status = 'APPROVED'
            join_request.save()
            return Response({
                'status': 'SUCCESS',
                'message': 'JOIN REQUEST APPROVED'
            })
        elif action == 'reject':
            join_request.status = 'REJECTED'
            join_request.save()
            return Response({
                'status': 'SUCCESS',
                'message': 'JOIN REQUEST REJECTED'
            })
        else:
            return Response(
                {'status': 'ERROR', 'message': 'INVALID ACTION'},
                status=status.HTTP_400_BAD_REQUEST
            )

class MessageView(APIView):
    def get(self, request):
        user_id = request.session.get('user_id')
        if not user_id:
            return Response(
                {'status': 'ERROR', 'message': 'USER NOT LOGGED IN'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        last_message_id = request.GET.get('last_message_id', '0')
        group_id = request.GET.get('group_id')
        recipient_id = request.GET.get('recipient_id')

        try:
            last_message_id = int(last_message_id)
        except ValueError:
            return Response(
                {'status': 'ERROR', 'message': 'INVALID MESSAGE ID'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # DATABASE MESSAGES FIRST
        messages = Message.objects.filter(id__gt=last_message_id).select_related('sender', 'recipient', 'group').prefetch_related('files').order_by('timestamp')

        if group_id:
            try:
                group_id = int(group_id)
                if not Group.objects.filter(id=group_id, members__id=user_id).exists():
                    return Response(
                        {'status': 'ERROR', 'message': 'YOU ARE NOT A MEMBER OF THIS GROUP'},
                        status=status.HTTP_403_FORBIDDEN
                    )
                messages = messages.filter(group_id=group_id)
            except ValueError:
                return Response(
                    {'status': 'ERROR', 'message': 'INVALID GROUP ID'},
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
                    {'status': 'ERROR', 'message': 'INVALID RECIPIENT ID'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            messages = messages.filter(
                models.Q(sender_id=user_id) |
                models.Q(recipient_id=user_id) |
                models.Q(group__members__id=user_id)
            )

        # ADD CACHED MESSAGES
        cached_messages = []
        for msg_data in message_cache:
            if group_id and msg_data.get('group_id') == int(group_id):
                cached_messages.append(msg_data)
            elif recipient_id and (
                (msg_data.get('sender_id') == user_id and msg_data.get('recipient_id') == int(recipient_id)) or
                (msg_data.get('sender_id') == int(recipient_id) and msg_data.get('recipient_id') == user_id)
            ):
                cached_messages.append(msg_data)
            elif not group_id and not recipient_id:
                if msg_data.get('sender_id') == user_id or msg_data.get('recipient_id') == user_id:
                    cached_messages.append(msg_data)
                elif msg_data.get('group_id') and Group.objects.filter(id=msg_data['group_id'], members__id=user_id).exists():
                    cached_messages.append(msg_data)

        # SERIALIZE DATABASE MESSAGES
        serializer = MessageSerializer(messages, many=True)
        serialized_data = serializer.data

        # ADD CACHED MESSAGES TO RESPONSE
        for msg_data in cached_messages:
            serialized_data.append({
                'id': None,  # CACHED MESSAGES DON'T YET HAVE A DATABASE ID
                'sender': {'id': msg_data['sender_id']},
                'content': msg_data['content'],
                'group': {'id': msg_data.get('group_id')} if msg_data.get('group_id') else None,
                'recipient': {'id': msg_data.get('recipient_id')} if msg_data.get('recipient_id') else None,
                'timestamp': msg_data['delivered_at'].isoformat(),
                'delivered_at': msg_data['delivered_at'].isoformat(),
                'read_at': msg_data.get('read_at').isoformat() if msg_data.get('read_at') else None,
                'files': [{'id': fid} for fid in msg_data.get('file_ids', [])]
            })

        return Response(serialized_data)

    def post(self, request):
        user_id = request.session.get('user_id')
        if not user_id:
            return Response(
                {'status': 'ERROR', 'message': 'USER NOT LOGGED IN'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        data = request.data
        content = data.get('content', '').strip()
        group_id = data.get('group_id')
        recipient_id = data.get('recipient_id')
        file_ids = data.get('file_ids', [])

        if not content and not file_ids:
            return Response(
                {'status': 'ERROR', 'message': 'CONTENT OR FILE IS REQUIRED'},
                status=status.HTTP_400_BAD_REQUEST
            )

        message_data = {
            'sender_id': user_id,
            'content': content,
            'delivered_at': timezone.now(),
            'file_ids': file_ids
        }
        if group_id:
            try:
                group_id = int(group_id)
                if not Group.objects.filter(id=group_id, members__id=user_id).exists():
                    return Response(
                        {'status': 'ERROR', 'message': 'YOU ARE NOT A MEMBER OF THIS GROUP'},
                        status=status.HTTP_403_FORBIDDEN
                    )
                message_data['group_id'] = group_id
            except ValueError:
                return Response(
                    {'status': 'ERROR', 'message': 'INVALID GROUP ID'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        if recipient_id:
            try:
                recipient_id = int(recipient_id)
                if not User.objects.filter(id=recipient_id).exists():
                    return Response(
                        {'status': 'ERROR', 'message': 'RECIPIENT DOES NOT EXIST'},
                        status=status.HTTP_404_NOT_FOUND
                    )
                message_data['recipient_id'] = recipient_id
                message_data['read_at'] = timezone.now()
            except ValueError:
                return Response(
                    {'status': 'ERROR', 'message': 'INVALID RECIPIENT ID'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        # ADD MESSAGE TO CACHE
        message_cache.append(message_data)
        
        # RESPONSE IN SAME FORMAT AS DATABASE MESSAGES
        response_data = {
            'id': None,  # NOT YET STORED IN DATABASE
            'sender': {'id': user_id},
            'content': content,
            'group': {'id': group_id} if group_id else None,
            'recipient': {'id': recipient_id} if recipient_id else None,
            'timestamp': message_data['delivered_at'].isoformat(),
            'delivered_at': message_data['delivered_at'].isoformat(),
            'read_at': message_data.get('read_at').isoformat() if message_data.get('read_at') else None,
            'files': [{'id': fid} for fid in file_ids]
        }

        return Response({'status': 'SUCCESS', 'message_id': None, 'message': response_data})

class MessageDetailView(APIView):
    def patch(self, request, pk):
        user_id = request.session.get('user_id')
        if not user_id:
            return Response(
                {'status': 'ERROR', 'message': 'USER NOT LOGGED IN'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        message = get_object_or_404(Message, pk=pk)
        if message.sender_id != user_id:
            return Response(
                {'status': 'ERROR', 'message': 'ONLY THE MESSAGE OWNER CAN EDIT IT'},
                status=status.HTTP_403_FORBIDDEN
            )

        data = request.data
        content = data.get('content', '').strip()
        if not content:
            return Response(
                {'status': 'ERROR', 'message': 'MESSAGE CANNOT BE EMPTY'},
                status=status.HTTP_400_BAD_REQUEST
            )

        message.content = content
        message.save()
        serializer = MessageSerializer(message)
        return Response({'status': 'SUCCESS', 'message': serializer.data})

    def delete(self, request, pk):
        user_id = request.session.get('user_id')
        if not user_id:
            return Response(
                {'status': 'ERROR', 'message': 'USER NOT LOGGED IN'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        message = get_object_or_404(Message, pk=pk)
        if message.sender_id != user_id:
            return Response(
                {'status': 'ERROR', 'message': 'ONLY THE MESSAGE OWNER CAN DELETE IT'},
                status=status.HTTP_403_FORBIDDEN
            )

        message.delete()
        return Response({'status': 'SUCCESS'})

class UploadView(APIView):
    def post(self, request):
        user_id = request.session.get('user_id')
        if not user_id:
            return Response(
                {'status': 'ERROR', 'message': 'USER NOT LOGGED IN'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        files = request.FILES.getlist('files')
        if not files:
            return Response(
                {'status': 'ERROR', 'message': 'NO FILE SELECTED'},
                status=status.HTTP_400_BAD_REQUEST
            )

        max_size = 20 * 1024 * 1024 * 1024
        file_ids = []
        for file in files:
            if file.size > max_size:
                return Response(
                    {'status': 'ERROR', 'message': f'FILE {file.name} EXCEEDS 20GB'},
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
                logger.error(f"ERROR SAVING FILE {file.name}: {str(e)}")
                return Response(
                    {'status': 'ERROR', 'message': f'ERROR SAVING FILE {file.name}: {str(e)}'},
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
                    logger.error(f"ERROR COMPRESSING IMAGE {file.name}: {str(e)}")
                    if default_storage.exists(saved_path):
                        default_storage.delete(saved_path)
                    return Response(
                        {'status': 'ERROR', 'message': f'ERROR COMPRESSING IMAGE {file.name}: {str(e)}'},
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
                logger.error(f"ERROR CREATING FILE OBJECT FOR {saved_path}: {str(e)}")
                if default_storage.exists(saved_path):
                    default_storage.delete(saved_path)
                return Response(
                    {'status': 'ERROR', 'message': f'ERROR REGISTERING FILE {file.name}: {str(e)}'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

        return Response({'status': 'SUCCESS', 'file_ids': file_ids})

class MessageSeenView(APIView):
    def post(self, request):
        user_id = request.session.get('user_id')
        if not user_id:
            return Response(
                {'status': 'ERROR', 'message': 'USER NOT LOGGED IN'},
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
                return Response({'status': 'SUCCESS'})
            except ValueError:
                return Response(
                    {'status': 'ERROR', 'message': 'INVALID RECIPIENT ID'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        elif group_id:
            try:
                group_id = int(group_id)
                if not Group.objects.filter(id=group_id, members__id=user_id).exists():
                    return Response(
                        {'status': 'ERROR', 'message': 'YOU ARE NOT A MEMBER OF THIS GROUP'},
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
                return Response({'status': 'SUCCESS'})
            except ValueError:
                return Response(
                    {'status': 'ERROR', 'message': 'INVALID GROUP ID'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        return Response(
            {'status': 'ERROR', 'message': 'RECIPIENT OR GROUP ID IS REQUIRED'},
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
        return Response({'status': 'SUCCESS'})

threading.Thread(target=flush_messages_to_db, daemon=True).start()