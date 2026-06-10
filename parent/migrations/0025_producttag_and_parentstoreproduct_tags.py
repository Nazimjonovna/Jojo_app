# ProductTag (multi-lang) + M2M from ParentStoreProduct.tags

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("parent", "0024_support_ticket_lang_rating_quickreply"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProductTag",
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
                ("name", models.CharField(max_length=80, unique=True)),
                ("name_ru", models.CharField(blank=True, default="", max_length=80)),
                ("name_en", models.CharField(blank=True, default="", max_length=80)),
                ("slug", models.SlugField(max_length=90, unique=True)),
                ("is_active", models.BooleanField(default=True)),
                ("usage_count", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "verbose_name": "Mahsulot tegi",
                "verbose_name_plural": "Mahsulot teglari",
                "ordering": ["-usage_count", "name"],
            },
        ),
        migrations.AddIndex(
            model_name="producttag",
            index=models.Index(fields=["slug"], name="product_tag_slug_idx"),
        ),
        migrations.AddField(
            model_name="parentstoreproduct",
            name="tags",
            field=models.ManyToManyField(
                blank=True,
                help_text=(
                    "Mahsulot teglari. Adminda yangi tag yozilsa "
                    "uch tilga tarjima qilinadi."
                ),
                related_name="products",
                to="parent.producttag",
            ),
        ),
    ]
