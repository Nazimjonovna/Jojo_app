from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import Group

from .models import (
    User,
    OTPCode,
    PairingCode,
    ParentChild,
    ChildLocation,
    ChildLastLocation,
    SafeRoute,
    SafeRoutePoint,
    ChildRouteAssignment,
    RouteAlert,
    DeviceToken,
    SavedLocation,
    GameCategory,
    GameItem,
    ShopCategory,
    ShopItem,
    ChildWallet,
    ChildTransaction,
    ShopPurchase,
    SOSAlert,
)


CONTENT_ADMIN_GROUP = "content_admin"
SUPPORT_ADMIN_GROUP = "support_admin"


CONTENT_ADMIN_MODELS = {
    "GameCategory",
    "GameItem",
    "ShopCategory",
    "ShopItem",
}


SUPPORT_ADMIN_MODELS = {
    "SOSAlert",
    "RouteAlert",
    "ChildLocation",
    "ChildLastLocation",
    "DeviceToken",
    "SavedLocation",
    "ParentChild",
    "PairingCode",
    "ChildWallet",
    "ChildTransaction",
    "ShopPurchase",
}


SUPPORT_READONLY_MODELS = {
    "RouteAlert",
    "ChildLocation",
    "ChildLastLocation",
    "DeviceToken",
    "ParentChild",
    "PairingCode",
    "ChildWallet",
    "ChildTransaction",
    "ShopPurchase",
}


def user_group_names(user):
    if not user or not user.is_authenticated:
        return set()

    return set(user.groups.values_list("name", flat=True))


def allowed_models_for_user(user):
    if user.is_superuser:
        return "all"

    groups = user_group_names(user)
    allowed = set()

    if CONTENT_ADMIN_GROUP in groups:
        allowed |= CONTENT_ADMIN_MODELS

    if SUPPORT_ADMIN_GROUP in groups:
        allowed |= SUPPORT_ADMIN_MODELS

    return allowed


class RoleBasedAdminMixin:
    def model_name(self):
        return self.model.__name__

    def has_role_access(self, request):
        if request.user.is_superuser:
            return True

        allowed = allowed_models_for_user(request.user)

        if allowed == "all":
            return True

        return self.model_name() in allowed

    def has_module_permission(self, request):
        return self.has_role_access(request)

    def has_view_permission(self, request, obj=None):
        return self.has_role_access(request)

    def has_add_permission(self, request):
        if request.user.is_superuser:
            return True

        model_name = self.model_name()
        groups = user_group_names(request.user)

        if CONTENT_ADMIN_GROUP in groups and model_name in CONTENT_ADMIN_MODELS:
            return True

        return False

    def has_change_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True

        model_name = self.model_name()
        groups = user_group_names(request.user)

        if CONTENT_ADMIN_GROUP in groups and model_name in CONTENT_ADMIN_MODELS:
            return True

        if SUPPORT_ADMIN_GROUP in groups and model_name in SUPPORT_ADMIN_MODELS:
            return model_name not in SUPPORT_READONLY_MODELS

        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


class SafeRoutePointInline(admin.TabularInline):
    model = SafeRoutePoint
    extra = 1


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = (
        "id",
        "phone",
        "username",
        "full_name",
        "role",
        "gender",
        "age",
        "language",
        "child_status",
        "is_active",
        "is_staff",
        "is_superuser",
    )

    list_filter = (
        "role",
        "gender",
        "language",
        "child_status",
        "is_active",
        "is_staff",
        "is_superuser",
    )

    search_fields = (
        "phone",
        "username",
        "full_name",
        "first_name",
        "last_name",
    )

    ordering = ("-id",)

    fieldsets = UserAdmin.fieldsets + (
        (
            "Jojo fields",
            {
                "fields": (
                    "phone",
                    "full_name",
                    "role",
                    "gender",
                    "language",
                    "age",
                    "child_status",
                    "pending_delete_at",
                    "avatar",
                )
            },
        ),
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "phone",
                    "username",
                    "full_name",
                    "role",
                    "gender",
                    "language",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "password1",
                    "password2",
                ),
            },
        ),
    )

    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(OTPCode)
