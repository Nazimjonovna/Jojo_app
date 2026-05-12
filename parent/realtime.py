from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from .models import ParentChild


def build_location_payload(child, location, route_statuses=None):
    if route_statuses is None:
        route_statuses = []

    return {
        "type": "child_location_updated",
        "child": {
            "id": child.id,
            "name": child.first_name,
            "role": child.role,
        },
        "location": {
            "latitude": float(location.latitude),
            "longitude": float(location.longitude),
            "accuracy": location.accuracy,
            "battery_level": location.battery_level,
            "speed": location.speed,
            "heading": location.heading,
            "created_at": location.created_at.isoformat(),
        },
        "route_statuses": route_statuses,
    }


def broadcast_child_location(child, location, route_statuses=None):
    channel_layer = get_channel_layer()

    parent_ids = ParentChild.objects.filter(
        child=child
    ).values_list("parent_id", flat=True)

    payload = build_location_payload(
        child=child,
        location=location,
        route_statuses=route_statuses,
    )

    for parent_id in parent_ids:
        async_to_sync(channel_layer.group_send)(
            f"parent_{parent_id}",
            {
                "type": "child.location",
                "payload": payload,
            }
        )

    return payload


def broadcast_route_alert(parent_id, payload):
    channel_layer = get_channel_layer()

    async_to_sync(channel_layer.group_send)(
        f"parent_{parent_id}",
        {
            "type": "route.alert",
            "payload": payload,
        }
    )