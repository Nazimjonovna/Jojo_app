# BulkSmsCampaign + SmsContactGroup + SmsContact + SmsSendLog.campaign FK

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("parent", "0029_sms_send_log"),
    ]

    operations = [
        # 1) Bulk choice ni SmsSendLog kind ga qo'shamiz (state-only;
        #    DB ga ta'sir qilmaydi, faqat choices ro'yxati o'zgaradi).
        migrations.AlterField(
            model_name="smssendlog",
            name="kind",
            field=models.CharField(
                choices=[
                    ("otp", "OTP"),
                    ("broadcast", "Broadcast"),
                    ("bulk", "Bulk"),
                    ("rule", "Notif rule"),
                    ("test", "Test"),
                    ("other", "Other"),
                ],
                db_index=True,
                default="other",
                max_length=20,
            ),
        ),
        # 2) Yangi modellar
        migrations.CreateModel(
            name="SmsContactGroup",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120)),
                ("description", models.CharField(blank=True, default="", max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "owner",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="sms_contact_groups",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "SMS contact group",
                "verbose_name_plural": "SMS contact groups",
                "ordering": ["-updated_at"],
            },
        ),
        migrations.CreateModel(
            name="SmsContact",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("phone", models.CharField(max_length=20)),
                ("phone_normalized", models.CharField(db_index=True, default="", max_length=20)),
                ("name", models.CharField(blank=True, default="", max_length=120)),
                ("notes", models.CharField(blank=True, default="", max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "group",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="contacts",
                        to="parent.smscontactgroup",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
                "constraints": [
                    models.UniqueConstraint(fields=("group", "phone_normalized"), name="uniq_group_phone"),
                ],
            },
        ),
        migrations.CreateModel(
            name="BulkSmsCampaign",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(blank=True, default="", max_length=160)),
                ("message", models.TextField()),
                ("message_ru", models.TextField(blank=True, default="")),
                ("message_en", models.TextField(blank=True, default="")),
                ("message_uz_cyrl", models.TextField(blank=True, default="")),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("queued", "Navbatda"),
                            ("sending", "Yuborilmoqda"),
                            ("done", "Yakunlangan"),
                        ],
                        db_index=True,
                        default="queued",
                        max_length=16,
                    ),
                ),
                (
                    "source",
                    models.CharField(
                        choices=[
                            ("manual", "Qo'lda kiritildi"),
                            ("group", "Guruhdan"),
                            ("csv", "CSV/XLSX dan"),
                            ("mixed", "Aralash"),
                        ],
                        default="manual",
                        max_length=16,
                    ),
                ),
                ("total", models.PositiveIntegerField(default=0)),
                ("sent_count", models.PositiveIntegerField(default=0)),
                ("failed_count", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="bulk_sms_campaigns",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "group",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="campaigns",
                        to="parent.smscontactgroup",
                    ),
                ),
            ],
            options={
                "verbose_name": "Bulk SMS campaign",
                "verbose_name_plural": "Bulk SMS campaigns",
                "ordering": ["-created_at"],
            },
        ),
        # 3) SmsSendLog ga campaign FK
        migrations.AddField(
            model_name="smssendlog",
            name="campaign",
            field=models.ForeignKey(
                blank=True,
                db_index=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="logs",
                to="parent.bulksmscampaign",
            ),
        ),
    ]
