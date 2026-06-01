from datetime import timedelta

from django.utils import timezone

from .firebase import send_fcm_multicast
from .models import (
    ChildLocation,
    ChildLastLocation,
    ChildRouteAssignment,
    RouteAlert,
    DeviceToken,
)
from .realtime import broadcast_child_location, broadcast_route_alert
from .utils import nearest_route_point_distance


def to_float(value):
    if value is None:
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def to_int(value):
    if value is None:
        return None

    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def speed_to_kmh(speed):
   
    speed_float = to_float(speed)

    if speed_float is None:
        return None

    return round(speed_float * 3.6, 2)


def build_location_payload(location):
    return {
        "id": location.id,
        "latitude": float(location.latitude),
        "longitude": float(location.longitude),
        "accuracy": location.accuracy,
        "battery_level": location.battery_level,
        "speed": location.speed,
        "speed_kmh": speed_to_kmh(location.speed),
        "heading": location.heading,
        "source": location.source,
        "created_at": location.created_at.isoformat(),
    }


def send_route_deviation_notification(assignment, location, distance_meters):
    parent = assignment.parent
    child = assignment.child

    tokens = DeviceToken.objects.filter(
        user=parent,
        is_active=True
    ).values_list("token", flat=True)

    tokens = list(tokens)

    title = "Jojo"
    child_name = child.full_name or child.first_name or "Farzandingiz"
    body = f"{child_name} belgilangan marshrutdan chiqdi."

    payload = {
        "type": "route_deviation",
        "child_id": child.id,
        "child_name": child_name,
        "route_id": assignment.route.id,
        "route_name": assignment.route.name,
        "distance_meters": round(distance_meters, 2),
        "latitude": float(location.latitude),
        "longitude": float(location.longitude),
        "speed": location.speed,
        "speed_kmh": speed_to_kmh(location.speed),
        "heading": location.heading,
        "created_at": location.created_at.isoformat(),
    }

    if tokens:
        try:
            send_fcm_multicast(
                tokens=tokens,
                title=title,
                body=body,
                data=payload,
            )
        except Exception:
            pass

    broadcast_route_alert(
        parent_id=parent.id,
        payload={
            "type": "route_deviation",
            "title": title,
            "body": body,
            "data": payload,
        }
    )


def should_create_alert(assignment):
    last_alert = RouteAlert.objects.filter(
        assignment=assignment,
        alert_type=RouteAlert.ALERT_OFF_ROUTE
    ).order_by("-created_at").first()

    if not last_alert:
        return True

    return timezone.now() - last_alert.created_at > timedelta(minutes=10)


def get_route_statuses_for_child(child, latitude, longitude, location):
    assignments = ChildRouteAssignment.objects.filter(
        child=child,
        status=ChildRouteAssignment.STATUS_ACTIVE,
        route__is_active=True,
    ).select_related("route", "parent").prefetch_related("route__points")

    statuses = []

    for assignment in assignments:
        points = list(assignment.route.points.all())

        if not points:
            continue

        distance_meters, nearest_point = nearest_route_point_distance(
            latitude=latitude,
            longitude=longitude,
            route_points=points,
        )

        is_off_route = distance_meters > assignment.allowed_radius_meters

        status_data = {
            "assignment_id": assignment.id,
            "route_id": assignment.route.id,
            "route_name": assignment.route.name,
            "allowed_radius_meters": assignment.allowed_radius_meters,
            "distance_meters": round(distance_meters, 2),
            "is_off_route": is_off_route,
            "nearest_point": {
                "id": nearest_point.id,
                "order": nearest_point.order,
                "latitude": float(nearest_point.latitude),
                "longitude": float(nearest_point.longitude),
            } if nearest_point else None,
        }

        statuses.append(status_data)

        if (
            is_off_route
            and assignment.notify_on_deviation
            and should_create_alert(assignment)
        ):
            RouteAlert.objects.create(
                assignment=assignment,
                child=child,
                alert_type=RouteAlert.ALERT_OFF_ROUTE,
                distance_meters=distance_meters,
                location=location,
            )

            send_route_deviation_notification(
                assignment=assignment,
                location=location,
                distance_meters=distance_meters,
            )

    return statuses


def process_child_location(
    child,
    latitude,
    longitude,
    accuracy=None,
    battery_level=None,
    speed=None,
    heading=None,
    source=ChildLocation.SOURCE_REST,
):
   

    latitude = to_float(latitude)
    longitude = to_float(longitude)
    accuracy = to_float(accuracy)
    battery_level = to_int(battery_level)
    speed = to_float(speed)
    heading = to_float(heading)

    location = ChildLocation.objects.create(
        child=child,
        latitude=latitude,
        longitude=longitude,
        accuracy=accuracy,
        battery_level=battery_level,
        speed=speed,
        heading=heading,
        source=source,
    )

    ChildLastLocation.objects.update_or_create(
        child=child,
        defaults={
            "latitude": latitude,
            "longitude": longitude,
            "accuracy": accuracy,
            "battery_level": battery_level,
            "speed": speed,
            "heading": heading,
        }
    )

    route_statuses = get_route_statuses_for_child(
        child=child,
        latitude=latitude,
        longitude=longitude,
        location=location,
    )

    payload = broadcast_child_location(
        child=child,
        location=location,
        route_statuses=route_statuses,
    )

    if isinstance(payload, dict):
        payload["location"] = build_location_payload(location)
        payload["route_statuses"] = route_statuses

        payload["child"] = {
            "id": child.id,
            "phone": child.phone,
            "username": child.username,
            "full_name": child.full_name,
            "first_name": child.first_name,
            "role": child.role,
        }

    return location, payload