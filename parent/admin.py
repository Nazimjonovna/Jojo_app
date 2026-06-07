from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import Group
from django.contrib import admin, messages
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import redirect, render
from django.urls import path
from django.utils import timezone
from django.db.models import Count, Q
from django.contrib import admin, messages
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import path
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.db.models import Q
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
    ChildInstalledApp,
    ChildAppLimit,
    ChildBlockedApp,
    ChildAppUsage,
    ChildSavedLocationState,
    ChildSavedLocationEvent,
    SubscriptionPayment,
    SubscriptionPlan,
    UserSubscription,  
    CallCenterTicket,
    CallCenterComment,  
    BlogCategory,
    BlogPost,
    BlogPostSave,
    BlogPostLike,
)


CONTENT_ADMIN_GROUP = "content_admin"
SUPPORT_ADMIN_GROUP = "support_admin"
CALL_CENTER_GROUP = "call_center"


CONTENT_ADMIN_MODELS = {
    "GameCategory",
    "GameItem",
    "ShopCategory",
    "ShopItem",
    "BlogCategory",
    "BlogPost",
    "BlogPostSave",
    "BlogPostLike",
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
    "ChildInstalledApp",
    "ChildAppLimit",
    "ChildBlockedApp",
    "ChildAppUsage",
    "BlogCategory",
    "BlogPost",
    "BlogPostSave",
    "BlogPostLike",
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
    "ChildInstalledApp",
    "ChildAppUsage",
    "BlogCategory",
    "BlogPost",
    "BlogPostSave",
    "BlogPostLike",
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


def user_in_group(user, group_name):
    return user.groups.filter(name=group_name).exists()


def user_in_group(user, group_name):
    return group_name in user_group_names(user)

def is_call_center_user(user):
    return user.is_superuser or user_in_group(user, CALL_CENTER_GROUP)


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
        "old_price_points",
        "price_points",
        "discount_percent_display",
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

    def discount_percent_display(self, obj):
        return f"{obj.discount_percent()}%"

    discount_percent_display.short_description = "Discount"


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
    

@admin.register(ChildInstalledApp)
class ChildInstalledAppAdmin(RoleBasedAdminMixin, admin.ModelAdmin):
    list_display = (
        "id",
        "child",
        "app_name",
        "package_name",
        "category",
        "is_system_app",
        "is_active",
        "last_synced_at",
    )
    list_filter = ("is_system_app", "is_active", "category")
    search_fields = ("child__phone", "child__full_name", "app_name", "package_name")
    readonly_fields = (
        "child",
        "app_name",
        "package_name",
        "category",
        "is_system_app",
        "is_active",
        "last_synced_at",
        "created_at",
    )


@admin.register(ChildAppLimit)
class ChildAppLimitAdmin(RoleBasedAdminMixin, admin.ModelAdmin):
    list_display = (
        "id",
        "child",
        "app",
        "daily_limit_seconds",
        "is_enabled",
        "created_by",
        "updated_at",
    )
    list_filter = ("is_enabled",)
    search_fields = ("child__phone", "child__full_name", "app__app_name", "app__package_name")


@admin.register(ChildBlockedApp)
class ChildBlockedAppAdmin(RoleBasedAdminMixin, admin.ModelAdmin):
    list_display = (
        "id",
        "child",
        "app",
        "is_blocked",
        "reason",
        "created_by",
        "updated_at",
    )
    list_filter = ("is_blocked",)
    search_fields = ("child__phone", "child__full_name", "app__app_name", "app__package_name")


@admin.register(ChildAppUsage)
class ChildAppUsageAdmin(RoleBasedAdminMixin, admin.ModelAdmin):
    list_display = (
        "id",
        "child",
        "app",
        "usage_date",
        "total_usage_seconds",
        "open_count",
        "updated_at",
    )
    list_filter = ("usage_date",)
    search_fields = ("child__phone", "child__full_name", "app__app_name", "app__package_name")
    readonly_fields = (
        "child",
        "app",
        "usage_date",
        "total_usage_seconds",
        "first_opened_at",
        "last_opened_at",
        "open_count",
        "updated_at",
        "created_at",
    )
    

@admin.register(ChildSavedLocationState)
class ChildSavedLocationStateAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "child",
        "current_location",
        "previous_location",
        "last_event_type",
        "last_event_at",
        "updated_at",
    )
    search_fields = (
        "child__phone",
        "child__full_name",
        "current_location__name",
        "previous_location__name",
    )
    readonly_fields = (
        "child",
        "current_location",
        "previous_location",
        "last_event_type",
        "last_event_at",
        "updated_at",
    )


