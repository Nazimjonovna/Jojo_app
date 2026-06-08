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
)


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


class AdminStoreProductSerializer(serializers.ModelSerializer):
    """Frontend `cover_image`, `product_type`, `brand`, `stock_count` yuboradi.
    Bizning modelda bu fieldlar yo'q yoki boshqa nomda — sukunatda tashlab yuboramiz."""

    cover_image = serializers.SerializerMethodField()
    product_type = serializers.SerializerMethodField()
    brand = serializers.SerializerMethodField()
    stock_count = serializers.SerializerMethodField()

    class Meta:
        model = ParentStoreProduct
        fields = [
            "id",
            "name",
            "slug",
            "category",
            "category_label",
            "age_label",
            "price",
            "old_price",
            "badge",
            "features",
            "short_description",
            "description",
            "thumbnail",
            "cover_image",   # read-only alias
            "product_type",  # read-only alias (returns badge or category_label)
            "brand",         # always "" — model has no brand
            "stock_count",   # always 0 — model has no stock
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
        return super().to_internal_value(data)

    def create(self, validated_data):
        if not validated_data.get("slug"):
            validated_data["slug"] = _uniq_slug(ParentStoreProduct, validated_data.get("name", ""))
        obj = super().create(validated_data)
        if getattr(self, "_thumb_path", None):
            obj.thumbnail.name = self._thumb_path
            obj.save(update_fields=["thumbnail"])
        return obj

    def update(self, instance, validated_data):
        if validated_data.get("slug") == "":
            validated_data.pop("slug", None)
        obj = super().update(instance, validated_data)
        if getattr(self, "_thumb_path", None):
            obj.thumbnail.name = self._thumb_path
            obj.save(update_fields=["thumbnail"])
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
            "title",
            "subtitle",
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
            "title": {"required": True},
            "subtitle": {"required": False, "allow_blank": True, "default": ""},
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
            "icon",
            "is_active",
            "order",
        ]
        extra_kwargs = {
            "name": {"required": True},
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
            "excerpt",
            "short_description",
            "body",
            "content",
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
            "post_type": {"required": False, "default": BlogPost.TYPE_BLOG},
            "category": {"required": False, "allow_null": True},
            "short_description": {"required": False, "allow_blank": True, "allow_null": True},
            "content": {"required": False, "allow_blank": True, "allow_null": True},
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