class OTPCodeAdmin(RoleBasedAdminMixin, admin.ModelAdmin):
    list_display = (
        "id",
        "phone",
        "code",
        "is_used",
        "attempt_count",
        "blocked_until",
        "expires_at",
        "created_at",
    )
    list_filter = ("is_used", "created_at")
    search_fields = ("phone", "code")
    readonly_fields = (
        "phone",
        "code",
        "expires_at",
        "is_used",
        "attempt_count",
        "first_attempt_at",
        "blocked_until",
        "created_at",
    )


@admin.register(PairingCode)
class PairingCodeAdmin(RoleBasedAdminMixin, admin.ModelAdmin):
    list_display = (
        "id",
        "parent",
        "child",
        "code",
        "is_used",
        "expires_at",
        "created_at",
    )
    list_filter = ("is_used", "created_at")
    search_fields = (
        "code",
        "parent__phone",
        "parent__full_name",
        "child__phone",
        "child__full_name",
    )
    readonly_fields = (
        "parent",
        "child",
        "code",
        "expires_at",
        "is_used",
        "child_name",
        "child_gender",
        "child_age",
        "child_avatar",
        "created_at",
    )


@admin.register(ParentChild)
class ParentChildAdmin(RoleBasedAdminMixin, admin.ModelAdmin):
    list_display = (
        "id",
        "parent",
        "child",
        "created_at",
    )
    search_fields = (
        "parent__phone",
        "parent__full_name",
        "child__phone",
        "child__full_name",
    )
    readonly_fields = (
        "parent",
        "child",
        "created_at",
    )


@admin.register(ChildLocation)
class ChildLocationAdmin(RoleBasedAdminMixin, admin.ModelAdmin):
    list_display = (
        "id",
        "child",
        "latitude",
        "longitude",
        "battery_level",
        "speed",
        "heading",
        "source",
        "created_at",
    )
    list_filter = ("source", "created_at")
    search_fields = (
        "child__phone",
        "child__full_name",
    )
    readonly_fields = (
        "child",
        "latitude",
        "longitude",
        "accuracy",
        "battery_level",
        "speed",
        "heading",
        "source",
        "created_at",
    )


@admin.register(ChildLastLocation)
class ChildLastLocationAdmin(RoleBasedAdminMixin, admin.ModelAdmin):
    list_display = (
        "id",
        "child",
        "latitude",
        "longitude",
        "battery_level",
        "speed",
        "heading",
        "updated_at",
    )
    search_fields = (
        "child__phone",
        "child__full_name",
    )
    readonly_fields = (
        "child",
        "latitude",
        "longitude",
        "accuracy",
        "battery_level",
        "speed",
        "heading",
        "updated_at",
    )


@admin.register(SafeRoute)
class SafeRouteAdmin(RoleBasedAdminMixin, admin.ModelAdmin):
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
        "parent__full_name",
    )
    list_filter = ("is_active", "created_at")
    inlines = [SafeRoutePointInline]


@admin.register(ChildRouteAssignment)
class ChildRouteAssignmentAdmin(RoleBasedAdminMixin, admin.ModelAdmin):
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
        "created_at",
    )
    search_fields = (
        "parent__phone",
        "parent__full_name",
        "child__phone",
        "child__full_name",
        "route__name",
    )


@admin.register(RouteAlert)
class RouteAlertAdmin(RoleBasedAdminMixin, admin.ModelAdmin):
    list_display = (
        "id",
        "child",
        "assignment",
        "alert_type",
        "distance_meters",
        "created_at",
    )
    list_filter = ("alert_type", "created_at")
    search_fields = (
        "child__phone",
        "child__full_name",
    )
    readonly_fields = (
        "assignment",
        "child",
        "alert_type",
        "distance_meters",
        "location",
        "created_at",
    )


@admin.register(DeviceToken)
class DeviceTokenAdmin(RoleBasedAdminMixin, admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "device_id",
        "device_type",
        "is_active",
        "last_login_at",
        "created_at",
    )
    list_filter = (
        "device_type",
        "is_active",
        "created_at",
    )
    search_fields = (
        "user__phone",
        "user__full_name",
        "device_id",
        "token",
    )
    readonly_fields = (
        "user",
        "device_id",
        "token",
        "device_type",
        "is_active",
        "last_login_at",
        "created_at",
        "updated_at",
    )