@admin.register(ChildSavedLocationEvent)
class ChildSavedLocationEventAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "child",
        "parent",
        "saved_location",
        "event_type",
        "created_at",
    )
    list_filter = (
        "event_type",
        "created_at",
    )
    search_fields = (
        "child__phone",
        "child__full_name",
        "parent__phone",
        "saved_location__name",
    )
    readonly_fields = (
        "child",
        "parent",
        "saved_location",
        "event_type",
        "title",
        "body",
        "latitude",
        "longitude",
        "created_at",
    )
    
    
@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "price",
        "currency",
        "duration_value",
        "duration_type",
        "is_trial",
        "trial_days",
        "is_active",
        "is_featured",
        "order",
    )
    list_filter = (
        "is_trial",
        "is_active",
        "is_featured",
        "duration_type",
    )
    search_fields = (
        "name",
        "description",
    )


@admin.register(UserSubscription)
class UserSubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "plan",
        "status",
        "source",
        "started_at",
        "expires_at",
        "created_by",
        "created_at",
    )
    list_filter = (
        "status",
        "source",
        "created_at",
    )
    search_fields = (
        "user__phone",
        "user__full_name",
        "plan__name",
    )


@admin.register(SubscriptionPayment)
class SubscriptionPaymentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "plan",
        "amount",
        "currency",
        "provider",
        "status",
        "paid_at",
        "created_at",
    )
    list_filter = (
        "status",
        "provider",
        "currency",
        "created_at",
    )
    search_fields = (
        "user__phone",
        "user__full_name",
        "plan__name",
        "provider_transaction_id",
    )
    
    
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
        "is_premium",
        "premium_expires_at",
        "is_active",
        "is_staff",
        "is_superuser",
    )

    list_filter = (
        "role",
        "gender",
        "language",
        "is_premium",
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
                    "is_premium",
                    "premium_expires_at",
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

    actions = [
        "block_users",
        "unblock_users",
    ]

    def get_queryset(self, request):
        queryset = super().get_queryset(request)

        if request.user.is_superuser:
            return queryset

        if user_in_group(request.user, CALL_CENTER_GROUP):
            return queryset.filter(role=User.ROLE_PARENT)

        return queryset.none()

    def has_module_permission(self, request):
        return request.user.is_superuser or user_in_group(request.user, CALL_CENTER_GROUP)

    def has_view_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True

        if user_in_group(request.user, CALL_CENTER_GROUP):
            if obj is None:
                return True
            return obj.role == User.ROLE_PARENT

        return False

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True

        if user_in_group(request.user, CALL_CENTER_GROUP):
            if obj is None:
                return True
            return obj.role == User.ROLE_PARENT

        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    def get_readonly_fields(self, request, obj=None):
        if request.user.is_superuser:
            return super().get_readonly_fields(request, obj)

        if user_in_group(request.user, CALL_CENTER_GROUP):
            return (
                "password",
                "last_login",
                "date_joined",
                "is_staff",
                "is_superuser",
                "groups",
                "user_permissions",
                "role",
                "phone",
                "username",
            )

        return super().get_readonly_fields(request, obj)

    def block_users(self, request, queryset):
        if not request.user.is_superuser and not user_in_group(request.user, CALL_CENTER_GROUP):
            self.message_user(request, "Ruxsat yo‘q.", level="error")
            return

        queryset.filter(role=User.ROLE_PARENT).update(is_active=False)
        self.message_user(request, "Tanlangan parent userlar bloklandi.")

    block_users.short_description = "Tanlangan parent userlarni bloklash"

    def unblock_users(self, request, queryset):
        if not request.user.is_superuser and not user_in_group(request.user, CALL_CENTER_GROUP):
            self.message_user(request, "Ruxsat yo‘q.", level="error")
            return

        queryset.filter(role=User.ROLE_PARENT).update(is_active=True)
        self.message_user(request, "Tanlangan parent userlar blokdan chiqarildi.")

    unblock_users.short_description = "Tanlangan parent userlarni blokdan chiqarish"
    

@admin.register(CallCenterTicket)
class CallCenterTicketAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "parent",
        "operator",
        "status",
        "priority",
        "last_contact_at",
        "created_at",
        "updated_at",
    )
    list_filter = (
        "status",
        "priority",
        "created_at",
        "updated_at",
    )
    search_fields = (
        "parent__phone",
        "parent__full_name",
        "operator__phone",
        "operator__full_name",
        "title",
        "description",
    )

    def has_module_permission(self, request):
        return request.user.is_superuser or user_in_group(request.user, CALL_CENTER_GROUP)

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser or user_in_group(request.user, CALL_CENTER_GROUP)

    def has_add_permission(self, request):
        return request.user.is_superuser or user_in_group(request.user, CALL_CENTER_GROUP)

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser or user_in_group(request.user, CALL_CENTER_GROUP)

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(CallCenterComment)
class CallCenterCommentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "ticket",
        "operator",
        "old_status",
        "new_status",
        "created_at",
    )
    list_filter = (
        "old_status",
        "new_status",
        "created_at",
    )
    search_fields = (
        "ticket__parent__phone",
        "ticket__parent__full_name",
        "operator__phone",
        "operator__full_name",
        "comment",
    )

    def has_module_permission(self, request):
        return request.user.is_superuser or user_in_group(request.user, CALL_CENTER_GROUP)

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser or user_in_group(request.user, CALL_CENTER_GROUP)

    def has_add_permission(self, request):
        return request.user.is_superuser or user_in_group(request.user, CALL_CENTER_GROUP)

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser or user_in_group(request.user, CALL_CENTER_GROUP)

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
    

