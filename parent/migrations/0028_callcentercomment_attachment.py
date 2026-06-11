# CallCenterComment-ga rasm/hujjat ilova qilish uchun maydonlar.
# Botdan kelgan rasmlar va admin tomondan yuborilgan fayllar shu yerda
# saqlanadi.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("parent", "0027_uz_cyrl_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="callcentercomment",
            name="attachment",
            field=models.FileField(
                blank=True,
                null=True,
                upload_to="support/attachments/%Y/%m/",
            ),
        ),
        migrations.AddField(
            model_name="callcentercomment",
            name="attachment_kind",
            field=models.CharField(
                blank=True,
                choices=[
                    ("", "Yo'q"),
                    ("photo", "Rasm"),
                    ("document", "Hujjat"),
                ],
                default="",
                max_length=12,
            ),
        ),
        migrations.AddField(
            model_name="callcentercomment",
            name="attachment_name",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
    ]
