"""Real-time location tracking consumers.

Protokol (JSON, qisqartirilgan kalit nomlari tezlik uchun):

Child -> Server  (kanal: `ws/child/location/`)
    {
        "t": "loc",               # type: location update
        "lat": 41.31, "lng": 69.27,
        "ts": "2026-06-07T08:00:00Z",   # captured_at (ISO 8601)
        "acc": 8.4,               # accuracy m
        "alt": 412.0,             # altitude m
        "spd": 1.2,               # speed m/s
        "hdg": 92.0,              # heading deg
        "bat": 78,                # battery %
        "chg": false,             # is_charging
        "sig": 3,                 # signal strength 0..4
        "net": "wifi",            # wifi/cellular/none
        "prv": "fused",           # provider gps/fused/network
        "mck": false,             # is_mock
        "act": "walking"          # activity_type
    }

    {"t": "batch", "items": [<loc>, <loc>, ...]}   # ofline buffer drenaji
    {"t": "ping"}                                  # heartbeat

Server -> Child
    {"t": "ack", "id": <loc_id>}
    {"t": "pong"}
    {"t": "error", "msg": "..."}

Server -> Parent  (kanal: `ws/parent/tracking/`)
    {"t": "child_location", "child_id": 12, "loc": <full payload>, "route_statuses": [...]}
    {"t": "saved_location_event", "child_id": 12, "event": {...}}
    {"t": "destination_prediction", "child_id": 12, "saved_location": {...}, ...}
    {"t": "route_alert", "payload": {...}}
    {"t": "pong"}

Parent -> Server
    {"t": "ping"}
    {"t": "subscribe", "child_ids": [12, 14]}  # bo'lib turish (kelajakda)
"""

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from .models import User, ChildLocation
from .services import process_child_location


def _payload_from_message(content):
    """Klient JSON'idan `process_child_location` argumentlariga konvertatsiya."""
    return {
        "latitude": content.get("lat", content.get("latitude")),
        "longitude": content.get("lng", content.get("longitude")),
        "accuracy": content.get("acc", content.get("accuracy")),
        "altitude": content.get("alt", content.get("altitude")),
        "altitude_accuracy": content.get("alt_acc", content.get("altitude_accuracy")),
        "battery_level": content.get("bat", content.get("battery_level")),
        "is_charging": content.get("chg", content.get("is_charging")),
        "speed": content.get("spd", content.get("speed")),
        "speed_accuracy": content.get("spd_acc", content.get("speed_accuracy")),
        "heading": content.get("hdg", content.get("heading")),
        "signal_strength": content.get("sig", content.get("signal_strength")),
        "network_type": content.get("net", content.get("network_type")),
        "provider": content.get("prv", content.get("provider")),
        "is_mock_location": content.get("mck", content.get("is_mock_location")),
        "activity_type": content.get("act", content.get("activity_type")),
        "captured_at": content.get("ts", content.get("captured_at")),
    }


class ParentTrackingConsumer(AsyncJsonWebsocketConsumer):
    """Ota-ona endpointi — barcha farzandlar real-time eventlari."""

    async def connect(self):
        user = self.scope.get("user")

        if not user or user.is_anonymous:
            await self.close(code=4001)
            return

        if user.role != User.ROLE_PARENT:
            await self.close(code=4003)
            return

        self.parent_group_name = f"parent_{user.id}"

        await self.channel_layer.group_add(
            self.parent_group_name,
            self.channel_name,
        )

        await self.accept()

        await self.send_json(
            {
                "t": "connected",
                "group": self.parent_group_name,
            }
        )

    async def disconnect(self, close_code):
        if hasattr(self, "parent_group_name"):
            await self.channel_layer.group_discard(
                self.parent_group_name,
                self.channel_name,
            )

    async def receive_json(self, content, **kwargs):
        action = content.get("t") or content.get("action")
        if action == "ping":
            await self.send_json({"t": "pong"})

    # ---- group event handlers (channel layer type -> method) ----

    async def child_location(self, event):
        await self.send_json(event["payload"])

    async def child_presence(self, event):
        # `payload`ni "t" bilan o'rab parent dasturiga yuboramiz.
        payload = dict(event.get("payload") or {})
        payload["t"] = "presence"
        await self.send_json(payload)

    async def route_alert(self, event):
        await self.send_json(event["payload"])

    async def saved_location_event(self, event):
        await self.send_json(event["payload"])

    async def destination_prediction(self, event):
        await self.send_json(event["payload"])

    async def parent_notification(self, event):
        await self.send_json(event["payload"])


