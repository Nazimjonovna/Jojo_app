from django.core.management.base import BaseCommand
from django.utils import timezone

from parent.models import User


class Command(BaseCommand):
    help = "Delete non-active children whose pending_delete_at has expired."

    def handle(self, *args, **options):
        expired_children = User.objects.filter(
            role=User.ROLE_CHILD,
            child_status=User.CHILD_STATUS_NON_ACTIVE,
            pending_delete_at__isnull=False,
            pending_delete_at__lte=timezone.now(),
        )

        count = expired_children.count()
        expired_children.delete()

        self.stdout.write(
            self.style.SUCCESS(f"Deleted {count} expired non-active children.")
        )