def call_center_dashboard_view(request):
    if not request.user.is_superuser and not user_in_group(request.user, CALL_CENTER_GROUP):
        messages.error(request, "Call Center dashboard uchun ruxsat yo‘q.")
        return redirect("/admin/")

    if request.method == "POST":
        action = request.POST.get("action")
        ticket_id = request.POST.get("ticket_id")
        comment_text = request.POST.get("comment")
        new_status = request.POST.get("new_status")

        ticket = CallCenterTicket.objects.filter(id=ticket_id).select_related("parent").first()

        if ticket:
            old_status = ticket.status

            if action == "change_status" and new_status:
                ticket.status = new_status

                if new_status in [
                    CallCenterTicket.STATUS_CLOSED,
                    CallCenterTicket.STATUS_RESOLVED,
                ]:
                    ticket.closed_at = timezone.now()

                ticket.operator = request.user
                ticket.last_contact_at = timezone.now()
                ticket.save(
                    update_fields=[
                        "status",
                        "operator",
                        "last_contact_at",
                        "closed_at",
                        "updated_at",
                    ]
                )

                CallCenterComment.objects.create(
                    ticket=ticket,
                    operator=request.user,
                    comment=comment_text or f"Status {old_status} dan {new_status} ga o‘zgartirildi.",
                    old_status=old_status,
                    new_status=new_status,
                )

                messages.success(request, "Status o‘zgartirildi.")

            if action == "block_user":
                ticket.parent.is_active = False
                ticket.parent.save(update_fields=["is_active"])

                ticket.status = CallCenterTicket.STATUS_BLOCKED
                ticket.operator = request.user
                ticket.last_contact_at = timezone.now()
                ticket.save(update_fields=["status", "operator", "last_contact_at", "updated_at"])

                CallCenterComment.objects.create(
                    ticket=ticket,
                    operator=request.user,
                    comment=comment_text or "Foydalanuvchi bloklandi.",
                    old_status=old_status,
                    new_status=CallCenterTicket.STATUS_BLOCKED,
                )

                messages.success(request, "Foydalanuvchi bloklandi.")

            if action == "unblock_user":
                ticket.parent.is_active = True
                ticket.parent.save(update_fields=["is_active"])

                CallCenterComment.objects.create(
                    ticket=ticket,
                    operator=request.user,
                    comment=comment_text or "Foydalanuvchi blokdan chiqarildi.",
                    old_status=old_status,
                    new_status=old_status,
                )

                messages.success(request, "Foydalanuvchi blokdan chiqarildi.")

        return redirect("/admin/call-center/")

    search = request.GET.get("q", "")
    selected_ticket_id = request.GET.get("ticket_id")
    status_filter = request.GET.get("status")

    parent_users = User.objects.filter(
        role=User.ROLE_PARENT
    ).order_by("-date_joined")

    if search:
        parent_users = parent_users.filter(
            Q(phone__icontains=search)
            | Q(full_name__icontains=search)
            | Q(username__icontains=search)
        )

    for parent in parent_users[:200]:
        CallCenterTicket.objects.get_or_create(
            parent=parent,
            defaults={
                "title": "Foydalanuvchi nazorati",
                "status": CallCenterTicket.STATUS_NEW,
            }
        )

    tickets = CallCenterTicket.objects.filter(
        parent__role=User.ROLE_PARENT
    ).select_related(
        "parent",
        "operator",
    ).prefetch_related(
        "parent__children_links",
        "comments",
    )

    if search:
        tickets = tickets.filter(
            Q(parent__phone__icontains=search)
            | Q(parent__full_name__icontains=search)
            | Q(parent__username__icontains=search)
        )

    if status_filter:
        tickets = tickets.filter(status=status_filter)

    tickets = tickets.order_by("-updated_at")

    selected_ticket = None

    if selected_ticket_id:
        selected_ticket = tickets.filter(id=selected_ticket_id).first()

    if not selected_ticket:
        selected_ticket = tickets.first()

    stats = {
        "total_parents": User.objects.filter(role=User.ROLE_PARENT).count(),
        "children_connected": User.objects.filter(role=User.ROLE_CHILD, child_status=User.CHILD_STATUS_ACTIVE).count(),
        "premium_users": User.objects.filter(role=User.ROLE_PARENT, is_premium=True).count(),
        "blocked_users": User.objects.filter(role=User.ROLE_PARENT, is_active=False).count(),
        "new_tickets": CallCenterTicket.objects.filter(status=CallCenterTicket.STATUS_NEW).count(),
        "in_progress_tickets": CallCenterTicket.objects.filter(status=CallCenterTicket.STATUS_IN_PROGRESS).count(),
        "waiting_tickets": CallCenterTicket.objects.filter(status=CallCenterTicket.STATUS_WAITING).count(),
        "resolved_tickets": CallCenterTicket.objects.filter(status=CallCenterTicket.STATUS_RESOLVED).count(),
        "closed_tickets": CallCenterTicket.objects.filter(status=CallCenterTicket.STATUS_CLOSED).count(),
    }

    columns = [
        {
            "key": CallCenterTicket.STATUS_NEW,
            "label": "Yangi",
            "tickets": tickets.filter(status=CallCenterTicket.STATUS_NEW)[:50],
        },
        {
            "key": CallCenterTicket.STATUS_IN_PROGRESS,
            "label": "Jarayonda",
            "tickets": tickets.filter(status=CallCenterTicket.STATUS_IN_PROGRESS)[:50],
        },
        {
            "key": CallCenterTicket.STATUS_WAITING,
            "label": "Kutilmoqda",
            "tickets": tickets.filter(status=CallCenterTicket.STATUS_WAITING)[:50],
        },
        {
            "key": CallCenterTicket.STATUS_RESOLVED,
            "label": "Hal qilingan",
            "tickets": tickets.filter(status=CallCenterTicket.STATUS_RESOLVED)[:50],
        },
        {
            "key": CallCenterTicket.STATUS_CLOSED,
            "label": "Yopilgan",
            "tickets": tickets.filter(status=CallCenterTicket.STATUS_CLOSED)[:50],
        },
        {
            "key": CallCenterTicket.STATUS_BLOCKED,
            "label": "Bloklangan",
            "tickets": tickets.filter(status=CallCenterTicket.STATUS_BLOCKED)[:50],
        },
    ]

    context = {
        **admin.site.each_context(request),
        "title": "Call Center",
        "stats": stats,
        "columns": columns,
        "selected_ticket": selected_ticket,
        "statuses": CallCenterTicket.STATUS_CHOICES,
        "search": search,
        "status_filter": status_filter,
    }

    return render(request, "admin/call_center_dashboard.html", context)