@admin.register(SavedLocation)
class SavedLocationAdmin(RoleBasedAdminMixin, admin.ModelAdmin):
    list_display = (
        "id",
        "parent",
        "name",
        "location_type",
        "latitude",
        "longitude",
        "radius_meters",
        "is_active",
        "created_at",
    )
    list_filter = (
        "location_type",
        "is_active",
        "created_at",
    )
    search_fields = (
        "name",
        "address",
        "parent__phone",
        "parent__full_name",
    )


@admin.register(GameCategory)
class GameCategoryAdmin(RoleBasedAdminMixin, admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "is_active",
        "order",
        "created_at",
    )
    list_filter = ("is_active",)
    search_fields = ("name",)
    ordering = ("order", "id")


@admin.register(GameItem)
class GameItemAdmin(RoleBasedAdminMixin, admin.ModelAdmin):
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
    list_filter = (
        "is_active",
        "is_featured",
        "category",
    )
    search_fields = (
        "title",
        "description",
    )
    ordering = ("order", "-created_at")


@admin.register(ShopCategory)
class ShopCategoryAdmin(RoleBasedAdminMixin, admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "is_active",
        "order",
        "created_at",
    )
    list_filter = ("is_active",)
    search_fields = ("name",)
    ordering = ("order", "id")


@admin.register(ShopItem)
class ShopItemAdmin(RoleBasedAdminMixin, admin.ModelAdmin):
    list_display = (
        "id",
        "title",
        "category",
        "price_points",
        "stock",
        "age_min",
        "age_max",
        "is_active",
        "is_featured",
        "order",
        "created_at",
    )
    list_filter = (
        "is_active",
        "is_featured",
        "category",
    )
    search_fields = (
        "title",
        "description",
    )
    ordering = ("order", "-created_at")


@admin.register(ChildWallet)
class ChildWalletAdmin(RoleBasedAdminMixin, admin.ModelAdmin):
    list_display = (
        "id",
        "child",
        "balance",
        "updated_at",
    )
    search_fields = (
        "child__phone",
        "child__full_name",
    )
    readonly_fields = (
        "child",
        "balance",
        "updated_at",
    )


@admin.register(ChildTransaction)
class ChildTransactionAdmin(RoleBasedAdminMixin, admin.ModelAdmin):
    list_display = (
        "id",
        "child",
        "amount",
        "transaction_type",
        "source",
        "created_at",
    )
    list_filter = (
        "transaction_type",
        "source",
        "created_at",
    )
    search_fields = (
        "child__phone",
        "child__full_name",
        "description",
    )
    readonly_fields = (
        "child",
        "amount",
        "transaction_type",
        "source",
        "description",
        "created_at",
    )


@admin.register(ShopPurchase)
class ShopPurchaseAdmin(RoleBasedAdminMixin, admin.ModelAdmin):
    list_display = (
        "id",
        "child",
        "item",
        "price_points",
        "status",
        "created_at",
    )
    list_filter = (
        "status",
        "created_at",
    )
    search_fields = (
        "child__phone",
        "child__full_name",
        "item__title",
    )


@admin.register(SOSAlert)
class SOSAlertAdmin(RoleBasedAdminMixin, admin.ModelAdmin):
    list_display = (
        "id",
        "child",
        "parent",
        "status",
        "latitude",
        "longitude",
        "created_at",
    )
    list_filter = (
        "status",
        "created_at",
    )
    search_fields = (
        "child__phone",
        "child__full_name",
        "parent__phone",
        "parent__full_name",
    )
    readonly_fields = (
        "child",
        "parent",
        "latitude",
        "longitude",
        "address",
        "note",
        "created_at",
        "updated_at",
    )


try:
    admin.site.unregister(Group)
except admin.sites.NotRegistered:
    pass


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ("id", "name")
    search_fields = ("name",)

    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser