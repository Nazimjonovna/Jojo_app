# KidsVideoCategory + KidsVideo — Play tab uchun YouTube-asosli kontent.
# Multi-language sarlavha/tavsif, bolaning yoshiga qarab recommend qilinadi.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("parent", "0025_producttag_and_parentstoreproduct_tags"),
    ]

    operations = [
        migrations.CreateModel(
            name="KidsVideoCategory",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=150)),
                ("name_ru", models.CharField(blank=True, default="", max_length=150)),
                ("name_en", models.CharField(blank=True, default="", max_length=150)),
                (
                    "icon",
                    models.ImageField(
                        blank=True,
                        null=True,
                        upload_to="kids_videos/categories/",
                    ),
                ),
                ("is_active", models.BooleanField(default=True)),
                ("order", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "verbose_name": "Kids Video Category",
                "verbose_name_plural": "Kids Video Categories",
                "ordering": ["order", "id"],
            },
        ),
        migrations.CreateModel(
            name="KidsVideo",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("title", models.CharField(max_length=200)),
                ("title_ru", models.CharField(blank=True, default="", max_length=200)),
                ("title_en", models.CharField(blank=True, default="", max_length=200)),
                ("description", models.TextField(blank=True, default="")),
                ("description_ru", models.TextField(blank=True, default="")),
                ("description_en", models.TextField(blank=True, default="")),
                (
                    "youtube_url",
                    models.URLField(
                        help_text=(
                            "Toʻliq YouTube havola, masalan "
                            "https://www.youtube.com/watch?v=XXXX"
                        )
                    ),
                ),
                (
                    "thumbnail",
                    models.ImageField(
                        blank=True,
                        help_text=(
                            "Ixtiyoriy. Boʻsh boʻlsa YouTube avto-thumbnail "
                            "ishlatiladi."
                        ),
                        null=True,
                        upload_to="kids_videos/thumbnails/",
                    ),
                ),
                (
                    "duration_label",
                    models.CharField(
                        blank=True,
                        default="",
                        help_text="Davomiyligi, masalan '30 Min' yoki '5:42'.",
                        max_length=16,
                    ),
                ),
                ("age_min", models.PositiveSmallIntegerField(default=3)),
                ("age_max", models.PositiveSmallIntegerField(default=12)),
                ("views_count", models.PositiveIntegerField(default=0)),
                ("is_active", models.BooleanField(default=True)),
                ("is_featured", models.BooleanField(default=False)),
                ("order", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "category",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="videos",
                        to="parent.kidsvideocategory",
                    ),
                ),
            ],
            options={
                "verbose_name": "Kids Video",
                "verbose_name_plural": "Kids Videos",
                "ordering": ["order", "-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="kidsvideo",
            index=models.Index(
                fields=["age_min", "age_max"], name="kidsvideo_age_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="kidsvideo",
            index=models.Index(
                fields=["is_active", "is_featured"], name="kidsvideo_flags_idx"
            ),
        ),
    ]
