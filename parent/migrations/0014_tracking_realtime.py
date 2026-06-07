# Real-time tracking — extended ChildLocation/ChildLastLocation +
# ChildFrequentPlace + ChildDestinationPrediction.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("parent", "0013_parent_store_and_blog_duration"),
    ]

    operations = [
        # ChildLocation new fields
        migrations.AddField(
            model_name="childlocation",
            name="altitude",
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="childlocation",
            name="altitude_accuracy",
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="childlocation",
            name="is_charging",
            field=models.BooleanField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="childlocation",
            name="speed_accuracy",
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="childlocation",
            name="signal_strength",
            field=models.IntegerField(
                blank=True,
                help_text="0..4 ASU yoki -100..-50 dBm asosida 0..4 ko‘rsatkich.",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="childlocation",
            name="network_type",
            field=models.CharField(
                blank=True,
                default="",
                help_text="wifi/cellular/none",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="childlocation",
            name="provider",
            field=models.CharField(
                blank=True,
                choices=[
                    ("gps", "GPS"),
                    ("fused", "Fused"),
                    ("network", "Network"),
                    ("passive", "Passive"),
                ],
                default="",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="childlocation",
            name="is_mock_location",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="childlocation",
            name="activity_type",
            field=models.CharField(
                blank=True,
                default="",
                help_text="still/walking/running/in_vehicle/on_bicycle/unknown",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="childlocation",
            name="captured_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="childlocation",
            name="speed",
            field=models.FloatField(blank=True, help_text="m/s", null=True),
        ),
        migrations.AddIndex(
            model_name="childlocation",
            index=models.Index(
                fields=["child", "-created_at"],
                name="child_loc_recent_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="childlocation",
            index=models.Index(
                fields=["child", "created_at"],
                name="child_loc_range_idx",
            ),
        ),
        # ChildLastLocation new fields
        migrations.AddField(
            model_name="childlastlocation",
            name="altitude",
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="childlastlocation",
            name="is_charging",
            field=models.BooleanField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="childlastlocation",
            name="signal_strength",
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="childlastlocation",
            name="network_type",
            field=models.CharField(blank=True, default="", max_length=20),
        ),
        migrations.AddField(
            model_name="childlastlocation",
            name="activity_type",
            field=models.CharField(blank=True, default="", max_length=20),
        ),
        migrations.AddField(
            model_name="childlastlocation",
            name="provider",
            field=models.CharField(blank=True, default="", max_length=20),
        ),
        migrations.AddField(
            model_name="childlastlocation",
            name="captured_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        # ChildFrequentPlace
        migrations.CreateModel(
            name="ChildFrequentPlace",
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
                ("latitude", models.DecimalField(decimal_places=7, max_digits=10)),
                ("longitude", models.DecimalField(decimal_places=7, max_digits=10)),
                ("radius_meters", models.PositiveIntegerField(default=120)),
                ("visit_count", models.PositiveIntegerField(default=0)),
                ("total_dwell_seconds", models.PositiveIntegerField(default=0)),
                ("first_seen_at", models.DateTimeField(auto_now_add=True)),
                ("last_seen_at", models.DateTimeField(auto_now=True)),
                (
                    "label",
                    models.CharField(
                        blank=True,
                        default="",
                        help_text="Avtomatik label (masalan, 'Doim boriladigan joy').",
                        max_length=120,
                    ),
                ),
                ("is_recommendation_dismissed", models.BooleanField(default=False)),
                (
                    "child",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="frequent_places",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "parent",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="children_frequent_places",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "saved_location",
                    models.ForeignKey(
                        blank=True,
                        help_text="Agar ota-ona uni saved location'ga aylantirgan bo‘lsa.",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="frequent_places",
                        to="parent.savedlocation",
                    ),
                ),
            ],
            options={
                "ordering": ["-visit_count", "-last_seen_at"],
            },
        ),
        migrations.AddIndex(
            model_name="childfrequentplace",
            index=models.Index(
                fields=["child", "-visit_count"],
                name="child_fp_visit_idx",
            ),
        ),
        # ChildDestinationPrediction
        migrations.CreateModel(
            name="ChildDestinationPrediction",
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
                    "event_type",
                    models.CharField(
                        choices=[
                            ("heading_to", "Heading to"),
                            ("arriving_soon", "Arriving soon"),
                        ],
                        default="heading_to",
                        max_length=20,
                    ),
                ),
                ("distance_meters", models.FloatField()),
                ("speed_kmh", models.FloatField(blank=True, null=True)),
                ("eta_seconds", models.FloatField(blank=True, null=True)),
                ("title", models.CharField(blank=True, default="", max_length=120)),
                ("body", models.CharField(blank=True, default="", max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "child",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="destination_predictions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "parent",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="children_destination_predictions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "saved_location",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="destination_predictions",
                        to="parent.savedlocation",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="childdestinationprediction",
            index=models.Index(
                fields=["child", "saved_location", "-created_at"],
                name="child_pred_recent_idx",
            ),
        ),
    ]