class ChildLocationConsumer(AsyncJsonWebsocketConsumer):
    """Bola qurilmasi yuboradigan endpoint — high-frequency location updates."""

    async def connect(self):
        user = self.scope.get("user")

        if not user or user.is_anonymous:
            await self.close(code=4001)
            return

        if user.role != User.ROLE_CHILD:
            await self.close(code=4003)
            return

        # Push channeli — server tomondan policy update yuborish uchun.
        self.child_group_name = f"child_{user.id}"
        await self.channel_layer.group_add(
            self.child_group_name,
            self.channel_name,
        )

        await self.accept()

        await self.send_json({"t": "connected"})

        # Bola dasturga kirgani zahoti parent'ga "online" broadcast.
        # Bu hali birinchi GPS fix kelmagunga qadar ham parent dasturda
        # "Online" ko'rinishini ta'minlaydi.
        await self._broadcast_presence({
            "child_id": user.id,
            "online": True,
            "has_gps_fix": False,
            "battery_level": None,
            "is_charging": False,
            "network_type": None,
            "captured_at": None,
        })

    async def receive_json(self, content, **kwargs):
        msg_type = content.get("t") or content.get("action")

        if msg_type == "ping":
            await self.send_json({"t": "pong"})
            return

        if msg_type == "presence":
            await self._handle_presence(content)
            return

        if msg_type in ("loc", "location.update"):
            await self._handle_single(content)
            return

        if msg_type == "batch":
            items = content.get("items") or []
            for item in items:
                if isinstance(item, dict):
                    await self._handle_single(item, silent=True)
            await self.send_json({"t": "batch_ack", "count": len(items)})
            return

        await self.send_json(
            {
                "t": "error",
                "msg": f"Unknown action: {msg_type}",
            }
        )

    async def _handle_presence(self, content):
        """GPS hali kelmagan paytda yoki tinch turgan paytda bola dasturi
        15s da bir yuboradigan presence ping. Backend hech narsani
        saqlamaydi — faqat parent'larga 'child online' broadcast qiladi.
        Shu orqali parent dasturi WS uzilmasdan bolaning real online
        statusini bilib turadi."""
        child = self.scope["user"]
        payload = {
            "child_id": child.id,
            "online": True,
            "has_gps_fix": bool(content.get("has_gps_fix")),
            "battery_level": content.get("battery_level"),
            "is_charging": bool(content.get("is_charging")),
            "network_type": content.get("network_type"),
            "captured_at": content.get("captured_at"),
        }
        await self._broadcast_presence(payload)

    @database_sync_to_async
    def _broadcast_presence(self, payload):
        from .realtime import broadcast_child_presence

        broadcast_child_presence(self.scope["user"], payload)

    async def _handle_single(self, content, *, silent=False):
        payload = _payload_from_message(content)
        if payload["latitude"] is None or payload["longitude"] is None:
            if not silent:
                await self.send_json(
                    {"t": "error", "msg": "lat/lng required"}
                )
            return

        try:
            saved_payload = await self._save(payload)
        except Exception as error:
            if not silent:
                await self.send_json(
                    {"t": "error", "msg": "save_failed", "detail": str(error)}
                )
            return

        if not silent:
            await self.send_json(
                {"t": "ack", "id": saved_payload.get("location", {}).get("id")}
            )

    @database_sync_to_async
    def _save(self, payload):
        child = self.scope["user"]
        location, broadcast_payload = process_child_location(
            child=child,
            source=ChildLocation.SOURCE_WEBSOCKET,
            **payload,
        )
        return broadcast_payload

    async def disconnect(self, close_code):
        if hasattr(self, "child_group_name"):
            await self.channel_layer.group_discard(
                self.child_group_name,
                self.channel_name,
            )
        # Bola uzilganda parent'larga "offline" broadcast.
        user = self.scope.get("user")
        if user and not user.is_anonymous and user.role == User.ROLE_CHILD:
            try:
                await self._broadcast_presence({
                    "child_id": user.id,
                    "online": False,
                    "has_gps_fix": False,
                    "battery_level": None,
                    "is_charging": False,
                    "network_type": None,
                    "captured_at": None,
                })
            except Exception:
                pass

    # === Group event handlers ===

    async def app_policy_update(self, event):
        """`broadcast_child_app_policy` chaqirig'idan keladigan payload."""
        await self.send_json(event["payload"])