original_get_urls = admin.site.get_urls


def get_call_center_urls():
    urls = original_get_urls()

    custom_urls = [
        path(
            "call-center/",
            admin.site.admin_view(call_center_dashboard_view),
            name="call-center-dashboard",
        ),
    ]

    return custom_urls + urls


admin.site.get_urls = get_call_center_urls


def ensure_parent_tickets():
    parents = User.objects.filter(
        role=User.ROLE_PARENT
    ).only(
        "id",
        "phone",
        "full_name",
        "username",
        "role",
    )

    existing_parent_ids = set(
        CallCenterTicket.objects.filter(
            parent__role=User.ROLE_PARENT
        ).values_list("parent_id", flat=True)
    )

    new_tickets = []

    for parent in parents:
        if parent.id not in existing_parent_ids:
            new_tickets.append(
                CallCenterTicket(
                    parent=parent,
                    title="Foydalanuvchi nazorati",
                    status=CallCenterTicket.STATUS_NEW,
                )
            )

    if new_tickets:
        CallCenterTicket.objects.bulk_create(new_tickets)


def call_center_dashboard_view(request):
    if not is_call_center_user(request.user):
        messages.error(request, "Call Center dashboard uchun ruxsat yo‘q.")
        return redirect("/admin/")

    ensure_parent_tickets()

    search = request.GET.get("q", "").strip()
    selected_ticket_id = request.GET.get("ticket_id")
    status_filter = request.GET.get("status")

    tickets = CallCenterTicket.objects.filter(
        parent__role=User.ROLE_PARENT
    ).select_related(
        "parent",
        "operator",
    ).prefetch_related(
        "comments",
        "parent__children_links",
    )

    if search:
        tickets = tickets.filter(
            Q(parent__phone__icontains=search)
            | Q(parent__full_name__icontains=search)
            | Q(parent__username__icontains=search)
        )

    if status_filter:
        tickets = tickets.filter(status=status_filter)

    tickets = tickets.order_by("-updated_at")

    selected_ticket = None

    if selected_ticket_id:
        selected_ticket = tickets.filter(id=selected_ticket_id).first()

    if not selected_ticket:
        selected_ticket = tickets.first()

    stats = {
        "total_parents": User.objects.filter(role=User.ROLE_PARENT).count(),
        "children_connected": User.objects.filter(
            role=User.ROLE_CHILD,
            child_status=User.CHILD_STATUS_ACTIVE,
        ).count(),
        "premium_users": User.objects.filter(
            role=User.ROLE_PARENT,
            is_premium=True,
        ).count(),
        "blocked_users": User.objects.filter(
            role=User.ROLE_PARENT,
            is_active=False,
        ).count(),
        "new_tickets": CallCenterTicket.objects.filter(status=CallCenterTicket.STATUS_NEW).count(),
        "in_progress_tickets": CallCenterTicket.objects.filter(status=CallCenterTicket.STATUS_IN_PROGRESS).count(),
        "waiting_tickets": CallCenterTicket.objects.filter(status=CallCenterTicket.STATUS_WAITING).count(),
        "resolved_tickets": CallCenterTicket.objects.filter(status=CallCenterTicket.STATUS_RESOLVED).count(),
        "closed_tickets": CallCenterTicket.objects.filter(status=CallCenterTicket.STATUS_CLOSED).count(),
        "blocked_tickets": CallCenterTicket.objects.filter(status=CallCenterTicket.STATUS_BLOCKED).count(),
    }

    columns = [
        {
            "key": CallCenterTicket.STATUS_NEW,
            "label": "Yangi",
            "tickets": tickets.filter(status=CallCenterTicket.STATUS_NEW)[:100],
        },
        {
            "key": CallCenterTicket.STATUS_IN_PROGRESS,
            "label": "Jarayonda",
            "tickets": tickets.filter(status=CallCenterTicket.STATUS_IN_PROGRESS)[:100],
        },
        {
            "key": CallCenterTicket.STATUS_WAITING,
            "label": "Kutilmoqda",
            "tickets": tickets.filter(status=CallCenterTicket.STATUS_WAITING)[:100],
        },
        {
            "key": CallCenterTicket.STATUS_RESOLVED,
            "label": "Hal qilingan",
            "tickets": tickets.filter(status=CallCenterTicket.STATUS_RESOLVED)[:100],
        },
        {
            "key": CallCenterTicket.STATUS_CLOSED,
            "label": "Yopilgan",
            "tickets": tickets.filter(status=CallCenterTicket.STATUS_CLOSED)[:100],
        },
        {
            "key": CallCenterTicket.STATUS_BLOCKED,
            "label": "Bloklangan",
            "tickets": tickets.filter(status=CallCenterTicket.STATUS_BLOCKED)[:100],
        },
    ]

    context = {
        **admin.site.each_context(request),
        "title": "Call Center",
        "stats": stats,
        "columns": columns,
        "selected_ticket": selected_ticket,
        "statuses": CallCenterTicket.STATUS_CHOICES,
        "search": search,
        "status_filter": status_filter,
    }

    return render(request, "admin/call_center_dashboard.html", context)


