"""Bitta manba — Free vs Premium tarif chegaralari.

Bu yerda barcha gate konstantalari va endpoint helpers turadi. Server ham,
client (parent ilova) ham `feature-gates/` endpoint'idan o'qib oladi —
shunda UI lock badge'lari, paywall'lar va backend cheklovlari mos keladi.
"""

from rest_framework.exceptions import PermissionDenied

# Free tarifda ruxsat etilgan chegaralar
FREE_CHILD_LIMIT = 1
FREE_SAVED_LOCATIONS_LIMIT = 1
FREE_LOCATION_HISTORY_HOURS = 24  # faqat oxirgi 24 soat
FREE_AREA_BLOCK_RULES_LIMIT = 0  # hudud bloklash umuman yopiq


def is_premium(user):
    return bool(user and user.is_authenticated and user.has_active_premium())


def gates_for(user):
    """Client-side render uchun gate kartasi."""
    premium = is_premium(user)
    return {
        "is_premium": premium,
        "limits": {
            "children": None if premium else FREE_CHILD_LIMIT,
            "saved_locations": None if premium else FREE_SAVED_LOCATIONS_LIMIT,
            "location_history_hours": None if premium else FREE_LOCATION_HISTORY_HOURS,
            "area_block_rules": None if premium else FREE_AREA_BLOCK_RULES_LIMIT,
        },
        "features": {
            # True = ruxsat. False = bloklangan (UI lock badge ko'rsatadi).
            "location_basic": True,
            "advice": True,
            "stem_toys": True,
            "add_child": True,  # birinchi bola hamisha ruxsat
            "add_extra_child": premium,
            "location_history_full": premium,
            "location_deep_search": premium,
            "app_blocks_write": premium,
            "app_limits_write": premium,
            "saved_locations_extra": premium,
            "area_block_rules": premium,
        },
    }


def require_premium(user, feature_key="premium"):
    """View ichidan chaqirish uchun (permission class o'rniga inline gate)."""
    if not is_premium(user):
        raise PermissionDenied({
            "code": "premium_required",
            "feature": feature_key,
            "detail": "Bu funksiya faqat Premium foydalanuvchilar uchun.",
        })


def can_add_more_children(user):
    from .models import ParentChild  # circular import
    if is_premium(user):
        return True
    count = ParentChild.objects.filter(parent=user).count()
    return count < FREE_CHILD_LIMIT


def can_add_more_saved_locations(user):
    from .models import SavedLocation
    if is_premium(user):
        return True
    count = SavedLocation.objects.filter(parent=user).count()
    return count < FREE_SAVED_LOCATIONS_LIMIT
