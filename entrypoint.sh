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

python manage.py shell << END
from django.contrib.auth import get_user_model

User = get_user_model()

username = "${DJANGO_SUPERUSER_USERNAME}"
email = "${DJANGO_SUPERUSER_EMAIL}"
password = "${DJANGO_SUPERUSER_PASSWORD}"

if not User.objects.filter(username=username).exists():
    user = User.objects.create_superuser(
        username=username,
        email=email,
        password=password
    )

    if hasattr(user, "role"):
        user.role = "parent"

    if hasattr(user, "phone"):
        user.phone = "+998000000000"

    if hasattr(user, "language"):
        user.language = "uz_latn"

    user.save()

    print("Superuser created.")
else:
    print("Superuser already exists.")
END

echo "Starting server..."

exec "$@"