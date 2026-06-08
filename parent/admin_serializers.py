"""Admin panel uchun maxsus write/read serializerlar.

Frontend yuborayotgan field nomlari va backend model nomlari mos kelmaydi.
Bu fayl ikkalasini bog'laydi: slug auto-generatsiya, alias name mapping va
URL string'larni image fieldlarga to'g'rilaydi.
"""

from rest_framework import serializers
from django.utils.text import slugify

from .models import (
    BlogCategory,
    BlogPost,
    ParentStoreCategory,
    ParentStorePromoBanner,
    ParentStoreProduct,
)


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
        # UI may send icon as URL string — ignore that, keep existing.
        data = data.copy() if hasattr(data, "copy") else dict(data)
        if isinstance(data.get("icon"), str):
            data.pop("icon", None)
        return super().to_internal_value(data)

    def create(self, validated_data):
        validated_data.pop("category_type", None)  # already mapped via source
        if not validated_data.get("slug"):
            validated_data["slug"] = _uniq_slug(ParentStoreCategory, validated_data.get("name", ""))
        if not validated_data.get("product_type"):
            validated_data["product_type"] = ParentStoreCategory.TYPE_OTHER
        return super().create(validated_data)

    def update(self, instance, validated_data):
        if validated_data.get("slug") == "":
            validated_data.pop("slug", None)
        return super().update(instance, validated_data)


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
        # Frontend sends URL strings for cover_image — backend has thumbnail (File).
        # Just drop it. User can upload via Django admin if needed.
        data.pop("cover_image", None)
        if isinstance(data.get("thumbnail"), str):
            data.pop("thumbnail", None)
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
        return super().create(validated_data)

    def update(self, instance, validated_data):
        if validated_data.get("slug") == "":
            validated_data.pop("slug", None)
        return super().update(instance, validated_data)


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
        if isinstance(data.get("image"), str):
            data.pop("image", None)
        # Frontend may send link_category_type as null
        if data.get("link_category_type") is None:
            data["link_category_type"] = ""
        return super().to_internal_value(data)


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
        if isinstance(data.get("icon"), str):
            data.pop("icon", None)
        return super().to_internal_value(data)


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
        data.pop("cover_image", None)
        if isinstance(data.get("thumbnail"), str):
            data.pop("thumbnail", None)
        if not data.get("post_type"):
            data["post_type"] = BlogPost.TYPE_BLOG
        return super().to_internal_value(data)
