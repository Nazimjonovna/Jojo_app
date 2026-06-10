"""Admin panel uchun maxsus write/read serializerlar.

Frontend yuborayotgan field nomlari va backend model nomlari mos kelmaydi.
Bu fayl ikkalasini bog'laydi: slug auto-generatsiya, alias name mapping va
URL string'larni image fieldlarga to'g'rilaydi.
"""

from urllib.parse import urlparse

from rest_framework import serializers
from django.conf import settings
from django.core.files.storage import default_storage
from django.utils.text import slugify

from .models import (
    BlogCategory,
    BlogPost,
    ParentStoreCategory,
    ParentStorePromoBanner,
    ParentStoreProduct,
    ProductTag,
)
from .translation import fill_missing, translate as _translate, SUPPORTED as _LANGS

# Mahsulot va Blog uchun "uz" tildagi qiymatni avtomatik
# qolgan tillarga tarjima qilishda ishtirok etadigan maydonlar.
_PRODUCT_I18N_FIELDS = (
    "name",
    "short_description",
    "description",
    "category_label",
)
_BLOG_I18N_FIELDS = (
    "title",
    "short_description",
    "content",
)


def _autotranslate_payload(data, fields, source="uz"):
    """`data` ichidagi bo'sh `_ru/_en` maydonlarni `source` tilidagi
    qiymatdan tarjima qilib to'ldiradi.

    `data` — dict-like (validated_data yoki request payload). In-place
    o'zgartiriladi va shu o'zi qaytariladi.
    """
    for f in fields:
        base = (data.get(f) or "").strip()
        if not base:
            continue
        values = {
            "uz": base,
            "ru": (data.get(f"{f}_ru") or "").strip(),
            "en": (data.get(f"{f}_en") or "").strip(),
        }
        if source != "uz":
            values[source] = base
        filled = fill_missing(values, source=source)
        for lang_code, value in filled.items():
            if lang_code == source:
                continue
            field_name = f if lang_code == "uz" else f"{f}_{lang_code}"
            if not (data.get(field_name) or "").strip():
                data[field_name] = value
    return data


def _normalize_tag_name(value):
    if value is None:
        return ""
    s = str(value).strip().lstrip("#").strip()
    return s


def _ensure_tag(name):
    """Tag nomi bo'yicha mavjud bo'lsa qaytaradi, yo'q bo'lsa
    yaratadi va boshqa tillarga tarjima qiladi."""
    base = _normalize_tag_name(name)
    if not base:
        return None
    # Avval mavjudni topishga harakat
    existing = ProductTag.objects.filter(name__iexact=base).first()
    if existing:
        return existing
    existing = ProductTag.objects.filter(name_ru__iexact=base).first()
    if existing:
        return existing
    existing = ProductTag.objects.filter(name_en__iexact=base).first()
    if existing:
        return existing

    # Yangi yaratamiz
    translated = {"uz": base, "ru": "", "en": ""}
    try:
        translated = fill_missing(translated, source="uz")
    except Exception:
        pass
    slug_base = slugify(base) or f"tag-{ProductTag.objects.count() + 1}"
    slug = slug_base
    i = 1
    while ProductTag.objects.filter(slug=slug).exists():
        i += 1
        slug = f"{slug_base}-{i}"
    tag = ProductTag.objects.create(
        name=base,
        name_ru=translated.get("ru") or "",
        name_en=translated.get("en") or "",
        slug=slug,
    )
    return tag


def _resolve_tags(values):
    """`values` — string list yoki aralash list/string. Har bir element
    uchun `_ensure_tag` chaqirib, ProductTag obyektlari ro'yxatini qaytaradi.
    """
    if values is None:
        return []
    if isinstance(values, str):
        # CSV bo'lsa parse qilamiz
        raw_list = [p.strip() for p in values.split(",")]
    elif isinstance(values, (list, tuple)):
        raw_list = values
    else:
        raw_list = [values]
    seen = set()
    result = []
    for item in raw_list:
        # element ID (int yoki digit-string) bo'lishi mumkin
        if isinstance(item, int):
            tag = ProductTag.objects.filter(id=item).first()
        elif isinstance(item, str) and item.strip().isdigit():
            tag = ProductTag.objects.filter(id=int(item.strip())).first()
        elif isinstance(item, dict):
            tag = _ensure_tag(item.get("name") or item.get("name_uz") or "")
        else:
            tag = _ensure_tag(item)
        if tag and tag.id not in seen:
            seen.add(tag.id)
            result.append(tag)
    return result


