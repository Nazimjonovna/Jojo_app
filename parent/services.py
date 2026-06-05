from datetime import timedelta
import math
from django.utils import timezone

from .firebase import send_fcm_multicast
from .models import (
    ChildLocation,
    ChildLastLocation,
    ChildRouteAssignment,
    RouteAlert,
    ParentChild,
    DeviceToken,
    SavedLocation,
    ChildSavedLocationState,
    ChildSavedLocationEvent,
    UserSubscription, SubscriptionPlan,
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
    
    saved_location_events = process_saved_location_events(
    child=child,
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
        payload["saved_location_events"] = [
            {
                "id": event.id,
                "event_type": event.event_type,
                "title": event.title,
                "body": event.body,
                "saved_location_id": event.saved_location_id,
                "created_at": event.created_at.isoformat(),
            }
            for event in saved_location_events
        ]
        payload["child"] = {
            "id": child.id,
            "phone": child.phone,
            "username": child.username,
            "full_name": child.full_name,
            "first_name": child.first_name,
            "role": child.role,
        }

    return location, payload


def calculate_distance_meters(lat1, lon1, lat2, lon2):
    radius = 6371000

    phi1 = math.radians(float(lat1))
    phi2 = math.radians(float(lat2))

    delta_phi = math.radians(float(lat2) - float(lat1))
    delta_lambda = math.radians(float(lon2) - float(lon1))

    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )

    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return radius * c


def get_child_parent(child):
    link = ParentChild.objects.filter(
        child=child
    ).select_related("parent").first()

    if not link:
        return None

    return link.parent


def find_current_saved_location(child, latitude, longitude):
    parent = get_child_parent(child)

    if not parent:
        return None

    saved_locations = SavedLocation.objects.filter(
        parent=parent,
        is_active=True,
    )

    matched_location = None
    matched_distance = None

    for saved_location in saved_locations:
        distance = calculate_distance_meters(
            lat1=latitude,
            lon1=longitude,
            lat2=saved_location.latitude,
            lon2=saved_location.longitude,
        )

        if distance <= saved_location.radius_meters:
            if matched_distance is None or distance < matched_distance:
                matched_location = saved_location
                matched_distance = distance

    return matched_location


def should_send_saved_location_event(state, event_type):
    if not state.last_event_at:
        return True

    if state.last_event_type != event_type:
        return True

    # bir xil eventni 10 minut ichida qayta yubormaymiz
    return timezone.now() - state.last_event_at > timedelta(minutes=10)


def build_saved_location_message(child, event_type, saved_location=None, previous_location=None):
    child_name = child.full_name or child.first_name or "Farzandingiz"

    if event_type == ChildSavedLocationEvent.EVENT_ENTER:
        return (
            "Jojo",
            f"{child_name} {saved_location.name} hududiga kirdi."
        )

    if event_type == ChildSavedLocationEvent.EVENT_EXIT:
        return (
            "Jojo",
            f"{child_name} {previous_location.name} hududidan chiqdi."
        )

    if event_type == ChildSavedLocationEvent.EVENT_MOVING_HOME_TO_SCHOOL:
        return (
            "Jojo",
            f"{child_name} uydan chiqib maktab tomonga ketayapti."
        )

    if event_type == ChildSavedLocationEvent.EVENT_MOVING_SCHOOL_TO_HOME:
        return (
            "Jojo",
            f"{child_name} maktabdan chiqib uy tomonga ketayapti."
        )

    return (
        "Jojo",
        f"{child_name} joylashuvi o‘zgardi."
    )


def send_saved_location_notification(parent, child, event, location):
    tokens = DeviceToken.objects.filter(
        user=parent,
        is_active=True
    ).values_list("token", flat=True)

    tokens = list(tokens)

    payload = {
        "type": "saved_location_event",
        "event_id": event.id,
        "event_type": event.event_type,
        "child_id": child.id,
        "child_name": child.full_name or child.first_name or "",
        "saved_location_id": event.saved_location_id,
        "latitude": float(location.latitude),
        "longitude": float(location.longitude),
        "created_at": event.created_at.isoformat(),
    }

    if tokens:
        try:
            send_fcm_multicast(
                tokens=tokens,
                title=event.title,
                body=event.body,
                data=payload,
            )
        except Exception:
            pass
        
def process_saved_location_events(child, location):
    parent = get_child_parent(child)

    if not parent:
        return []

    current_location = find_current_saved_location(
        child=child,
        latitude=location.latitude,
        longitude=location.longitude,
    )

    state, _ = ChildSavedLocationState.objects.get_or_create(
        child=child
    )

    previous_location = state.current_location

    if previous_location_id_equals(previous_location, current_location):
        return []

    created_events = []

    # Oldingi saved locationdan chiqdi
    if previous_location and not current_location:
        event_type = ChildSavedLocationEvent.EVENT_EXIT

        if should_send_saved_location_event(state, event_type):
            title, body = build_saved_location_message(
                child=child,
                event_type=event_type,
                previous_location=previous_location,
            )

            event = ChildSavedLocationEvent.objects.create(
                child=child,
                parent=parent,
                saved_location=previous_location,
                event_type=event_type,
                title=title,
                body=body,
                latitude=location.latitude,
                longitude=location.longitude,
            )

            send_saved_location_notification(parent, child, event, location)
            created_events.append(event)

    # Yangi saved locationga kirdi
    if current_location and not previous_location:
        event_type = ChildSavedLocationEvent.EVENT_ENTER

        if should_send_saved_location_event(state, event_type):
            title, body = build_saved_location_message(
                child=child,
                event_type=event_type,
                saved_location=current_location,
            )

            event = ChildSavedLocationEvent.objects.create(
                child=child,
                parent=parent,
                saved_location=current_location,
                event_type=event_type,
                title=title,
                body=body,
                latitude=location.latitude,
                longitude=location.longitude,
            )

            send_saved_location_notification(parent, child, event, location)
            created_events.append(event)

    # Home -> School mantiqi
    if previous_location and current_location:
        if (
            previous_location.location_type == SavedLocation.LOCATION_HOME
            and current_location.location_type == SavedLocation.LOCATION_SCHOOL
        ):
            event_type = ChildSavedLocationEvent.EVENT_MOVING_HOME_TO_SCHOOL

            if should_send_saved_location_event(state, event_type):
                title, body = build_saved_location_message(
                    child=child,
                    event_type=event_type,
                    saved_location=current_location,
                    previous_location=previous_location,
                )

                event = ChildSavedLocationEvent.objects.create(
                    child=child,
                    parent=parent,
                    saved_location=current_location,
                    event_type=event_type,
                    title=title,
                    body=body,
                    latitude=location.latitude,
                    longitude=location.longitude,
                )

                send_saved_location_notification(parent, child, event, location)
                created_events.append(event)

        if (
            previous_location.location_type == SavedLocation.LOCATION_SCHOOL
            and current_location.location_type == SavedLocation.LOCATION_HOME
        ):
            event_type = ChildSavedLocationEvent.EVENT_MOVING_SCHOOL_TO_HOME

            if should_send_saved_location_event(state, event_type):
                title, body = build_saved_location_message(
                    child=child,
                    event_type=event_type,
                    saved_location=current_location,
                    previous_location=previous_location,
                )

                event = ChildSavedLocationEvent.objects.create(
                    child=child,
                    parent=parent,
                    saved_location=current_location,
                    event_type=event_type,
                    title=title,
                    body=body,
                    latitude=location.latitude,
                    longitude=location.longitude,
                )

                send_saved_location_notification(parent, child, event, location)
                created_events.append(event)

    state.previous_location = previous_location
    state.current_location = current_location

    if created_events:
        state.last_event_type = created_events[-1].event_type
        state.last_event_at = timezone.now()

    state.save(
        update_fields=[
            "previous_location",
            "current_location",
            "last_event_type",
            "last_event_at",
            "updated_at",
        ]
    )

    return created_events


def previous_location_id_equals(previous_location, current_location):
    previous_id = previous_location.id if previous_location else None
    current_id = current_location.id if current_location else None
    return previous_id == current_id


DEFAULT_TRIAL_DAYS = 14


def get_active_subscription(user):
    return UserSubscription.objects.filter(
        user=user,
        status__in=[
            UserSubscription.STATUS_TRIAL,
            UserSubscription.STATUS_ACTIVE,
        ],
        expires_at__gt=timezone.now(),
    ).select_related("plan").order_by("-expires_at").first()


def sync_user_premium_status(user):
    subscription = get_active_subscription(user)

    if subscription:
        user.is_premium = True
        user.premium_expires_at = subscription.expires_at
    else:
        user.is_premium = False
        user.premium_expires_at = None

    user.save(update_fields=["is_premium", "premium_expires_at"])
    return subscription


def give_free_trial_if_new_user(user, days=DEFAULT_TRIAL_DAYS):
    if user.role != user.ROLE_PARENT:
        return None

    if UserSubscription.objects.filter(
        user=user,
        source=UserSubscription.SOURCE_TRIAL,
    ).exists():
        return None

    now = timezone.now()
    expires_at = now + timedelta(days=days)

    trial_plan = SubscriptionPlan.objects.filter(
        is_trial=True,
        is_active=True,
    ).order_by("order", "id").first()

    subscription = UserSubscription.objects.create(
        user=user,
        plan=trial_plan,
        status=UserSubscription.STATUS_TRIAL,
        source=UserSubscription.SOURCE_TRIAL,
        started_at=now,
        expires_at=expires_at,
    )

    user.is_premium = True
    user.premium_expires_at = expires_at
    user.save(update_fields=["is_premium", "premium_expires_at"])

    return subscription


def activate_paid_subscription(user, plan, source=UserSubscription.SOURCE_PAYMENT, created_by=None):
    now = timezone.now()

    active_subscription = get_active_subscription(user)
    start_date = active_subscription.expires_at if active_subscription else now
    expires_at = plan.calculate_expires_at(start_date=start_date)

    subscription = UserSubscription.objects.create(
        user=user,
        plan=plan,
        status=UserSubscription.STATUS_ACTIVE,
        source=source,
        started_at=start_date,
        expires_at=expires_at,
        created_by=created_by,
    )

    user.is_premium = True
    user.premium_expires_at = expires_at
    user.save(update_fields=["is_premium", "premium_expires_at"])

    return subscription