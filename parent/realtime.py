"""
Real-time broadcasts — emits over Socket.IO.

Migrated from Django Channels group_send to socket.io rooms. Each helper
emits a single named event to the relevant `parent_<id>` or `child_<id>`
room. Clients subscribe via `core/socketio_server.py`.

Channel-layer (group_send) call sites are kept as a no-op fallback in
case anyone is still on the old WS code path; once kids/parent apps are
fully migrated, those layers can be deleted entirely.
"""

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


# ---------------------------------------------------------------------------
# Socket.IO emit helper — single entry-point. Old code path (Channels
# group_send) is kept as a best-effort dual-write so legacy WS clients
# still get the message during migration.
# ---------------------------------------------------------------------------

def _emit(event: str, payload: dict, room: str, *, legacy_type: str = None):
    """Emit `event` to `room` over Socket.IO. Also tries the old Channels
    group_send so any still-connected WebSocket consumer continues to
    receive it. Both paths are wrapped in try/except — a single failure
    must never break the caller (Django views/services)."""
    try:
        from core.socketio_server import emit_to_room_sync
        emit_to_room_sync(event, payload, room)
    except Exception:
        pass

    if legacy_type:
        try:
            channel_layer = get_channel_layer()
            if channel_layer is not None:
                async_to_sync(channel_layer.group_send)(
                    room,
                    {"type": legacy_type, "payload": payload},
                )
        except Exception:
            pass


def broadcast_sos_alert(parent_id, payload):
    _emit("sos_alert", payload, f"parent_{parent_id}", legacy_type="sos.alert")


def broadcast_child_presence(child, payload):
    # Klient `onAny` orqali event nomini `t` qiymati sifatida ko'radi —
    # eski klient `t == 'presence'` deb tekshiradi, shuning uchun event
    # nomi `presence` (uchburchak yo'q).
    for parent_id in _parent_ids_for(child):
        _emit("presence", payload, f"parent_{parent_id}",
              legacy_type="child.presence")


def broadcast_child_location(child, location, route_statuses=None):
    payload = build_location_payload(
        child=child,
        location=location,
        route_statuses=route_statuses,
    )
    for parent_id in _parent_ids_for(child):
        _emit("child_location", payload, f"parent_{parent_id}",
              legacy_type="child.location")
    return payload


def broadcast_route_alert(parent_id, payload):
    _emit("route_alert", payload, f"parent_{parent_id}",
          legacy_type="route.alert")


def broadcast_saved_location_event(child, event):
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
        _emit("saved_location_event", payload, f"parent_{parent_id}",
              legacy_type="saved.location.event")


def broadcast_parent_notification(parent_id, notification):
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
    _emit("notification_created", payload, f"parent_{parent_id}",
          legacy_type="parent.notification")


def broadcast_child_app_policy(child_id, policies):
    """Bola qurilmasidagi soketga app policy yangilanishini push qiladi."""
    payload = {
        "t": "app_policy_update",
        "policies": policies,
    }
    _emit("app_policy_update", payload, f"child_{child_id}",
          legacy_type="app.policy.update")


def broadcast_destination_prediction(parent_id, prediction):
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
    _emit("destination_prediction", payload, f"parent_{parent_id}",
          legacy_type="destination.prediction")