def _url_or_path_to_field_value(value):
    """Mijoz ImageField uchun URL yoki path yuborgan bo'lsa, ImageField uchun
    relativ path qaytaramiz (yoki None — agar ajratib bo'lmasa).

    Misol: "https://api.jojoapp.uz/media/admin_uploads/products/abc.jpg"
           -> "admin_uploads/products/abc.jpg"
    """
    if not value:
        return None
    if not isinstance(value, str):
        return None
    s = value.strip()
    if not s:
        return None
    # URL bo'lsa, /media/ dan keyingi qismni olamiz
    if s.startswith("http://") or s.startswith("https://"):
        path = urlparse(s).path
        media_url = (settings.MEDIA_URL or "/media/").rstrip("/") + "/"
        idx = path.find(media_url)
        if idx == -1:
            return None
        rel = path[idx + len(media_url):]
        return rel if default_storage.exists(rel) else rel  # trust the client
    # Allaqachon relativ path
    if s.startswith("/"):
        s = s[1:]
    return s


def _uniq_slug(model, base, instance_id=None):
    base = slugify(base) or "item"
    s = base
    i = 1
    qs = model.objects.filter(slug=s)
    if instance_id:
        qs = qs.exclude(id=instance_id)
    while qs.exists():
        i += 1
        s = f"{base}-{i}"
        qs = model.objects.filter(slug=s)
        if instance_id:
            qs = qs.exclude(id=instance_id)
    return s


# ============================================================================
# Store category
# ============================================================================


class AdminStoreCategorySerializer(serializers.ModelSerializer):
    """Read + write. Slug auto-generatsiya, `category_type` alias `product_type`."""

    category_type = serializers.CharField(source="product_type", required=False, allow_blank=True)
    icon = serializers.ImageField(required=False, allow_null=True)

    class Meta:
        model = ParentStoreCategory
        fields = [
            "id",
            "name",
            "name_ru", "name_en",
            "slug",
            "product_type",
            "category_type",
            "icon",
            "is_active",
            "order",
        ]
        extra_kwargs = {
            "slug": {"required": False, "allow_blank": True},
            "product_type": {"required": False, "allow_blank": True},
            "name_ru": {"required": False, "allow_blank": True},
            "name_en": {"required": False, "allow_blank": True},
        }

    def to_internal_value(self, data):
        # UI may send icon as URL string — convert to relative path.
        data = data.copy() if hasattr(data, "copy") else dict(data)
        icon = data.get("icon")
        if isinstance(icon, str):
            data.pop("icon", None)
            self._icon_path = _url_or_path_to_field_value(icon)
        else:
            self._icon_path = None
        return super().to_internal_value(data)

    def create(self, validated_data):
        validated_data.pop("category_type", None)  # already mapped via source
        if not validated_data.get("slug"):
            validated_data["slug"] = _uniq_slug(ParentStoreCategory, validated_data.get("name", ""))
        if not validated_data.get("product_type"):
            validated_data["product_type"] = ParentStoreCategory.TYPE_OTHER
        obj = super().create(validated_data)
        if getattr(self, "_icon_path", None):
            obj.icon.name = self._icon_path
            obj.save(update_fields=["icon"])
        return obj

    def update(self, instance, validated_data):
        if validated_data.get("slug") == "":
            validated_data.pop("slug", None)
        obj = super().update(instance, validated_data)
        if getattr(self, "_icon_path", None):
            obj.icon.name = self._icon_path
            obj.save(update_fields=["icon"])
        return obj


# ============================================================================
# Store product
# ============================================================================


class AdminProductTagMiniSerializer(serializers.ModelSerializer):
    """Tag o'qish uchun yengillashtirilgan ko'rinish."""

    class Meta:
        model = ProductTag
        fields = ["id", "name", "name_ru", "name_en", "slug"]


