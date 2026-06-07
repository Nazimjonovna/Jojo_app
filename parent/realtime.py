from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from .models import ParentChild


def _safe_iso(dt):
    return dt.isoformat() if dt else None


def build_location_payload(child, location, route_statuses=None):
    if route_statuses is None:
        route_statuses = []

    return {
        "t": "child_location",
        "child_id": child.id,
        "child": {
            "id": child.id,
            "name": child.full_name or child.first_name or "",
            "role": child.role,
        },
        "loc": {
            "id": location.id,
            "lat": float(location.latitude),
            "lng": float(location.longitude),
            "acc": location.accuracy,
            "alt": location.altitude,
            "spd": location.speed,
            "hdg": location.heading,
            "bat": location.battery_level,
            "chg": location.is_charging,
            "sig": location.signal_strength,
            "net": location.network_type,
            "prv": location.provider,
            "act": location.activity_type,
            "mck": location.is_mock_location,
            "ts": _safe_iso(location.captured_at) or _safe_iso(location.created_at),
            "created_at": _safe_iso(location.created_at),
        },
        "route_statuses": route_statuses,
    }


def _parent_ids_for(child):
    return list(
        ParentChild.objects.filter(child=child)
        .values_list("parent_id", flat=True)
    )


def broadcast_child_location(child, location, route_statuses=None):
    channel_layer = get_channel_layer()

    payload = build_location_payload(
        child=child,
        location=location,
        route_statuses=route_statuses,
    )

    for parent_id in _parent_ids_for(child):
        async_to_sync(channel_layer.group_send)(
            f"parent_{parent_id}",
            {"type": "child.location", "payload": payload},
        )

    return payload


def broadcast_route_alert(parent_id, payload):
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"parent_{parent_id}",
        {"type": "route.alert", "payload": payload},
    )


def broadcast_saved_location_event(child, event):
    channel_layer = get_channel_layer()
    payload = {
        "t": "saved_location_event",
        "child_id": child.id,
        "event": {
            "id": event.id,
            "event_type": event.event_type,
            "title": event.title,
            "body": event.body,
            "saved_location_id": event.saved_location_id,
            "lat": float(event.latitude),
            "lng": float(event.longitude),
            "created_at": event.created_at.isoformat(),
        },
    }
    for parent_id in _parent_ids_for(child):
        async_to_sync(channel_layer.group_send)(
            f"parent_{parent_id}",
            {"type": "saved.location.event", "payload": payload},
        )


def broadcast_parent_notification(parent_id, notification):
    """Yangi inbox yozuvi haqida real-time xabar — UI darhol ro'yxatga
    qo'shadi va `unreadCount` oshadi."""
    channel_layer = get_channel_layer()
    payload = {
        "t": "notification_created",
        "notification": {
            "id": notification.id,
            "category": notification.category,
            "title": notification.title,
            "body": notification.body,
            "data": notification.data or {},
            "is_read": notification.is_read,
            "child_id": notification.child_id,
            "created_at": notification.created_at.isoformat(),
        },
    }
    async_to_sync(channel_layer.group_send)(
        f"parent_{parent_id}",
        {"type": "parent.notification", "payload": payload},
    )


def broadcast_child_app_policy(child_id, policies):
    """Bola qurilmasidagi WS soketga app policy yangilanishini push qiladi.

    `policies` — `[{"package_name": "...", "is_blocked": bool,
    "daily_limit_seconds": int|null}, ...]` ko'rinishida list.

    Bola tomonida `tracking_service.dart` shu xabarni qabul qilib
    SharedPreferences'ga yozadi va AccessibilityService darrov darrov
    qayta o'qib oladi (PrefsListener). Block buyurtmasi parent tugmasini
    bosishi bilan kuchga kiradi — endi polling kerakmas.
    """
    channel_layer = get_channel_layer()
    payload = {
        "t": "app_policy_update",
        "policies": policies,
    }
    async_to_sync(channel_layer.group_send)(
        f"child_{child_id}",
        {"type": "app.policy.update", "payload": payload},
    )


def broadcast_destination_prediction(parent_id, prediction):
    channel_layer = get_channel_layer()
    payload = {
        "t": "destination_prediction",
        "child_id": prediction.child_id,
        "saved_location": {
            "id": prediction.saved_location_id,
            "name": prediction.saved_location.name,
            "type": prediction.saved_location.location_type,
        },
        "event_type": prediction.event_type,
        "distance_meters": prediction.distance_meters,
        "speed_kmh": prediction.speed_kmh,
        "eta_seconds": prediction.eta_seconds,
        "title": prediction.title,
        "body": prediction.body,
        "created_at": prediction.created_at.isoformat(),
    }
    async_to_sync(channel_layer.group_send)(
        f"parent_{parent_id}",
        {"type": "destination.prediction", "payload": payload},
    )
