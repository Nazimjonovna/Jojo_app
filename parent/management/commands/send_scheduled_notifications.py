"""Reja bo'yicha bildirishnomalarni yuborish.

Foydalanish (har daqiqada cron orqali):
    docker exec jojo_backend python manage.py send_scheduled_notifications

Server'dagi `crontab` da:
    * * * * * docker exec jojo_backend python manage.py send_scheduled_notifications >/dev/null 2>&1
"""

from django.core.management.base import BaseCommand

from parent.notification_scheduler import tick


class Command(BaseCommand):
    help = "Reja qilingan NotificationRule'larni hozirgi vaqtga qarab yuboradi."

    def handle(self, *args, **options):
        fired = tick()
        self.stdout.write(self.style.SUCCESS(f"fired: {fired}"))
