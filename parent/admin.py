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


admin.site.register(OTPCode)
admin.site.register(PairingCode)
admin.site.register(ParentChild)
admin.site.register(ChildLocation)
admin.site.register(ChildLastLocation)
admin.site.register(DeviceToken)