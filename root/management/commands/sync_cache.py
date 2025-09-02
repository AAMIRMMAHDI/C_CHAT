from django.core.management.base import BaseCommand
from django.core.cache import cache
from root.models import User, Group, Message, File
from django.utils import timezone

class Command(BaseCommand):
    help = 'Sync cache data to database'

    def handle(self, *args, **options):
        # گرفتن لیست کلیدهای کش از کلید 'cache_keys'
        cache_keys = cache.get('cache_keys', set())

        # سینک داده‌های کاربران
        for key in cache_keys:
            if key.startswith('user_'):
                data = cache.get(key)
                if data:
                    try:
                        user_id = data['user_id']
                        user = User.objects.get(id=user_id)
                        user.username = data['username']
                        user.display_name = data['display_name']
                        user.description = data.get('description', '')
                        user.save()
                        self.stdout.write(self.style.SUCCESS(f'Synced user {user_id}'))
                        cache.delete(key)
                        cache_keys.discard(key)  # حذف کلید از لیست
                    except User.DoesNotExist:
                        self.stdout.write(self.style.WARNING(f'User {user_id} not found'))

            # سینک داده‌های گروه‌ها
            elif key.startswith('groups_'):
                data = cache.get(key)
                if data:
                    user_id = key.split('_')[-1]
                    Group.objects.filter(members__id=user_id).update()  # به‌روزرسانی گروه‌ها
                    self.stdout.write(self.style.SUCCESS(f'Synced groups for user {user_id}'))
                    cache.delete(key)
                    cache_keys.discard(key)

            # سینک داده‌های پیام‌ها
            elif key.startswith('messages_'):
                data = cache.get(key)
                if data:
                    self.stdout.write(self.style.SUCCESS(f'Synced messages for {key}'))
                    cache.delete(key)
                    cache_keys.discard(key)

            # سینک داده‌های فایل‌ها
            elif key.startswith('file_'):
                data = cache.get(key)
                if data:
                    try:
                        file_obj = File.objects.get(id=data['id'])
                        file_obj.file_type = data['file_type']
                        file_obj.save()
                        self.stdout.write(self.style.SUCCESS(f'Synced file {data["id"]}'))
                        cache.delete(key)
                        cache_keys.discard(key)
                    except File.DoesNotExist:
                        self.stdout.write(self.style.WARNING(f'File {data["id"]} not found'))

        # به‌روزرسانی لیست کلیدهای کش
        cache.set('cache_keys', cache_keys, timeout=None)  # بدون انقضا
        self.stdout.write(self.style.SUCCESS('Cache sync completed'))