@require_POST
def call_center_update_status_view(request):
    if not is_call_center_user(request.user):
        return JsonResponse(
            {
                "status": False,
                "detail": "Ruxsat yo‘q.",
            },
            status=403,
        )

    ticket_id = request.POST.get("ticket_id")
    new_status = request.POST.get("new_status")
    comment = request.POST.get("comment", "").strip()

    ticket = CallCenterTicket.objects.filter(
        id=ticket_id
    ).select_related(
        "parent"
    ).first()

    if not ticket:
        return JsonResponse(
            {
                "status": False,
                "detail": "Ticket topilmadi.",
            },
            status=404,
        )

    allowed_statuses = [
        item[0]
        for item in CallCenterTicket.STATUS_CHOICES
    ]

    if new_status not in allowed_statuses:
        return JsonResponse(
            {
                "status": False,
                "detail": "Status noto‘g‘ri.",
            },
            status=400,
        )

    old_status = ticket.status

    ticket.status = new_status
    ticket.operator = request.user
    ticket.last_contact_at = timezone.now()

    if new_status in [
        CallCenterTicket.STATUS_RESOLVED,
        CallCenterTicket.STATUS_CLOSED,
    ]:
        ticket.closed_at = timezone.now()

    if new_status == CallCenterTicket.STATUS_BLOCKED:
        ticket.parent.is_active = False
        ticket.parent.save(update_fields=["is_active"])

    ticket.save(
        update_fields=[
            "status",
            "operator",
            "last_contact_at",
            "closed_at",
            "updated_at",
        ]
    )

    CallCenterComment.objects.create(
        ticket=ticket,
        operator=request.user,
        comment=comment or f"Status {old_status} dan {new_status} ga o‘zgartirildi.",
        old_status=old_status,
        new_status=new_status,
    )

    return JsonResponse(
        {
            "status": True,
            "detail": "Status o‘zgartirildi.",
            "ticket_id": ticket.id,
            "old_status": old_status,
            "new_status": new_status,
        }
    )


