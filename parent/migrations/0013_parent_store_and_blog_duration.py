# Parent Store models + BlogPost.duration_label field.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("parent", "0012_blogcategory_blogpost_blogpostlike_blogpostsave"),
    ]

    operations = [
        migrations.AddField(
            model_name="blogpost",
            name="duration_label",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Video davomiyligi, masalan '11:38'. Faqat video uchun.",
                max_length=16,
            ),
        ),
        migrations.CreateModel(
            name="ParentStoreCategory",
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
                ("name", models.CharField(max_length=150)),
                ("slug", models.SlugField(max_length=160, unique=True)),
                (
                    "product_type",
                    models.CharField(
                        choices=[
                            ("stem", "STEM"),
                            ("book", "Kitob"),
                            ("other", "Boshqa"),
                        ],
                        default="other",
                        max_length=20,
                    ),
                ),
                (
                    "icon",
                    models.ImageField(
                        blank=True,
                        null=True,
                        upload_to="parent_store/categories/",
                    ),
                ),
                ("is_active", models.BooleanField(default=True)),
                ("order", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "verbose_name": "Parent Store Category",
                "verbose_name_plural": "Parent Store Categories",
                "ordering": ["order", "id"],
            },
        ),
        migrations.CreateModel(
            name="ParentStoreProduct",
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
                ("name", models.CharField(max_length=255)),
                ("slug", models.SlugField(max_length=255, unique=True)),
                (
                    "category_label",
                    models.CharField(
                        blank=True,
                        default="",
                        help_text="Kartochkada chiqadigan kichik label, masalan 'STEM O‘YINCHOQ'",
                        max_length=120,
                    ),
                ),
                (
                    "age_label",
                    models.CharField(
                        blank=True,
                        default="",
                        help_text="Masalan '6+ yosh'",
                        max_length=40,
                    ),
                ),
                ("price", models.PositiveIntegerField(help_text="so‘m")),
                ("old_price", models.PositiveIntegerField(blank=True, null=True)),
                (
                    "badge",
                    models.CharField(
                        choices=[
                            ("none", "Belgi yo‘q"),
                            ("top", "TOP"),
                            ("yangi", "YANGI"),
                        ],
                        default="none",
                        max_length=10,
                    ),
                ),
                (
                    "features",
                    models.JSONField(
                        blank=True,
                        default=list,
                        help_text="String list, masalan [\"Bluetooth\", \"50+ daraja\"]",
                    ),
                ),
                (
                    "short_description",
                    models.CharField(blank=True, default="", max_length=500),
                ),
                ("description", models.TextField(blank=True, default="")),
                (
                    "thumbnail",
                    models.ImageField(
                        blank=True,
                        null=True,
                        upload_to="parent_store/products/thumbnails/",
                    ),
                ),
                ("video_url", models.URLField(blank=True, default="")),
                (
                    "video_file",
                    models.FileField(
                        blank=True,
                        null=True,
                        upload_to="parent_store/products/videos/",
                    ),
                ),
                ("deal_ends_at", models.DateTimeField(blank=True, null=True)),
                ("is_featured", models.BooleanField(default=False)),
                ("is_active", models.BooleanField(default=True)),
                ("order", models.PositiveIntegerField(default=0)),
                (
                    "placeholder_label",
                    models.CharField(
                        blank=True,
                        default="",
                        help_text="Surat yuklanmaganda ko‘rsatiladigan label (offline placeholder).",
                        max_length=40,
                    ),
                ),
                (
                    "placeholder_tint",
                    models.CharField(
                        blank=True,
                        default="",
                        help_text="Placeholder fon rangi, hex (#RRGGBB).",
                        max_length=9,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "category",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="products",
                        to="parent.parentstorecategory",
                    ),
                ),
            ],
            options={
                "verbose_name": "Parent Store Product",
                "verbose_name_plural": "Parent Store Products",
                "ordering": ["order", "-created_at"],
            },
        ),
        migrations.CreateModel(
            name="ParentStoreProductImage",
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
                    "image",
                    models.ImageField(upload_to="parent_store/products/gallery/"),
                ),
                ("order", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "product",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="images",
                        to="parent.parentstoreproduct",
                    ),
                ),
            ],
            options={
                "ordering": ["order", "id"],
            },
        ),
        migrations.CreateModel(
            name="ParentStorePromoBanner",
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
                ("kicker", models.CharField(max_length=80)),
                ("title", models.CharField(max_length=160)),
                (
                    "subtitle",
                    models.CharField(blank=True, default="", max_length=255),
                ),
                (
                    "theme",
                    models.CharField(
                        choices=[
                            ("cream", "Cream"),
                            ("sky", "Sky"),
                            ("green", "Green"),
                        ],
                        default="cream",
                        max_length=10,
                    ),
                ),
                (
                    "image",
                    models.ImageField(
                        blank=True,
                        null=True,
                        upload_to="parent_store/banners/",
                    ),
                ),
                (
                    "link_category_type",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("stem", "STEM"),
                            ("book", "Kitob"),
                            ("other", "Boshqa"),
                        ],
                        default="",
                        help_text="Mahsulot biriktirilmagan bo‘lsa, banner bosilganda filtrlanadigan tip.",
                        max_length=20,
                    ),
                ),
                ("gift_icon", models.BooleanField(default=False)),
                (
                    "placeholder_label",
                    models.CharField(blank=True, default="", max_length=40),
                ),
                (
                    "placeholder_tint",
                    models.CharField(blank=True, default="", max_length=9),
                ),
                ("is_active", models.BooleanField(default=True)),
                ("order", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "link_product",
                    models.ForeignKey(
                        blank=True,
                        help_text="Banner bosilganda ochiladigan mahsulot.",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to="parent.parentstoreproduct",
                    ),
                ),
            ],
            options={
                "verbose_name": "Parent Store Promo Banner",
                "verbose_name_plural": "Parent Store Promo Banners",
                "ordering": ["order", "id"],
            },
        ),
        migrations.CreateModel(
            name="ParentStoreSavedProduct",
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
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "product",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="saved_by_users",
                        to="parent.parentstoreproduct",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="parent_store_saved",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
                "unique_together": {("user", "product")},
            },
        ),
        migrations.CreateModel(
            name="ParentStoreOrder",
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
                    "code",
                    models.CharField(
                        help_text="Foydalanuvchiga ko‘rsatiladigan buyurtma raqami, masalan JOJ-1043",
                        max_length=24,
                        unique=True,
                    ),
                ),
                ("quantity", models.PositiveIntegerField(default=1)),
                (
                    "unit_price",
                    models.PositiveIntegerField(
                        help_text="Buyurtma yaratilgan paytdagi mahsulot narxi (so‘m).",
                    ),
                ),
                ("total_price", models.PositiveIntegerField()),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("sent", "Yuborildi"),
                            ("review", "Ko‘rib chiqilmoqda"),
                            ("confirmed", "Tasdiqlandi"),
                            ("shipping", "Yetkazilmoqda"),
                            ("delivered", "Yetkazildi"),
                            ("cancelled", "Bekor qilindi"),
                        ],
                        default="sent",
                        max_length=16,
                    ),
                ),
                ("contact_phone", models.CharField(blank=True, default="", max_length=20)),
                ("contact_name", models.CharField(blank=True, default="", max_length=150)),
                ("address", models.TextField(blank=True, default="")),
                ("note", models.TextField(blank=True, default="")),
                ("sent_at", models.DateTimeField(blank=True, null=True)),
                ("review_at", models.DateTimeField(blank=True, null=True)),
                ("confirmed_at", models.DateTimeField(blank=True, null=True)),
                ("shipping_at", models.DateTimeField(blank=True, null=True)),
                ("delivered_at", models.DateTimeField(blank=True, null=True)),
                ("cancelled_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "product",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="orders",
                        to="parent.parentstoreproduct",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="parent_store_orders",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Parent Store Order",
                "verbose_name_plural": "Parent Store Orders",
                "ordering": ["-created_at"],
            },
        ),
    ]
