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

echo "Making migrations..."
python manage.py makemigrations --noinput

echo "Running migrations..."
python manage.py migrate --noinput

echo "Collecting static files..."
python manage.py collectstatic --noinput

echo "Creating superuser if not exists..."

python manage.py shell -c "from django.contrib.auth import get_user_model; import os; User=get_user_model(); phone=os.environ.get('DJANGO_SUPERUSER_PHONE') or '+998000000000'; username=os.environ.get('DJANGO_SUPERUSER_USERNAME') or 'Admin'; email=os.environ.get('DJANGO_SUPERUSER_EMAIL') or 'admin@example.com'; password=os.environ.get('DJANGO_SUPERUSER_PASSWORD') or 'adminuser1'; exists=User.objects.filter(phone=phone).exists(); print('Superuser already exists.' if exists else 'Creating superuser...'); None if exists else User.objects.create_superuser(phone=phone, password=password, username=username, email=email, role='parent', language='uz_latn'); print('Superuser check finished.')"

echo "Starting server..."

exec "$@"