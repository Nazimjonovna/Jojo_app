# Parent notification inbox — saqlanadigan tarix uchun.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("parent", "0014_tracking_realtime"),
    ]

    operations = [
        migrations.CreateModel(
            name="ParentNotification",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "category",
                    models.CharField(
                        choices=[
                            ("zone_in", "Zone in"),
                            ("zone_out", "Zone out"),
                            ("zone_transition", "Zone transition"),
                            ("destination", "Destination"),
                            ("battery", "Battery"),
                            ("offline", "Offline"),
                            ("login", "Login"),
                            ("order", "Order"),
                            ("shipping", "Shipping"),
                            ("deal", "Deal"),
                            ("screen", "Screen time"),
                            ("premium", "Premium"),
                            ("tip", "Tip"),
                            ("route", "Route"),
                            ("place_recommendation", "Place recommendation"),
                            ("system", "System"),
                        ],
                        default="system",
                        max_length=32,
                    ),
                ),
                ("title", models.CharField(max_length=150)),
                ("body", models.CharField(blank=True, default="", max_length=500)),
                (
                    "data",
                    models.JSONField(
                        blank=True,
                        default=dict,
                        help_text="Marshrutlash uchun route/screen va eventga oid context.",
                    ),
                ),
                ("is_read", models.BooleanField(default=False)),
                ("read_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "child",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="related_parent_notifications",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "parent",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="parent_notifications",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="parentnotification",
            index=models.Index(
                fields=["parent", "is_read", "-created_at"],
                name="parent_notif_inbox_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="parentnotification",
            index=models.Index(
                fields=["parent", "-created_at"],
                name="parent_notif_recent_idx",
            ),
        ),
    ]
