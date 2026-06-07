"""
Socket.IO server — Jojo realtime tracking layer.

Replaces the older Django Channels WebSocket consumers. Bola (kids) va
ota-ona (parent) dasturlari Socket.IO orqali ulanadi. Bolaning ID si
bilan room'ga kiradi (`child_<id>`), uning ota-onalari `parent_<id>`
room'iga. Backend kerakli room'ga emit qiladi.

Path: `/socket.io/` (default).
Auth: JWT — client `auth={'token': '<jwt>'}` qiymatini connect chaqirig'ida
yuboradi. Token noto'g'ri/yo'q bo'lsa connection rad etiladi.

Events (client -> server):
- `presence`            — bola dasturidan har 15s (online ping + battery/
                          ringer holatlari).
- `location`            — bola dasturidan GPS yangilanishi.
- `ping`                — sodda keep-alive (`pong` qaytaradi).

Events (server -> client):
- `child.location`      — parent room'ga bolaning yangi joylashuvi.
- `child.presence`      — parent room'ga bolaning online/offline holati.
- `route.alert`         — saqlangan marshrut buzilishi.
- `saved_location_event` — bola saqlangan joyga kirdi/chiqdi.
- `destination_prediction` — taxminiy maqsad ehtimoli.
- `notification_created`  — inbox yozuvi.
- `sos_alert`             — SOS xabari (high priority).
- `app_policy_update`     — bola dasturiga (block/limit yangilash).
"""

from __future__ import annotations

import logging
import os
from typing import Optional

import socketio

logger = logging.getLogger("jojo.sio")


# Redis manager — bir nechta worker bo'lsa ham xabarlar yo'qolmaydi.
_redis_url = os.getenv("REDIS_URL", "redis://redis:6379/1")
mgr = socketio.AsyncRedisManager(_redis_url)

sio = socketio.AsyncServer(
    async_mode="asgi",
    client_manager=mgr,
    cors_allowed_origins="*",
    # ASGI lifespan bilan to'qnashmasin uchun
    ping_interval=20,
    ping_timeout=30,
    logger=False,
    engineio_logger=False,
)

# Sync Django view'lardan emit qilish uchun alohida write-only RedisManager.
# AsyncRedisManager'ni sync kontekstdan async_to_sync orqali chaqirish
# event loop ma'noda noto'g'ri ishlaydi (publish dispatch'i kechikadi yoki
# umuman bormaydi). python-socketio docs aniq tavsiya etadi: tashqi
# protsessdan emit qilish uchun `write_only=True` RedisManager ochish.
external_sio = socketio.RedisManager(_redis_url, write_only=True)


# ---------------------------------------------------------------------------
# Auth — JWT'ni `auth={'token': ...}` orqali qabul qilamiz. URL `?token=` ham
# qo'llab-quvvatlanadi (yoki HTTP Authorization headeri).
# ---------------------------------------------------------------------------

def _extract_token(auth, environ) -> Optional[str]:
    """Token uchta joydan kelishi mumkin:
       1. `auth={'token': '...'}` (yangi klientlar)
       2. URL query string `?token=...` (eski format / fallback)
       3. `Authorization: Bearer ...` header (REST namuna)
    Birinchi topilganni qaytaramiz."""
    # 1) auth dict — Socket.IO v4 standarti
    if isinstance(auth, dict):
        token = auth.get("token") or auth.get("access")
        if token:
            return str(token)

    if not environ:
        return None

    # 2) Query string (python-socketio ASGI mode WSGI-style environ beradi)
    import urllib.parse as _urlparse
    qs = environ.get("QUERY_STRING", "")
    if qs:
        params = _urlparse.parse_qs(qs)
        if "token" in params and params["token"]:
            return params["token"][0]

    # 3) Authorization header. ASGI scope ichidagi raw headers ham, WSGI-style
    # `HTTP_AUTHORIZATION` ham bo'lishi mumkin.
    raw_auth = environ.get("HTTP_AUTHORIZATION")
    if raw_auth and raw_auth.lower().startswith("bearer "):
        return raw_auth[7:]

    scope = environ.get("asgi.scope") or {}
    for name, value in scope.get("headers", []):
        try:
            key = name.decode("ascii").lower() if isinstance(name, bytes) else str(name).lower()
            val = value.decode("ascii") if isinstance(value, bytes) else str(value)
        except Exception:
            continue
        if key == "authorization" and val.lower().startswith("bearer "):
            return val[7:]

    return None