class AdminStoreProductSerializer(serializers.ModelSerializer):
    """Frontend `cover_image`, `product_type`, `brand`, `stock_count` yuboradi.
    Bizning modelda bu fieldlar yo'q yoki boshqa nomda — sukunatda tashlab yuboramiz.

    Tags: frontend `tags` ni string list yoki id list sifatida yuboradi.
    Yangi tag bo'lsa avtomatik yaratamiz va uch tilga tarjima qilib qo'yamiz.

    `auto_translate=true` yuborilsa, bo'sh _ru/_en maydonlar `uz`dan
    tarjima qilinadi (uzun matnlar chunklarga bo'linadi).
    """

    cover_image = serializers.SerializerMethodField()
    product_type = serializers.SerializerMethodField()
    brand = serializers.SerializerMethodField()
    stock_count = serializers.SerializerMethodField()
    tags = serializers.SerializerMethodField()
    tags_input = serializers.ListField(
        child=serializers.JSONField(),
        write_only=True,
        required=False,
        help_text="Tag nomlari ro'yxati. Yangisi bo'lsa avtomatik yaratiladi.",
    )
    auto_translate = serializers.BooleanField(
        write_only=True,
        required=False,
        default=False,
        help_text="True bo'lsa, bo'sh _ru/_en maydonlar uz'dan tarjima qilinadi.",
    )
    translate_source = serializers.ChoiceField(
        write_only=True,
        required=False,
        default="uz",
        choices=[("uz", "uz"), ("ru", "ru"), ("en", "en")],
        help_text="Auto-translate qaysi tildan ish ko'rsin.",
    )

    class Meta:
        model = ParentStoreProduct
        fields = [
            "id",
            "name",
            "name_ru", "name_en",
            "slug",
            "category",
            "category_label",
            "category_label_ru", "category_label_en",
            "age_label",
            "price",
            "old_price",
            "badge",
            "features",
            "hashtags",
            "tags",
            "tags_input",
            "auto_translate",
            "translate_source",
            "short_description",
            "short_description_ru", "short_description_en",
            "description",
            "description_ru", "description_en",
            "thumbnail",
            "cover_image",
            "product_type",
            "brand",
            "stock_count",
            "video_url",
            "is_featured",
            "is_active",
            "order",
            "placeholder_label",
            "placeholder_tint",
        ]
        extra_kwargs = {
            "slug": {"required": False, "allow_blank": True},
            "name": {"required": True},
            "name_ru": {"required": False, "allow_blank": True},
            "name_en": {"required": False, "allow_blank": True},
            "category_label_ru": {"required": False, "allow_blank": True},
            "category_label_en": {"required": False, "allow_blank": True},
            "short_description": {"required": False, "allow_blank": True},
            "short_description_ru": {"required": False, "allow_blank": True},
            "short_description_en": {"required": False, "allow_blank": True},
            "description": {"required": False, "allow_blank": True},
            "description_ru": {"required": False, "allow_blank": True},
            "description_en": {"required": False, "allow_blank": True},
            "price": {"required": False, "default": 0},
            "category": {"required": False, "allow_null": True},
        }

    def get_cover_image(self, obj):
        if obj.thumbnail:
            req = self.context.get("request")
            url = obj.thumbnail.url
            return req.build_absolute_uri(url) if req else url
        return None

    def get_product_type(self, obj):
        return obj.category_label or ""

    def get_brand(self, obj):
        return ""

    def get_stock_count(self, obj):
        return 0

    def get_tags(self, obj):
        if obj.pk is None:
            return []
        return AdminProductTagMiniSerializer(obj.tags.all(), many=True).data

    def to_internal_value(self, data):
        data = data.copy() if hasattr(data, "copy") else dict(data)
        # cover_image va thumbnail URL string bo'lsa — relativ path'ga aylantirib saqlaymiz
        cover = data.pop("cover_image", None)
        thumb = data.pop("thumbnail", None) if isinstance(data.get("thumbnail"), str) else None
        chosen = cover or thumb
        self._thumb_path = _url_or_path_to_field_value(chosen) if chosen else None
        # frontend may send 'product_type' as free-text — store it as category_label
        ptype = data.pop("product_type", None)
        if ptype and not data.get("category_label"):
            data["category_label"] = ptype
        # ignore fields not in model
        data.pop("brand", None)
        data.pop("stock_count", None)
        # `tags` field nomi backend uchun M2M (read-only `tags` SerializerMethodField),
        # write uchun esa `tags_input` qabul qilamiz. Frontend osonlik uchun
        # ikkalasini ham yuborishi mumkin — `tags`ni `tags_input`ga o'tkazamiz.
        if "tags" in data and "tags_input" not in data:
            data["tags_input"] = data.pop("tags")
        return super().to_internal_value(data)

    def _maybe_autotranslate(self, validated_data):
        if not validated_data.pop("auto_translate", False):
            validated_data.pop("translate_source", None)
            return validated_data
        source = validated_data.pop("translate_source", "uz") or "uz"
        try:
            _autotranslate_payload(validated_data, _PRODUCT_I18N_FIELDS, source=source)
        except Exception:
            # Tarjima xizmati tushib qolsa ham saqlash davom etsin.
            pass
        return validated_data

    def _apply_tags(self, obj, tag_values):
        if tag_values is None:
            return
        tags = _resolve_tags(tag_values)
        obj.tags.set(tags)
        # usage_count statistikasi
        for tag in tags:
            ProductTag.objects.filter(id=tag.id).update(usage_count=tag.products.count())

    def create(self, validated_data):
        tag_values = validated_data.pop("tags_input", None)
        validated_data = self._maybe_autotranslate(validated_data)
        if not validated_data.get("slug"):
            validated_data["slug"] = _uniq_slug(ParentStoreProduct, validated_data.get("name", ""))
        obj = super().create(validated_data)
        if getattr(self, "_thumb_path", None):
            obj.thumbnail.name = self._thumb_path
            obj.save(update_fields=["thumbnail"])
        self._apply_tags(obj, tag_values)
        return obj

    def update(self, instance, validated_data):
        tag_values = validated_data.pop("tags_input", None)
        validated_data = self._maybe_autotranslate(validated_data)
        if validated_data.get("slug") == "":
            validated_data.pop("slug", None)
        obj = super().update(instance, validated_data)
        if getattr(self, "_thumb_path", None):
            obj.thumbnail.name = self._thumb_path
            obj.save(update_fields=["thumbnail"])
        if tag_values is not None:
            self._apply_tags(obj, tag_values)
        return obj