@require_POST
def call_center_add_comment_view(request):
    if not is_call_center_user(request.user):
        return JsonResponse(
            {
                "status": False,
                "detail": "Ruxsat yo‘q.",
            },
            status=403,
        )

    ticket_id = request.POST.get("ticket_id")
    comment = request.POST.get("comment", "").strip()

    if not comment:
        return JsonResponse(
            {
                "status": False,
                "detail": "Izoh bo‘sh bo‘lmasligi kerak.",
            },
            status=400,
        )

    ticket = CallCenterTicket.objects.filter(id=ticket_id).first()

    if not ticket:
        return JsonResponse(
            {
                "status": False,
                "detail": "Ticket topilmadi.",
            },
            status=404,
        )

    ticket.operator = request.user
    ticket.last_contact_at = timezone.now()
    ticket.save(update_fields=["operator", "last_contact_at", "updated_at"])

    created_comment = CallCenterComment.objects.create(
        ticket=ticket,
        operator=request.user,
        comment=comment,
        old_status=ticket.status,
        new_status=ticket.status,
    )

    return JsonResponse(
        {
            "status": True,
            "detail": "Izoh qo‘shildi.",
            "comment": {
                "id": created_comment.id,
                "comment": created_comment.comment,
                "operator": request.user.full_name or request.user.phone,
                "created_at": created_comment.created_at.strftime("%d.%m.%Y %H:%M"),
            },
        }
    )


