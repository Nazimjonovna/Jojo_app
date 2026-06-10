# Generated for support/ticket professional rework:
#  - CallCenterTicket: language, bot_state, rating, rating_comment, rated_at, resolved_at
#  - new SupportQuickReply model (operator shortcuts / canned responses)

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("parent", "0023_merge_19_22"),
    ]

    operations = [
        migrations.AddField(
            model_name="callcenterticket",
            name="language",
            field=models.CharField(
                blank=True,
                choices=[
                    ("uz_latn", "O‘zbek lotin"),
                    ("uz_cyrl", "Ўзбек кирилл"),
                    ("ru", "Русский"),
                    ("en", "English"),
                ],
                default="",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="callcenterticket",
            name="bot_state",
            field=models.CharField(
                choices=[
                    ("awaiting_language", "Tilni tanlash"),
                    ("chatting", "Suhbatda"),
                    ("awaiting_rating", "Baho kutilmoqda"),
                    ("done", "Yakunlangan"),
                ],
                default="chatting",
                max_length=30,
            ),
        ),
        migrations.AddField(
            model_name="callcenterticket",
            name="rating",
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="callcenterticket",
            name="rating_comment",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="callcenterticket",
            name="rated_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="callcenterticket",
            name="resolved_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.CreateModel(
            name="SupportQuickReply",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "scope",
                    models.CharField(
                        choices=[("global", "Hammaga"), ("personal", "Faqat menga")],
                        default="global",
                        max_length=10,
                    ),
                ),
                ("code", models.CharField(db_index=True, max_length=40)),
                ("title", models.CharField(max_length=120)),
                ("text_uz_latn", models.TextField(blank=True, default="")),
                ("text_uz_cyrl", models.TextField(blank=True, default="")),
                ("text_ru", models.TextField(blank=True, default="")),
                ("text_en", models.TextField(blank=True, default="")),
                ("order", models.PositiveIntegerField(default=0)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "owner",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="support_quick_replies",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Support quick reply",
                "verbose_name_plural": "Support quick replies",
                "ordering": ["order", "title"],
            },
        ),
    ]