# ============================================================================
# Banner
# ============================================================================


class AdminBannerSerializer(serializers.ModelSerializer):
    class Meta:
        model = ParentStorePromoBanner
        fields = [
            "id",
            "kicker",
            "kicker_ru", "kicker_en",
            "title",
            "title_ru", "title_en",
            "subtitle",
            "subtitle_ru", "subtitle_en",
            "theme",
            "image",
            "link_product",
            "link_category_type",
            "gift_icon",
            "placeholder_label",
            "placeholder_tint",
            "is_active",
            "order",
        ]
        extra_kwargs = {
            "kicker": {"required": False, "allow_blank": True, "default": ""},
            "kicker_ru": {"required": False, "allow_blank": True, "default": ""},
            "kicker_en": {"required": False, "allow_blank": True, "default": ""},
            "title": {"required": True},
            "title_ru": {"required": False, "allow_blank": True, "default": ""},
            "title_en": {"required": False, "allow_blank": True, "default": ""},
            "subtitle": {"required": False, "allow_blank": True, "default": ""},
            "subtitle_ru": {"required": False, "allow_blank": True, "default": ""},
            "subtitle_en": {"required": False, "allow_blank": True, "default": ""},
            "theme": {"required": False, "default": ParentStorePromoBanner.THEME_CREAM},
            "link_product": {"required": False, "allow_null": True},
            "link_category_type": {"required": False, "allow_blank": True, "default": ""},
        }

    def to_internal_value(self, data):
        data = data.copy() if hasattr(data, "copy") else dict(data)
        img = data.pop("image", None) if isinstance(data.get("image"), str) else None
        self._image_path = _url_or_path_to_field_value(img) if img else None
        # Frontend may send link_category_type as null
        if data.get("link_category_type") is None:
            data["link_category_type"] = ""
        return super().to_internal_value(data)

    def create(self, validated_data):
        obj = super().create(validated_data)
        if getattr(self, "_image_path", None):
            obj.image.name = self._image_path
            obj.save(update_fields=["image"])
        return obj

    def update(self, instance, validated_data):
        obj = super().update(instance, validated_data)
        if getattr(self, "_image_path", None):
            obj.image.name = self._image_path
            obj.save(update_fields=["image"])
        return obj


