from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import (
    User,
    OTPCode,
    PairingCode,
    ParentChild,
    ChildLocation,
    ChildLastLocation,
    DeviceToken,
    SafeRoute,
    SafeRoutePoint,
    ChildRouteAssignment,
    RouteAlert,
    GameCategory,
    GameItem,
    ShopCategory,
    ShopItem,
    ChildWallet,
    ChildTransaction,
    ShopPurchase,
    SOSAlert,
)


class SafeRoutePointInline(admin.TabularInline):
    model = SafeRoutePoint
    extra = 1


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = (
        "id",
        "phone",
        "username",
        "first_name",
        "last_name",
        "role",
        "language",
        "is_active",
        "is_staff",
    )
    list_filter = (
        "role",
        "language",
        "is_active",
        "is_staff",
    )
    search_fields = (
        "phone",
        "username",
        "first_name",
        "last_name",
    )

    fieldsets = UserAdmin.fieldsets + (
        (
            "Jojo fields",
            {
                "fields": (
                    "phone",
                    "role",
                    "language",
                    "avatar",
                )
            },
        ),
    )


@admin.register(SafeRoute)
class SafeRouteAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "parent",
        "name",
        "is_active",
        "created_at",
    )
    search_fields = (
        "name",
        "parent__phone",
    )
    list_filter = ("is_active",)
    inlines = [SafeRoutePointInline]


@admin.register(ChildRouteAssignment)
class ChildRouteAssignmentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "parent",
        "child",
        "route",
        "status",
        "allowed_radius_meters",
        "notify_on_deviation",
        "created_at",
    )
    list_filter = (
        "status",
        "notify_on_deviation",
    )


@admin.register(RouteAlert)
class RouteAlertAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "child",
        "assignment",
        "alert_type",
        "distance_meters",
        "created_at",
    )
    list_filter = ("alert_type",)
    
    
@admin.register(GameCategory)
class GameCategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "is_active", "order", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name",)


@admin.register(GameItem)
class GameItemAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "title",
        "category",
        "age_min",
        "age_max",
        "reward_points",
        "is_active",
        "is_featured",
        "order",
        "created_at",
    )
    list_filter = ("is_active", "is_featured", "category")
    search_fields = ("title", "description")


@admin.register(ShopCategory)
class ShopCategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "is_active", "order", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name",)


@admin.register(ShopItem)
class ShopItemAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "title",
        "category",
        "price_points",
        "stock",
        "is_active",
        "is_featured",
        "order",
        "created_at",
    )
    list_filter = ("is_active", "is_featured", "category")
    search_fields = ("title", "description")


@admin.register(ChildWallet)
class ChildWalletAdmin(admin.ModelAdmin):
    list_display = ("id", "child", "balance", "updated_at")
    search_fields = ("child__phone", "child__full_name", "child__username")


@admin.register(ChildTransaction)
class ChildTransactionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "child",
        "amount",
        "transaction_type",
        "source",
        "created_at",
    )
    list_filter = ("transaction_type", "source")
    search_fields = ("child__phone", "child__full_name", "description")


@admin.register(ShopPurchase)
class ShopPurchaseAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "child",
        "item",
        "price_points",
        "status",
        "created_at",
    )
    list_filter = ("status",)
    search_fields = ("child__phone", "child__full_name", "item__title")


@admin.register(SOSAlert)
class SOSAlertAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "child",
        "parent",
        "status",
        "latitude",
        "longitude",
        "created_at",
    )
    list_filter = ("status",)
    search_fields = (
        "child__phone",
        "child__full_name",
        "parent__phone",
        "parent__full_name",
    )


admin.site.register(OTPCode)
admin.site.register(PairingCode)
admin.site.register(ParentChild)
admin.site.register(ChildLocation)
admin.site.register(ChildLastLocation)
admin.site.register(DeviceToken)