def _authenticate(token: str):
    """JWT'ni tekshirib `User` obyektini qaytaradi yoki None."""
    if not token:
        return None
    try:
        from rest_framework_simplejwt.authentication import JWTAuthentication
        auth = JWTAuthentication()
        validated = auth.get_validated_token(token)
        user = auth.get_user(validated)
        return user
    except Exception as e:
        logger.debug("sio auth failed: %s", e)
        return None


# ---------------------------------------------------------------------------
# Connection lifecycle
# ---------------------------------------------------------------------------

@sio.event
async def connect(sid, environ, auth=None):
    token = _extract_token(auth, environ)
    # Diagnostika — token yo'q bo'lsa nimaga yo'qligini bilamiz.
    if not token:
        logger.info(
            "sio no-token sid=%s auth=%r qs=%r has_auth_hdr=%s",
            sid,
            type(auth).__name__,
            (environ or {}).get("QUERY_STRING", "")[:80],
            bool((environ or {}).get("HTTP_AUTHORIZATION")),
        )
    user = _authenticate(token) if token else None
    if not user or getattr(user, "is_anonymous", True):
        logger.info("sio reject (no auth) sid=%s", sid)
        # Raising ConnectionRefusedError tells the client why.
        raise socketio.exceptions.ConnectionRefusedError("auth_required")

    role = getattr(user, "role", None)
    if role == "child":
        room = f"child_{user.id}"
    elif role == "parent":
        room = f"parent_{user.id}"
    else:
        logger.info("sio reject (bad role=%s) sid=%s", role, sid)
        raise socketio.exceptions.ConnectionRefusedError("bad_role")

    await sio.enter_room(sid, room)
    await sio.save_session(sid, {"user_id": user.id, "role": role, "room": room})
    logger.info("sio connect sid=%s user=%s role=%s room=%s", sid, user.id, role, room)
    await sio.emit("connected", {"role": role, "user_id": user.id}, to=sid)

    # Bola ulansa, ota-onalarga "online" broadcast.
    if role == "child":
        await _broadcast_child_presence_async(user, {
            "child_id": user.id,
            "online": True,
            "has_gps_fix": False,
            "battery_level": None,
            "is_charging": False,
            "network_type": None,
            "ringer_mode": None,
            "captured_at": None,
        })


def _authenticate_sync(token):
    return _authenticate(token)


@sio.event
async def disconnect(sid):
    session = await sio.get_session(sid)
    if not session:
        return
    role = session.get("role")
    user_id = session.get("user_id")
    logger.info("sio disconnect sid=%s user=%s role=%s", sid, user_id, role)
    if role == "child" and user_id:
        # Ota-onalarga "offline".
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            user = await sio.start_background_task(_get_user, user_id) if False else _get_user(user_id)
            if user:
                await _broadcast_child_presence_async(user, {
                    "child_id": user.id,
                    "online": False,
                    "has_gps_fix": False,
                })
        except Exception:
            pass


def _get_user(user_id):
    try:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        return User.objects.filter(id=user_id).first()
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Bola -> server: presence
# ---------------------------------------------------------------------------

@sio.event
async def presence(sid, data):
    session = await sio.get_session(sid)
    if not session or session.get("role") != "child":
        return
    user_id = session["user_id"]
    user = _get_user(user_id)
    if not user:
        return
    payload = {
        "child_id": user.id,
        "online": True,
        "has_gps_fix": bool(data.get("has_gps_fix")) if isinstance(data, dict) else False,
        "battery_level": (data or {}).get("battery_level") if isinstance(data, dict) else None,
        "is_charging": bool((data or {}).get("is_charging")) if isinstance(data, dict) else False,
        "network_type": (data or {}).get("network_type") if isinstance(data, dict) else None,
        "ringer_mode": (data or {}).get("ringer_mode") if isinstance(data, dict) else None,
        "captured_at": (data or {}).get("captured_at") if isinstance(data, dict) else None,
    }
    await _broadcast_child_presence_async(user, payload)