# ============================================================================
# Blog category
# ============================================================================


class AdminBlogCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = BlogCategory
        fields = [
            "id",
            "name",
            "name_ru", "name_en",
            "icon",
            "is_active",
            "order",
        ]
        extra_kwargs = {
            "name": {"required": True},
            "name_ru": {"required": False, "allow_blank": True},
            "name_en": {"required": False, "allow_blank": True},
            "order": {"required": False, "default": 0},
        }

    def to_internal_value(self, data):
        data = data.copy() if hasattr(data, "copy") else dict(data)
        icon = data.pop("icon", None) if isinstance(data.get("icon"), str) else None
        self._icon_path = _url_or_path_to_field_value(icon) if icon else None
        return super().to_internal_value(data)

    def create(self, validated_data):
        obj = super().create(validated_data)
        if getattr(self, "_icon_path", None):
            obj.icon.name = self._icon_path
            obj.save(update_fields=["icon"])
        return obj

    def update(self, instance, validated_data):
        obj = super().update(instance, validated_data)
        if getattr(self, "_icon_path", None):
            obj.icon.name = self._icon_path
            obj.save(update_fields=["icon"])
        return obj


# ============================================================================
# Blog post
# ============================================================================


class AdminBlogPostSerializer(serializers.ModelSerializer):
    """Frontend `excerpt`, `body`, `cover_image`, `read_minutes` yuboradi.
    Backendda esa `short_description`, `content`, `thumbnail`, `reading_time_minutes`."""

    excerpt = serializers.CharField(source="short_description", required=False, allow_blank=True, allow_null=True)
    body = serializers.CharField(source="content", required=False, allow_blank=True, allow_null=True)
    read_minutes = serializers.IntegerField(source="reading_time_minutes", required=False, default=5)
    cover_image = serializers.SerializerMethodField()

    class Meta:
        model = BlogPost
        fields = [
            "id",
            "title",
            "title_ru", "title_en",
            "excerpt",
            "short_description",
            "short_description_ru", "short_description_en",
            "body",
            "content",
            "content_ru", "content_en",
            "category",
            "post_type",
            "read_minutes",
            "reading_time_minutes",
            "thumbnail",
            "cover_image",
            "video_url",
            "is_active",
            "is_featured",
            "order",
        ]
        extra_kwargs = {
            "title": {"required": True},
            "title_ru": {"required": False, "allow_blank": True},
            "title_en": {"required": False, "allow_blank": True},
            "post_type": {"required": False, "default": BlogPost.TYPE_BLOG},
            "category": {"required": False, "allow_null": True},
            "short_description": {"required": False, "allow_blank": True, "allow_null": True},
            "short_description_ru": {"required": False, "allow_blank": True, "default": ""},
            "short_description_en": {"required": False, "allow_blank": True, "default": ""},
            "content": {"required": False, "allow_blank": True, "allow_null": True},
            "content_ru": {"required": False, "allow_blank": True, "default": ""},
            "content_en": {"required": False, "allow_blank": True, "default": ""},
        }

    def get_cover_image(self, obj):
        if obj.thumbnail:
            req = self.context.get("request")
            url = obj.thumbnail.url
            return req.build_absolute_uri(url) if req else url
        return None

    def to_internal_value(self, data):
        data = data.copy() if hasattr(data, "copy") else dict(data)
        cover = data.pop("cover_image", None)
        thumb = data.pop("thumbnail", None) if isinstance(data.get("thumbnail"), str) else None
        chosen = cover or thumb
        self._thumb_path = _url_or_path_to_field_value(chosen) if chosen else None
        if not data.get("post_type"):
            data["post_type"] = BlogPost.TYPE_BLOG
        return super().to_internal_value(data)

    def create(self, validated_data):
        obj = super().create(validated_data)
        if getattr(self, "_thumb_path", None):
            obj.thumbnail.name = self._thumb_path
            obj.save(update_fields=["thumbnail"])
        return obj

    def update(self, instance, validated_data):
        obj = super().update(instance, validated_data)
        if getattr(self, "_thumb_path", None):
            obj.thumbnail.name = self._thumb_path
            obj.save(update_fields=["thumbnail"])
        return obj
