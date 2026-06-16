# Multi-language uz_cyrl (Kirill o‘zbek) maydonlari — barcha matnli
# resurslarga `_uz_cyrl` qo‘shamiz. Mavjud _ru / _en parallel saqlanadi.
# Tarkib avtomatik to'ldirilmaydi — admin paneldan kiritiladi yoki
# transliteratsiya orqali (parent.translation.latin_to_cyrillic).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("parent", "0026_kids_video_content"),
    ]

    operations = [
        # BlogCategory
        migrations.AddField(
            model_name="blogcategory",
            name="name_uz_cyrl",
            field=models.CharField(blank=True, default="", max_length=150),
        ),
        # BlogPost
        migrations.AddField(
            model_name="blogpost",
            name="title_uz_cyrl",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="blogpost",
            name="short_description_uz_cyrl",
            field=models.CharField(blank=True, default="", max_length=500),
        ),
        migrations.AddField(
            model_name="blogpost",
            name="content_uz_cyrl",
            field=models.TextField(blank=True, default=""),
        ),
        # ParentStoreCategory
        migrations.AddField(
            model_name="parentstorecategory",
            name="name_uz_cyrl",
            field=models.CharField(blank=True, default="", max_length=150),
        ),
        # ProductTag
        migrations.AddField(
            model_name="producttag",
            name="name_uz_cyrl",
            field=models.CharField(blank=True, default="", max_length=80),
        ),
        # ParentStoreProduct
        migrations.AddField(
            model_name="parentstoreproduct",
            name="name_uz_cyrl",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="parentstoreproduct",
            name="short_description_uz_cyrl",
            field=models.CharField(blank=True, default="", max_length=500),
        ),
        migrations.AddField(
            model_name="parentstoreproduct",
            name="description_uz_cyrl",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="parentstoreproduct",
            name="category_label_uz_cyrl",
            field=models.CharField(blank=True, default="", max_length=120),
        ),
        # ParentStorePromoBanner
        migrations.AddField(
            model_name="parentstorepromobanner",
            name="kicker_uz_cyrl",
            field=models.CharField(blank=True, default="", max_length=80),
        ),
        migrations.AddField(
            model_name="parentstorepromobanner",
            name="title_uz_cyrl",
            field=models.CharField(blank=True, default="", max_length=160),
        ),
        migrations.AddField(
            model_name="parentstorepromobanner",
            name="subtitle_uz_cyrl",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        # ParentNotification
        migrations.AddField(
            model_name="parentnotification",
            name="title_uz_cyrl",
            field=models.CharField(blank=True, default="", max_length=150),
        ),
        migrations.AddField(
            model_name="parentnotification",
            name="body_uz_cyrl",
            field=models.CharField(blank=True, default="", max_length=500),
        ),
        # NotificationRule
        migrations.AddField(
            model_name="notificationrule",
            name="title_uz_cyrl",
            field=models.CharField(blank=True, default="", max_length=200),
        ),
        migrations.AddField(
            model_name="notificationrule",
            name="body_uz_cyrl",
            field=models.TextField(blank=True, default=""),
        ),
        # GameCategory + GameItem (Kids)
        migrations.AddField(
            model_name="gamecategory",
            name="name_uz_cyrl",
            field=models.CharField(blank=True, default="", max_length=150),
        ),
        migrations.AddField(
            model_name="gameitem",
            name="title_uz_cyrl",
            field=models.CharField(blank=True, default="", max_length=150),
        ),
        migrations.AddField(
            model_name="gameitem",
            name="description_uz_cyrl",
            field=models.TextField(blank=True, default=""),
        ),
        # KidsVideoCategory + KidsVideo
        migrations.AddField(
            model_name="kidsvideocategory",
            name="name_uz_cyrl",
            field=models.CharField(blank=True, default="", max_length=150),
        ),
        migrations.AddField(
            model_name="kidsvideo",
            name="title_uz_cyrl",
            field=models.CharField(blank=True, default="", max_length=200),
        ),
        migrations.AddField(
            model_name="kidsvideo",
            name="description_uz_cyrl",
            field=models.TextField(blank=True, default=""),
        ),
    ]