@require_POST
def call_center_toggle_block_view(request):
    if not is_call_center_user(request.user):
        return JsonResponse(
            {
                "status": False,
                "detail": "Ruxsat yo‘q.",
            },
            status=403,
        )

    ticket_id = request.POST.get("ticket_id")
    action = request.POST.get("action")
    comment = request.POST.get("comment", "").strip()

    ticket = CallCenterTicket.objects.filter(
        id=ticket_id
    ).select_related(
        "parent"
    ).first()

    if not ticket:
        return JsonResponse(
            {
                "status": False,
                "detail": "Ticket topilmadi.",
            },
            status=404,
        )

    old_status = ticket.status

    if action == "block":
        ticket.parent.is_active = False
        ticket.parent.save(update_fields=["is_active"])
        ticket.status = CallCenterTicket.STATUS_BLOCKED
        new_status = CallCenterTicket.STATUS_BLOCKED
        text = comment or "Foydalanuvchi bloklandi."

    elif action == "unblock":
        ticket.parent.is_active = True
        ticket.parent.save(update_fields=["is_active"])
        ticket.status = CallCenterTicket.STATUS_IN_PROGRESS
        new_status = CallCenterTicket.STATUS_IN_PROGRESS
        text = comment or "Foydalanuvchi blokdan chiqarildi."

    else:
        return JsonResponse(
            {
                "status": False,
                "detail": "Action noto‘g‘ri.",
            },
            status=400,
        )

    ticket.operator = request.user
    ticket.last_contact_at = timezone.now()
    ticket.save(update_fields=["status", "operator", "last_contact_at", "updated_at"])

    CallCenterComment.objects.create(
        ticket=ticket,
        operator=request.user,
        comment=text,
        old_status=old_status,
        new_status=new_status,
    )

    return JsonResponse(
        {
            "status": True,
            "detail": text,
            "ticket_id": ticket.id,
            "new_status": new_status,
            "is_active": ticket.parent.is_active,
        }
    )


_original_admin_get_urls = admin.site.get_urls


def get_call_center_urls():
    urls = _original_admin_get_urls()

    custom_urls = [
        path(
            "call-center/",
            admin.site.admin_view(call_center_dashboard_view),
            name="call-center-dashboard",
        ),
        path(
            "call-center/update-status/",
            admin.site.admin_view(call_center_update_status_view),
            name="call-center-update-status",
        ),
        path(
            "call-center/add-comment/",
            admin.site.admin_view(call_center_add_comment_view),
            name="call-center-add-comment",
        ),
        path(
            "call-center/toggle-block/",
            admin.site.admin_view(call_center_toggle_block_view),
            name="call-center-toggle-block",
        ),
    ]

    return custom_urls + urls


if not getattr(admin.site, "_call_center_urls_patched", False):
    admin.site.get_urls = get_call_center_urls
    admin.site._call_center_urls_patched = True


@admin.register(BlogCategory)
class BlogCategoryAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "is_active",
        "order",
        "created_at",
    )
    list_filter = (
        "is_active",
        "created_at",
    )
    search_fields = (
        "name",
    )
    ordering = ("order", "id")


@admin.register(BlogPost)
class BlogPostAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "title",
        "category",
        "post_type",
        "reading_time_minutes",
        "likes_count",
        "views_count",
        "is_active",
        "is_featured",
        "order",
        "published_at",
        "created_at",
    )
    list_filter = (
        "post_type",
        "category",
        "is_active",
        "is_featured",
        "published_at",
        "created_at",
    )
    search_fields = (
        "title",
        "short_description",
        "content",
    )
    readonly_fields = (
        "likes_count",
        "views_count",
        "created_at",
        "updated_at",
    )
    ordering = (
        "order",
        "-published_at",
        "-created_at",
    )


@admin.register(BlogPostSave)
class BlogPostSaveAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "post",
        "created_at",
    )
    search_fields = (
        "user__phone",
        "user__full_name",
        "post__title",
    )
    list_filter = (
        "created_at",
    )


@admin.register(BlogPostLike)
class BlogPostLikeAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "post",
        "created_at",
    )
    search_fields = (
        "user__phone",
        "user__full_name",
        "post__title",
    )
    list_filter = (
        "created_at",
    )