# SmsSendLog — har bir SMS yuborish urinishi tarixi.
# Admin retrospektiv "filan raqamga SMS yetib bordimi?" deb so'rasa shu DB
# javob beradi (SMSFLY xato kodi + reason bilan).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("parent", "0028_callcentercomment_attachment"),
    ]

    operations = [
        migrations.CreateModel(
            name="SmsSendLog",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("phone", models.CharField(db_index=True, max_length=20)),
                ("phone_normalized", models.CharField(db_index=True, default="", max_length=20)),
                (
                    "kind",
                    models.CharField(
                        choices=[
                            ("otp", "OTP"),
                            ("broadcast", "Broadcast"),
                            ("rule", "Notif rule"),
                            ("test", "Test"),
                            ("other", "Other"),
                        ],
                        db_index=True,
                        default="other",
                        max_length=20,
                    ),
                ),
                ("message", models.TextField(blank=True, default="")),
                ("success", models.BooleanField(db_index=True, default=False)),
                ("result_code", models.IntegerField(default=-1)),
                ("reason", models.CharField(blank=True, default="", max_length=120)),
                ("retry_count", models.PositiveSmallIntegerField(default=0)),
                ("related_user_id", models.PositiveIntegerField(blank=True, db_index=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
            ],
            options={
                "verbose_name": "SMS send log",
                "verbose_name_plural": "SMS send logs",
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(
                        fields=["kind", "success", "-created_at"],
                        name="parent_smss_kind_8f1cab_idx",
                    ),
                    models.Index(
                        fields=["phone_normalized", "-created_at"],
                        name="parent_smss_phone_n_d4ef6c_idx",
                    ),
                ],
            },
        ),
    ]
