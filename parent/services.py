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


def send_route_deviation_notification(assignment, location, distance_meters):
    parent = assignment.parent
    child = assignment.child

    tokens = DeviceToken.objects.filter(
        user=parent,
        is_active=True
    ).values_list("token", flat=True)

    tokens = list(tokens)

    title = "Jojo"
    body = f"{child.first_name} belgilangan marshrutdan chiqdi."

    payload = {
        "type": "route_deviation",
        "child_id": child.id,
        "child_name": child.first_name,
        "route_id": assignment.route.id,
        "route_name": assignment.route.name,
        "distance_meters": round(distance_meters, 2),
        "latitude": float(location.latitude),
        "longitude": float(location.longitude),
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
    ).select_related("route", "parent")

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

    return location, payload