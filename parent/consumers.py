from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from .models import User, ChildLocation
from .services import process_child_location


class ParentTrackingConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        user = self.scope["user"]

        if user.is_anonymous or user.role != User.ROLE_PARENT:
            await self.close()
            return

        self.parent_group_name = f"parent_{user.id}"

        await self.channel_layer.group_add(
            self.parent_group_name,
            self.channel_name,
        )

        await self.accept()

        await self.send_json(
            {
                "type": "connected",
                "message": "Parent real-time tracking connected.",
            }
        )

    async def disconnect(self, close_code):
        if hasattr(self, "parent_group_name"):
            await self.channel_layer.group_discard(
                self.parent_group_name,
                self.channel_name,
            )

    async def child_location(self, event):
        await self.send_json(event["payload"])

    async def route_alert(self, event):
        await self.send_json(event["payload"])


class ChildLocationConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        user = self.scope["user"]

        if user.is_anonymous or user.role != User.ROLE_CHILD:
            await self.close()
            return

        await self.accept()

        await self.send_json(
            {
                "type": "connected",
                "message": "Child location websocket connected.",
            }
        )

    async def receive_json(self, content, **kwargs):
        action = content.get("action")

        if action != "location.update":
            await self.send_json(
                {
                    "type": "error",
                    "message": "Invalid action.",
                }
            )
            return

        latitude = content.get("latitude")
        longitude = content.get("longitude")

        if latitude is None or longitude is None:
            await self.send_json(
                {
                    "type": "error",
                    "message": "latitude and longitude are required.",
                }
            )
            return

        payload = await self.save_location(content)

        await self.send_json(
            {
                "type": "location_saved",
                "payload": payload,
            }
        )

    @database_sync_to_async
    def save_location(self, content):
        child = self.scope["user"]

        location, payload = process_child_location(
            child=child,
            latitude=content.get("latitude"),
            longitude=content.get("longitude"),
            accuracy=content.get("accuracy"),
            battery_level=content.get("battery_level"),
            speed=content.get("speed"),
            heading=content.get("heading"),
            source=ChildLocation.SOURCE_WEBSOCKET,
        )

        return payload