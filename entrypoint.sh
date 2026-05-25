#!/bin/sh

set -e

echo "Waiting for PostgreSQL..."

while ! nc -z "$DB_HOST" "$DB_PORT"; do
  sleep 1
done

echo "PostgreSQL is ready."

echo "Waiting for Redis..."

while ! nc -z "$REDIS_HOST" "$REDIS_PORT"; do
  sleep 1
done

echo "Redis is ready."

echo "Running migrations..."
python manage.py migrate --noinput

echo "Collecting static files..."
python manage.py collectstatic --noinput

echo "Creating default admin users if not exists..."

python manage.py shell -c "
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
import os

User = get_user_model()

CONTENT_ADMIN_GROUP = 'content_admin'
SUPPORT_ADMIN_GROUP = 'support_admin'

content_group, _ = Group.objects.get_or_create(name=CONTENT_ADMIN_GROUP)
support_group, _ = Group.objects.get_or_create(name=SUPPORT_ADMIN_GROUP)


def create_or_update_user(phone, username, email, password, is_superuser=False, groups=None):
    if not phone:
        return None

    user = User.objects.filter(phone=phone).first()

    if not user:
        user = User.objects.create_user(
            phone=phone,
            username=username or phone,
            email=email or '',
            password=password,
            role='parent',
            language='uz_latn',
            is_staff=True,
            is_superuser=is_superuser,
            is_active=True,
        )
        print(f'Created admin user: {phone}')
    else:
        user.username = username or user.username or phone
        user.email = email or user.email
        user.role = user.role or 'parent'
        user.language = user.language or 'uz_latn'
        user.is_staff = True
        user.is_active = True

        if is_superuser:
            user.is_superuser = True

        if password:
            user.set_password(password)

        user.save()
        print(f'Updated admin user: {phone}')

    if groups:
        for group in groups:
            user.groups.add(group)

    return user


# 1. Superuser: all access
create_or_update_user(
    phone=os.environ.get('DJANGO_SUPERUSER_PHONE') or '+998000000000',
    username=os.environ.get('DJANGO_SUPERUSER_USERNAME') or 'SuperAdmin',
    email=os.environ.get('DJANGO_SUPERUSER_EMAIL') or 'superadmin@example.com',
    password=os.environ.get('DJANGO_SUPERUSER_PASSWORD') or 'jojoapp2026',
    is_superuser=True,
    groups=[],
)

# 2. Main admin: content_admin + support_admin
create_or_update_user(
    phone=os.environ.get('DJANGO_MAIN_ADMIN_PHONE') or '+998901236547',
    username=os.environ.get('DJANGO_MAIN_ADMIN_USERNAME') or 'MainAdmin',
    email=os.environ.get('DJANGO_MAIN_ADMIN_EMAIL') or 'mainadmin@example.com',
    password=os.environ.get('DJANGO_MAIN_ADMIN_PASSWORD') or 'jojoapp2026',
    is_superuser=False,
    groups=[content_group, support_group],
)

# 3. Support admin: support_admin only
create_or_update_user(
    phone=os.environ.get('DJANGO_SUPPORT_ADMIN_PHONE') or '+998911236547',
    username=os.environ.get('DJANGO_SUPPORT_ADMIN_USERNAME') or 'SupportAdmin',
    email=os.environ.get('DJANGO_SUPPORT_ADMIN_EMAIL') or 'supportadmin@example.com',
    password=os.environ.get('DJANGO_SUPPORT_ADMIN_PASSWORD') or 'jojoapp2026',
    is_superuser=False,
    groups=[support_group],
)

print('Admin users check finished.')
"

echo "Starting server..."

exec "$@"