# ---------------------------------------------------------------------------
# Bola -> server: location
# ---------------------------------------------------------------------------

def _payload_from_message(content):
    """Klient JSON'idan `process_child_location` argumentlariga konvertatsiya."""
    if not isinstance(content, dict):
        content = {}
    return {
        "latitude": content.get("lat", content.get("latitude")),
        "longitude": content.get("lng", content.get("longitude")),
        "accuracy": content.get("acc", content.get("accuracy")),
        "speed": content.get("spd", content.get("speed")),
        "heading": content.get("hdg", content.get("heading")),
        "altitude": content.get("alt", content.get("altitude")),
        "battery_level": content.get("bat", content.get("battery_level")),
        "is_charging": content.get("chg", content.get("is_charging")),
        "signal_strength": content.get("sig", content.get("signal_strength")),
        "network_type": content.get("net", content.get("network_type")),
        "activity_type": content.get("act", content.get("activity_type")),
        "captured_at": content.get("ts", content.get("captured_at")),
        "provider": content.get("prv", content.get("provider")),
        "is_mock_location": content.get("mck", content.get("is_mock_location")),
    }


async def _handle_location(sid, data):
    session = await sio.get_session(sid)
    if not session or session.get("role") != "child":
        return
    user_id = session["user_id"]
    payload = _payload_from_message(data)
    if payload["latitude"] is None or payload["longitude"] is None:
        return
    try:
        await sio.start_background_task(_save_and_broadcast_location, user_id, payload)
    except Exception as e:
        logger.warning("sio location save failed: %s", e)


@sio.event
async def location(sid, data):
    await _handle_location(sid, data)


# Eski klient `'loc'` event nomi bilan yuborardi — bir xil handler.
@sio.on("loc")
async def _location_alias(sid, data):
    await _handle_location(sid, data)


def _save_and_broadcast_location(user_id, payload):
    """Sync funksiya — DB yozuvi + broadcastni shu yerda qilamiz.
    Background task ichida sync chaqiriqlar xavfsiz."""
    from parent.models import ChildLocation
    user = _get_user(user_id)
    if not user:
        return
    try:
        from parent.services import process_child_location
        process_child_location(
            child=user,
            source=ChildLocation.SOURCE_WEBSOCKET,
            **payload,
        )
    except Exception as e:
        logger.warning("process_child_location failed: %s", e)


# ---------------------------------------------------------------------------
# Simple ping
# ---------------------------------------------------------------------------

@sio.event
async def ping(sid, data=None):
    await sio.emit("pong", {"ts": (data or {}).get("ts") if isinstance(data, dict) else None}, to=sid)


# ---------------------------------------------------------------------------
# Server -> client: helpers (used by parent.realtime)
# ---------------------------------------------------------------------------

async def _broadcast_child_presence_async(child, payload):
    from parent.models import ParentChild
    parent_ids = list(
        ParentChild.objects.filter(child=child).values_list("parent_id", flat=True)
    )
    # Klient eski WS protokoldagi 't=presence' bilan moslashishi uchun
    # event nomi `presence`.
    for parent_id in parent_ids:
        await sio.emit("presence", payload, room=f"parent_{parent_id}")


def emit_to_room_sync(event: str, payload: dict, room: str):
    """Sync entry-point — Django view'lar yoki services.py shu yerdan
    chaqiradi. Tashqi `RedisManager`'ga emit qiladi — u Redis pub/sub
    orqali AsyncServer'ga yetadi va ulangan klientlarga yuboriladi."""
    try:
        external_sio.emit(event, payload, room=room)
    except Exception as e:
        logger.warning("emit_to_room_sync(%s, %s) failed: %s", event, room, e)
