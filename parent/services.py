from datetime import timedelta, datetime
import math
from django.utils import timezone
from django.utils.dateparse import parse_datetime

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
    ChildFrequentPlace,
    ChildDestinationPrediction,
    ChildDailyActivity,
    ParentNotification,
    UserSubscription, SubscriptionPlan,
)
from .realtime import (
    broadcast_child_location,
    broadcast_route_alert,
    broadcast_saved_location_event,
    broadcast_destination_prediction,
    broadcast_parent_notification,
)
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


def record_parent_notification(
    parent,
    child,
    category,
    title,
    body,
    data=None,
    title_translations=None,
    body_translations=None,
):
    """Inbox yozuvi yaratadi va WS orqali parent ilovaga darhol uzatadi.

    `title` va `body` — asosiy (uz) matn. `title_translations` va
    `body_translations` — ixtiyoriy {"ru": "...", "en": "..."} dict'lari.
    Agar berilsa, ParentNotification _ru/_en maydonlariga yoziladi va
    parent tilini o'zgartirsa avval saqlangan xabarlar ham mos tilda
    ko'rinadi (LocalizedSerializerMixin tanlaydi).
    """
    if not parent:
        return None

    title_translations = title_translations or {}
    body_translations = body_translations or {}

    try:
        notification = ParentNotification.objects.create(
            parent=parent,
            child=child,
            category=category,
            title=(title or "")[:150],
            title_ru=(title_translations.get("ru") or "")[:150],
            title_en=(title_translations.get("en") or "")[:150],
            body=(body or "")[:500],
            body_ru=(body_translations.get("ru") or "")[:500],
            body_en=(body_translations.get("en") or "")[:500],
            data=data or {},
        )
    except Exception:
        return None
    try:
        broadcast_parent_notification(parent_id=parent.id, notification=notification)
    except Exception:
        pass
    return notification


def pick_for_lang(translations, lang, fallback=""):
    """Bola/parent uchun mos tildagi matnni tanlaydi.

    translations: {"uz": "...", "ru": "...", "en": "..."}
    """
    if not translations:
        return fallback
    code = (lang or "uz").lower()
    if code.startswith("ru"):
        return translations.get("ru") or translations.get("uz") or fallback
    if code.startswith("en"):
        return translations.get("en") or translations.get("uz") or fallback
    return translations.get("uz") or fallback


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
    name = child.full_name or child.first_name or ""
    fallback = {"uz": "Farzandingiz", "ru": "Ваш ребёнок", "en": "Your child"}

    def _name(lang):
        return name or fallback[lang]

    body_translations = {
        "uz": f"{_name('uz')} belgilangan marshrutdan chiqdi.",
        "ru": f"{_name('ru')} вышел за пределы маршрута.",
        "en": f"{_name('en')} left the assigned route.",
    }
    title_translations = {"uz": title, "ru": title, "en": title}
    body = body_translations["uz"]

    payload = {
        "type": "route_deviation",
        "child_id": child.id,
        "child_name": name,
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

    parent_lang = getattr(parent, "language", "uz") or "uz"
    fcm_body = pick_for_lang(body_translations, parent_lang, fallback=body)

    if tokens:
        try:
            send_fcm_multicast(
                tokens=tokens,
                title=title,
                body=fcm_body,
                data=payload,
            )
        except Exception:
            pass

    record_parent_notification(
        parent=parent,
        child=child,
        category=ParentNotification.CATEGORY_ROUTE,
        title=title,
        body=body,
        data=payload,
        title_translations=title_translations,
        body_translations=body_translations,
    )

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


def _parse_captured_at(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    parsed = parse_datetime(str(value))
    if parsed and timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, timezone.utc)
    return parsed


def process_child_location(
    child,
    latitude,
    longitude,
    accuracy=None,
    battery_level=None,
    speed=None,
    heading=None,
    altitude=None,
    altitude_accuracy=None,
    speed_accuracy=None,
    is_charging=None,
    signal_strength=None,
    network_type=None,
    provider=None,
    is_mock_location=None,
    activity_type=None,
    captured_at=None,
    source=ChildLocation.SOURCE_REST,
):

    latitude = to_float(latitude)
    longitude = to_float(longitude)
    accuracy = to_float(accuracy)
    battery_level = to_int(battery_level)
    speed = to_float(speed)
    heading = to_float(heading)
    altitude = to_float(altitude)
    altitude_accuracy = to_float(altitude_accuracy)
    speed_accuracy = to_float(speed_accuracy)
    signal_strength = to_int(signal_strength)
    captured_at = _parse_captured_at(captured_at)

    location = ChildLocation.objects.create(
        child=child,
        latitude=latitude,
        longitude=longitude,
        accuracy=accuracy,
        altitude=altitude,
        altitude_accuracy=altitude_accuracy,
        battery_level=battery_level,
        is_charging=is_charging if is_charging is not None else None,
        speed=speed,
        speed_accuracy=speed_accuracy,
        heading=heading,
        signal_strength=signal_strength,
        network_type=(network_type or "")[:20],
        provider=(provider or "")[:20],
        is_mock_location=bool(is_mock_location) if is_mock_location is not None else False,
        activity_type=(activity_type or "")[:20],
        captured_at=captured_at,
        source=source,
    )
    # [LOC] print olib tashlandi — har bir GPS ping'da log yozish I/O ni
    # to'ldirib boshqa endpointlarni sekinlashtirar edi. Agar debug kerak
    # bo'lsa, logging.debug() ishlatib LOG_LEVEL=DEBUG qiling.

    # ChildDailyActivity'ni bugungi kun uchun yangilash:
    # oxirgi nuqta bilan masofa farqi qo'shiladi.
    try:
        _accumulate_daily_activity(child=child, location=location)
    except Exception:
        pass

    ChildLastLocation.objects.update_or_create(
        child=child,
        defaults={
            "latitude": latitude,
            "longitude": longitude,
            "accuracy": accuracy,
            "altitude": altitude,
            "battery_level": battery_level,
            "is_charging": is_charging,
            "speed": speed,
            "heading": heading,
            "signal_strength": signal_strength,
            "network_type": (network_type or "")[:20],
            "activity_type": (activity_type or "")[:20],
            "provider": (provider or "")[:20],
            "captured_at": captured_at,
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

    # Frequent place detection — har ~30 sekundda bir nuqta yetarli.
    try:
        update_frequent_places_for_location(child=child, location=location)
    except Exception:
        pass

    # Destination prediction (uy/maktab/do'st uyiga yaqinlashishi).
    try:
        run_destination_predictions(child=child, location=location)
    except Exception:
        pass

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
    """Saqlangan joy hodisalari uchun ko'p tilli xabar.

    Qaytaradi: (title, body) — har biri {"uz", "ru", "en"} dict.
    Eski uz tilidagi single-tuple chaqiruvchilarga moslik uchun
    .get('uz') orqali ham olinadigan bo'lib qoldirilgan.
    """
    fallbacks = {
        "uz": "Farzandingiz",
        "ru": "Ваш ребёнок",
        "en": "Your child",
    }
    name = child.full_name or child.first_name or ""

    def child_name(lang):
        return name or fallbacks.get(lang, fallbacks["uz"])

    title = {"uz": "Jojo", "ru": "Jojo", "en": "Jojo"}

    if event_type == ChildSavedLocationEvent.EVENT_ENTER:
        loc = saved_location.name if saved_location else ""
        body = {
            "uz": f"{child_name('uz')} {loc} hududiga kirdi.",
            "ru": f"{child_name('ru')} вошёл в зону «{loc}».",
            "en": f"{child_name('en')} entered the «{loc}» area.",
        }
        return (title, body)

    if event_type == ChildSavedLocationEvent.EVENT_EXIT:
        loc = previous_location.name if previous_location else ""
        body = {
            "uz": f"{child_name('uz')} {loc} hududidan chiqdi.",
            "ru": f"{child_name('ru')} вышел из зоны «{loc}».",
            "en": f"{child_name('en')} left the «{loc}» area.",
        }
        return (title, body)

    if event_type == ChildSavedLocationEvent.EVENT_MOVING_HOME_TO_SCHOOL:
        body = {
            "uz": f"{child_name('uz')} uydan chiqib maktab tomonga ketayapti.",
            "ru": f"{child_name('ru')} вышел из дома и направляется в школу.",
            "en": f"{child_name('en')} left home and is heading to school.",
        }
        return (title, body)

    if event_type == ChildSavedLocationEvent.EVENT_MOVING_SCHOOL_TO_HOME:
        body = {
            "uz": f"{child_name('uz')} maktabdan chiqib uy tomonga ketayapti.",
            "ru": f"{child_name('ru')} вышел из школы и направляется домой.",
            "en": f"{child_name('en')} left school and is heading home.",
        }
        return (title, body)

    body = {
        "uz": f"{child_name('uz')} joylashuvi o'zgardi.",
        "ru": f"Местоположение ребёнка изменилось.",
        "en": f"{child_name('en')}'s location changed.",
    }
    return (title, body)


def send_saved_location_notification(
    parent, child, event, location,
    title_translations=None, body_translations=None,
):
    """FCM ni parent tiliga moslab yuboradi, inbox yozuvini ko'p tilli saqlaydi."""
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

    # FCM matnini parent tilini hisobga olgan holda tanlaymiz.
    parent_lang = getattr(parent, "language", "uz") or "uz"
    fcm_title = pick_for_lang(title_translations, parent_lang, fallback=event.title)
    fcm_body = pick_for_lang(body_translations, parent_lang, fallback=event.body)

    if tokens:
        try:
            send_fcm_multicast(
                tokens=tokens,
                title=fcm_title,
                body=fcm_body,
                data=payload,
            )
        except Exception:
            pass

    category_map = {
        ChildSavedLocationEvent.EVENT_ENTER: ParentNotification.CATEGORY_ZONE_IN,
        ChildSavedLocationEvent.EVENT_EXIT: ParentNotification.CATEGORY_ZONE_OUT,
        ChildSavedLocationEvent.EVENT_MOVING_HOME_TO_SCHOOL:
            ParentNotification.CATEGORY_ZONE_TRANSITION,
        ChildSavedLocationEvent.EVENT_MOVING_SCHOOL_TO_HOME:
            ParentNotification.CATEGORY_ZONE_TRANSITION,
    }
    record_parent_notification(
        parent=parent,
        child=child,
        category=category_map.get(event.event_type, ParentNotification.CATEGORY_ZONE_IN),
        title=event.title,
        body=event.body,
        data=payload,
        title_translations=title_translations,
        body_translations=body_translations,
    )
        
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
            title_tr, body_tr = build_saved_location_message(
                child=child,
                event_type=event_type,
                previous_location=previous_location,
            )

            event = ChildSavedLocationEvent.objects.create(
                child=child,
                parent=parent,
                saved_location=previous_location,
                event_type=event_type,
                title=title_tr.get("uz", "Jojo"),
                body=body_tr.get("uz", ""),
                latitude=location.latitude,
                longitude=location.longitude,
            )

            send_saved_location_notification(
                parent, child, event, location,
                title_translations=title_tr,
                body_translations=body_tr,
            )
            created_events.append(event)

    # Yangi saved locationga kirdi
    if current_location and not previous_location:
        event_type = ChildSavedLocationEvent.EVENT_ENTER

        if should_send_saved_location_event(state, event_type):
            title_tr, body_tr = build_saved_location_message(
                child=child,
                event_type=event_type,
                saved_location=current_location,
            )

            event = ChildSavedLocationEvent.objects.create(
                child=child,
                parent=parent,
                saved_location=current_location,
                event_type=event_type,
                title=title_tr.get("uz", "Jojo"),
                body=body_tr.get("uz", ""),
                latitude=location.latitude,
                longitude=location.longitude,
            )

            send_saved_location_notification(
                parent, child, event, location,
                title_translations=title_tr,
                body_translations=body_tr,
            )
            created_events.append(event)

    # Home -> School mantiqi
    if previous_location and current_location:
        if (
            previous_location.location_type == SavedLocation.LOCATION_HOME
            and current_location.location_type == SavedLocation.LOCATION_SCHOOL
        ):
            event_type = ChildSavedLocationEvent.EVENT_MOVING_HOME_TO_SCHOOL

            if should_send_saved_location_event(state, event_type):
                title_tr, body_tr = build_saved_location_message(
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
                    title=title_tr.get("uz", "Jojo"),
                    body=body_tr.get("uz", ""),
                    latitude=location.latitude,
                    longitude=location.longitude,
                )

                send_saved_location_notification(
                    parent, child, event, location,
                    title_translations=title_tr,
                    body_translations=body_tr,
                )
                created_events.append(event)

        if (
            previous_location.location_type == SavedLocation.LOCATION_SCHOOL
            and current_location.location_type == SavedLocation.LOCATION_HOME
        ):
            event_type = ChildSavedLocationEvent.EVENT_MOVING_SCHOOL_TO_HOME

            if should_send_saved_location_event(state, event_type):
                title_tr, body_tr = build_saved_location_message(
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
                    title=title_tr.get("uz", "Jojo"),
                    body=body_tr.get("uz", ""),
                    latitude=location.latitude,
                    longitude=location.longitude,
                )

                send_saved_location_notification(
                    parent, child, event, location,
                    title_translations=title_tr,
                    body_translations=body_tr,
                )
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

    # Hudud bo'yicha ilova bloklash qoidalari effective bo'lishi mumkin —
    # bola hududga kirsa/chiqsa, kid qurilmasiga yangi policy ro'yxati
    # WS orqali darrov yuboriladi. Importni tsiklik bog'liqlikdan saqlash
    # uchun lazy chaqiramiz.
    if created_events:
        try:
            from .views import _build_and_push_child_policies
            _build_and_push_child_policies(child.id)
        except Exception:
            pass

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

# ============================================================================
# Frequent-places: clustering + recommendation
# ============================================================================


FREQUENT_PLACE_RADIUS_METERS = 120
FREQUENT_PLACE_MIN_VISITS_FOR_RECOMMENDATION = 5
FREQUENT_PLACE_MIN_DWELL_SECONDS = 5 * 60          # 5 daqiqa dwell hisoblanadi
FREQUENT_PLACE_VISIT_WINDOW_HOURS = 2              # bir tashrif oralig'i


def _now():
    return timezone.now()


def update_frequent_places_for_location(child, location):
    """Sodda inline clustering.

    - Birinchi marta yaqin nuqtani topib oladi
    - Topilsa, visit_count'ni oshiradi va dwell qo'shadi
    - Topilmasa, yangi cluster yaratadi
    Bu agressiv DBSCAN emas — har bir nuqtada O(N) joriy cluster soni.
    Ko'p farzand uchun N kichik bo'ladi (~ < 50).
    """
    parent = get_child_parent(child)

    lat = float(location.latitude)
    lng = float(location.longitude)

    nearest = None
    nearest_distance = None

    for place in ChildFrequentPlace.objects.filter(child=child):
        distance = calculate_distance_meters(
            lat1=lat, lon1=lng,
            lat2=float(place.latitude), lon2=float(place.longitude),
        )
        if distance > place.radius_meters:
            continue
        if nearest_distance is None or distance < nearest_distance:
            nearest = place
            nearest_distance = distance

    now = _now()

    if nearest is None:
        ChildFrequentPlace.objects.create(
            child=child,
            parent=parent,
            latitude=lat,
            longitude=lng,
            radius_meters=FREQUENT_PLACE_RADIUS_METERS,
            visit_count=1,
            total_dwell_seconds=0,
        )
        return None

    # Bu joyga oxirgi marta `FREQUENT_PLACE_VISIT_WINDOW_HOURS` oldin kelgan bo'lsa
    # — yangi tashrif sifatida hisoblaymiz, aks holda dwell.
    visit_added = False
    if nearest.last_seen_at and (now - nearest.last_seen_at).total_seconds() > FREQUENT_PLACE_VISIT_WINDOW_HOURS * 3600:
        nearest.visit_count = (nearest.visit_count or 0) + 1
        visit_added = True
    else:
        # Dwell qo'shamiz
        if nearest.last_seen_at:
            delta = (now - nearest.last_seen_at).total_seconds()
            if 0 < delta < 30 * 60:  # 30 daqiqadan kichik delta — haqiqiy dwell
                nearest.total_dwell_seconds = (nearest.total_dwell_seconds or 0) + int(delta)

    # Markazni surilgan o'rtacha (running average)
    new_lat = (float(nearest.latitude) * 9 + lat) / 10
    new_lng = (float(nearest.longitude) * 9 + lng) / 10
    nearest.latitude = new_lat
    nearest.longitude = new_lng

    nearest.save(update_fields=[
        "visit_count", "total_dwell_seconds",
        "latitude", "longitude", "last_seen_at",
    ])

    if visit_added:
        _maybe_emit_recommendation(parent=parent, child=child, place=nearest)

    return nearest


def _maybe_emit_recommendation(parent, child, place):
    """Visit_count threshold'ga yetganda recommendation kanaliga yuboradi.

    Real recommendation lists `/parent/.../place-recommendations/` REST
    endpointidan o'qiladi (qaytariladigan flag bilan). Bu yerda faqat
    FCM yuborish va broadcast qilish.
    """
    if not parent:
        return
    if place.is_recommendation_dismissed or place.saved_location_id:
        return
    if (place.visit_count or 0) < FREQUENT_PLACE_MIN_VISITS_FOR_RECOMMENDATION:
        return

    # Saved location ostida bormi tekshiramiz — agar shu radius ichida saved
    # location bor bo'lsa, recommendation chiqarmaymiz.
    overlapping = SavedLocation.objects.filter(parent=parent, is_active=True).only(
        "latitude", "longitude", "radius_meters",
    )
    for sl in overlapping:
        distance = calculate_distance_meters(
            lat1=float(place.latitude), lon1=float(place.longitude),
            lat2=float(sl.latitude), lon2=float(sl.longitude),
        )
        if distance <= max(place.radius_meters, sl.radius_meters):
            return  # allaqachon saqlangan

    # FCM tavsiyasi
    tokens = list(
        DeviceToken.objects.filter(user=parent, is_active=True)
        .values_list("token", flat=True)
    )
    name = child.full_name or child.first_name or ""
    fb = {"uz": "Farzandingiz", "ru": "Ваш ребёнок", "en": "Your child"}

    def _n(lang):
        return name or fb[lang]

    title = "Jojo"
    body_translations = {
        "uz": f"{_n('uz')} ushbu joyga ko'p marta tashrif buyuradi. Saqlanganga qo'shamizmi?",
        "ru": f"{_n('ru')} часто посещает это место. Добавить в сохранённые?",
        "en": f"{_n('en')} visits this place often. Add it to saved locations?",
    }
    title_translations = {"uz": title, "ru": title, "en": title}
    body = body_translations["uz"]

    payload = {
        "type": "place_recommendation",
        "child_id": child.id,
        "place_id": place.id,
        "latitude": float(place.latitude),
        "longitude": float(place.longitude),
        "visit_count": place.visit_count,
    }

    parent_lang = getattr(parent, "language", "uz") or "uz"
    fcm_body = pick_for_lang(body_translations, parent_lang, fallback=body)
    if tokens:
        try:
            send_fcm_multicast(tokens=tokens, title=title, body=fcm_body, data=payload)
        except Exception:
            pass

    record_parent_notification(
        parent=parent,
        child=child,
        category=ParentNotification.CATEGORY_PLACE_RECOMMENDATION,
        title=title,
        body=body,
        data=payload,
        title_translations=title_translations,
        body_translations=body_translations,
    )


# ============================================================================
# Destination prediction (uy/maktab/do'st uyiga yaqinlashish)
# ============================================================================


DEST_HEADING_TOLERANCE_DEGREES = 35       # yo'nalish gradusi qancha mos kelishi
DEST_MIN_SPEED_KMH = 3                     # past tezlikda harakat hisoblanmaydi
DEST_NEAR_RADIUS_METERS = 400              # shu masofadan kelganda "yaqinlashyapti"
DEST_ARRIVING_RADIUS_METERS = 80           # "yetib kelyapti" pasligi
DEST_THROTTLE_MINUTES = 15                 # bir hil bashoratni qayta yubormaymiz


def _bearing_deg(lat1, lon1, lat2, lon2):
    """Initial bearing from (1) to (2) in degrees 0..360."""
    phi1 = math.radians(float(lat1))
    phi2 = math.radians(float(lat2))
    dl = math.radians(float(lon2) - float(lon1))

    x = math.sin(dl) * math.cos(phi2)
    y = (
        math.cos(phi1) * math.sin(phi2)
        - math.sin(phi1) * math.cos(phi2) * math.cos(dl)
    )
    deg = math.degrees(math.atan2(x, y))
    return (deg + 360) % 360


def _angle_diff(a, b):
    diff = abs(a - b) % 360
    return diff if diff <= 180 else 360 - diff


def run_destination_predictions(child, location):
    """Hozirgi joylashuv, tezlik va yo'nalish asosida saved locationga
    yaqinlashayotganligi haqida xabar berish."""

    parent = get_child_parent(child)
    if not parent:
        return []

    heading = to_float(location.heading)
    speed = to_float(location.speed)
    if speed is None:
        speed = 0
    speed_kmh = speed * 3.6

    if speed_kmh < DEST_MIN_SPEED_KMH:
        return []

    lat = float(location.latitude)
    lng = float(location.longitude)

    saved_locations = SavedLocation.objects.filter(
        parent=parent, is_active=True,
    )

    emitted = []

    for sl in saved_locations:
        distance = calculate_distance_meters(
            lat1=lat, lon1=lng,
            lat2=float(sl.latitude), lon2=float(sl.longitude),
        )

        if distance > DEST_NEAR_RADIUS_METERS:
            continue

        # Saved location ichida bo'lsa — bu boshqa event (enter), o'tkazib yuboramiz.
        if distance <= sl.radius_meters:
            continue

        # Yo'nalish saved locationga qaragandami?
        if heading is not None:
            bearing_to_target = _bearing_deg(lat, lng, float(sl.latitude), float(sl.longitude))
            if _angle_diff(bearing_to_target, heading) > DEST_HEADING_TOLERANCE_DEGREES:
                continue

        # Throttle — oxirgi bashoratdan beri 15 daqiqa o'tdimi?
        last = ChildDestinationPrediction.objects.filter(
            child=child, saved_location=sl,
        ).order_by("-created_at").first()
        if last and (_now() - last.created_at) < timedelta(minutes=DEST_THROTTLE_MINUTES):
            continue

        event_type = (
            ChildDestinationPrediction.EVENT_ARRIVING_SOON
            if distance <= DEST_ARRIVING_RADIUS_METERS
            else ChildDestinationPrediction.EVENT_HEADING_TO
        )

        eta = distance / max(speed, 0.5)  # sekund (m / (m/s))

        title_tr, body_tr = _build_prediction_message(
            child=child, saved_location=sl, event_type=event_type,
        )
        title = title_tr.get("uz", "Jojo")
        body = body_tr.get("uz", "")

        prediction = ChildDestinationPrediction.objects.create(
            child=child,
            parent=parent,
            saved_location=sl,
            event_type=event_type,
            distance_meters=distance,
            speed_kmh=round(speed_kmh, 2),
            eta_seconds=round(eta, 1),
            title=title,
            body=body,
        )

        # FCM — parent tilini hisobga olgan holda
        tokens = list(
            DeviceToken.objects.filter(user=parent, is_active=True)
            .values_list("token", flat=True)
        )
        prediction_payload = {
            "type": "destination_prediction",
            "event_type": event_type,
            "child_id": child.id,
            "saved_location_id": sl.id,
            "distance_meters": round(distance, 1),
            "eta_seconds": round(eta, 1),
        }
        parent_lang = getattr(parent, "language", "uz") or "uz"
        fcm_body = pick_for_lang(body_tr, parent_lang, fallback=body)
        if tokens:
            try:
                send_fcm_multicast(
                    tokens=tokens,
                    title=title,
                    body=fcm_body,
                    data=prediction_payload,
                )
            except Exception:
                pass

        record_parent_notification(
            parent=parent,
            child=child,
            category=ParentNotification.CATEGORY_DESTINATION,
            title=title,
            body=body,
            data=prediction_payload,
            title_translations=title_tr,
            body_translations=body_tr,
        )

        # WS broadcast
        try:
            broadcast_destination_prediction(parent_id=parent.id, prediction=prediction)
        except Exception:
            pass

        emitted.append(prediction)

    return emitted


def _build_prediction_message(child, saved_location, event_type):
    """Qaytaradi: (title_dict, body_dict) — har biri uz/ru/en."""
    name = child.full_name or child.first_name or ""
    fb = {"uz": "Farzandingiz", "ru": "Ваш ребёнок", "en": "Your child"}

    def _n(lang):
        return name or fb[lang]

    place_name = saved_location.name
    place_type = (saved_location.location_type or "").lower()
    title_tr = {"uz": "Jojo", "ru": "Jojo", "en": "Jojo"}

    if event_type == ChildDestinationPrediction.EVENT_ARRIVING_SOON:
        if place_type == SavedLocation.LOCATION_HOME:
            body = {
                "uz": f"{_n('uz')} uyga yetib keldi.",
                "ru": f"{_n('ru')} прибыл домой.",
                "en": f"{_n('en')} has arrived home.",
            }
            return (title_tr, body)
        if place_type == SavedLocation.LOCATION_SCHOOL:
            body = {
                "uz": f"{_n('uz')} maktabga yaqin qoldi.",
                "ru": f"{_n('ru')} почти у школы.",
                "en": f"{_n('en')} is close to school.",
            }
            return (title_tr, body)
        body = {
            "uz": f"{_n('uz')} '{place_name}' yaqiniga keldi.",
            "ru": f"{_n('ru')} приближается к «{place_name}».",
            "en": f"{_n('en')} is near «{place_name}».",
        }
        return (title_tr, body)

    # heading_to
    if place_type == SavedLocation.LOCATION_HOME:
        body = {
            "uz": f"{_n('uz')} uyga yaqinlashyapti.",
            "ru": f"{_n('ru')} направляется домой.",
            "en": f"{_n('en')} is heading home.",
        }
        return (title_tr, body)
    if place_type == SavedLocation.LOCATION_SCHOOL:
        body = {
            "uz": f"{_n('uz')} maktab tomon ketmoqda.",
            "ru": f"{_n('ru')} направляется в школу.",
            "en": f"{_n('en')} is heading to school.",
        }
        return (title_tr, body)
    body = {
        "uz": f"{_n('uz')} '{place_name}' tomon ketmoqda.",
        "ru": f"{_n('ru')} направляется к «{place_name}».",
        "en": f"{_n('en')} is heading to «{place_name}».",
    }
    return (title_tr, body)


# ============================================================================
# Daily activity (km) auto-update
# Kids ilovaning explicit sync'iga tayanmasdan, har bir kelgan location
# nuqtasidan oldingisigacha bo'lgan masofa ChildDailyActivity'ga qo'shiladi.
# Bu real-time km ko'rsatkichini imkon beradi.
# ============================================================================


# Bog'liq emas — barcha tezliklarni avtomatik filterlash uchun limitlar.
_DAILY_MIN_STEP_METERS = 3       # 3 metrdan kichik kichik shovqin — qabul qilmaymiz
_DAILY_MAX_STEP_METERS = 1500    # 1.5 km dan katta sakrash — GPS xatosi
_DAILY_MAX_GAP_SECONDS = 600     # 10 daqiqadan ko'p oraliq — boshqa kun ehtimol


def _accumulate_daily_activity(child, location):
    today = location.created_at.date()

    # Oldingi location
    previous = ChildLocation.objects.filter(
        child=child,
        created_at__lt=location.created_at,
    ).order_by("-created_at").only(
        "latitude", "longitude", "created_at",
    ).first()

    if not previous:
        # Kunning birinchi nuqtasi — distance 0, lekin row yarataymiz.
        ChildDailyActivity.objects.get_or_create(
            child=child,
            activity_date=today,
        )
        return

    # Bir kun ichida bo'lsami?
    if previous.created_at.date() != today:
        ChildDailyActivity.objects.get_or_create(
            child=child,
            activity_date=today,
        )
        return

    gap_seconds = (location.created_at - previous.created_at).total_seconds()
    if gap_seconds > _DAILY_MAX_GAP_SECONDS:
        return

    distance = calculate_distance_meters(
        lat1=previous.latitude, lon1=previous.longitude,
        lat2=location.latitude, lon2=location.longitude,
    )

    if distance < _DAILY_MIN_STEP_METERS:
        return  # GPS shovqini, hisobga kiritmaymiz
    if distance > _DAILY_MAX_STEP_METERS:
        return  # Sakrash — istisno

    activity, _created = ChildDailyActivity.objects.get_or_create(
        child=child,
        activity_date=today,
    )

    # Atomic update — multiple concurrent saves uchun
    from django.db.models import F as _F
    ChildDailyActivity.objects.filter(pk=activity.pk).update(
        distance_meters=_F("distance_meters") + int(distance),
        active_seconds=_F("active_seconds") + int(min(gap_seconds, 60)),
    )


# ============================================================================
# Journey timeline — kun davomidagi yo'l xulosasi
# ChildLocation nuqtalarini "to'xtagan joylar" (places) va "harakat
# parchalari" (segments) ga ajratadi. Findmykids dizayniga o'xshash.
# ============================================================================


_JOURNEY_PLACE_MIN_DWELL_SECONDS = 5 * 60        # 5 daqiqadan ortiq turish "joy"
_JOURNEY_PLACE_RADIUS_METERS = 60                # nuqta shu radiusda — bir joy
_JOURNEY_SEGMENT_MIN_DISTANCE_METERS = 30        # bundan kichik harakat — shovqin
_JOURNEY_MAX_GAP_SECONDS = 600                   # 10 daqiqadan katta uzilish — ajratish


def _classify_segment_activity(speeds_kmh, activity_types):
    """
    Segment davomidagi tezliklar va activity'lar o'rtacha qiymatidan
    eng aniq tasvirni tanlaydi.
    """
    if not speeds_kmh:
        return "walking"
    avg = sum(speeds_kmh) / len(speeds_kmh)
    peak = max(speeds_kmh)

    # in_vehicle activityni eng katta priortet bilan
    if "in_vehicle" in activity_types or "invehicle" in activity_types or peak >= 20:
        return "in_vehicle"
    if "running" in activity_types or peak >= 8:
        return "running"
    if avg >= 2:
        return "walking"
    return "walking"


def _classify_place(child, lat, lon):
    """Saved location'lardan birida bo'lsa shu joyni qaytaradi, aks holda None."""
    parent = get_child_parent(child)
    if not parent:
        return None
    saved_locations = SavedLocation.objects.filter(
        parent=parent, is_active=True
    )
    for sl in saved_locations:
        distance = calculate_distance_meters(
            lat1=lat, lon1=lon,
            lat2=float(sl.latitude), lon2=float(sl.longitude),
        )
        if distance <= max(sl.radius_meters, 50):
            return sl
    return None


def compute_child_journey(child, target_date):
    """Berilgan kun uchun bola yo'l xulosasini hisoblaydi.

    Qaytaradi:
      {
        "date": "YYYY-MM-DD",
        "summary": { ... },
        "items": [ {place/segment}, ... ]
      }
    """
    locations = list(
        ChildLocation.objects.filter(
            child=child,
            created_at__date=target_date,
        ).order_by("created_at").values(
            "id", "latitude", "longitude",
            "speed", "activity_type",
            "battery_level", "captured_at", "created_at",
        )
    )

    items = []
    summary = {
        "date": target_date.isoformat(),
        "total_distance_meters": 0,
        "max_speed_kmh": 0,
        "places_count": 0,
        "segments_count": 0,
        "first_seen_at": None,
        "last_seen_at": None,
    }

    if not locations:
        return {"date": target_date.isoformat(), "summary": summary, "items": []}

    summary["first_seen_at"] = (
        locations[0]["captured_at"] or locations[0]["created_at"]
    ).isoformat()
    summary["last_seen_at"] = (
        locations[-1]["captured_at"] or locations[-1]["created_at"]
    ).isoformat()

    # 1-bosqich: nuqtalarni "turish" yoki "harakat" deb yorliqlash
    n = len(locations)
    i = 0
    while i < n:
        # Place'ni topishga harakat — bir nuqtaning radiusida turuvchi nuqtalar
        anchor = locations[i]
        anchor_lat = float(anchor["latitude"])
        anchor_lon = float(anchor["longitude"])
        j = i + 1
        while j < n:
            next_loc = locations[j]
            d = calculate_distance_meters(
                lat1=anchor_lat, lon1=anchor_lon,
                lat2=float(next_loc["latitude"]),
                lon2=float(next_loc["longitude"]),
            )
            if d > _JOURNEY_PLACE_RADIUS_METERS:
                break
            j += 1

        anchor_time = anchor["captured_at"] or anchor["created_at"]
        end_idx = j - 1
        end_time = (
            locations[end_idx]["captured_at"]
            or locations[end_idx]["created_at"]
        )
        dwell_seconds = (end_time - anchor_time).total_seconds()

        if dwell_seconds >= _JOURNEY_PLACE_MIN_DWELL_SECONDS:
            # Bu place
            saved = _classify_place(child, anchor_lat, anchor_lon)
            place_item = {
                "type": "place",
                "saved_location_id": saved.id if saved else None,
                "saved_location_type": saved.location_type if saved else None,
                "name": saved.name if saved else "Joy",
                "latitude": anchor_lat,
                "longitude": anchor_lon,
                "arrived_at": anchor_time.isoformat(),
                "departed_at": end_time.isoformat(),
                "duration_seconds": int(dwell_seconds),
            }
            items.append(place_item)
            summary["places_count"] += 1
            i = j
            continue

        # Aks holda harakat segmentini topamiz — keyingi place'gacha
        # yoki kun oxirigacha
        seg_start_idx = i
        seg_points = []
        total_distance = 0.0
        speeds_kmh = []
        activity_set = set()

        prev = None
        k = i
        while k < n:
            cur = locations[k]
            cur_lat = float(cur["latitude"])
            cur_lon = float(cur["longitude"])
            cur_time = cur["captured_at"] or cur["created_at"]
            seg_points.append({
                "lat": cur_lat, "lng": cur_lon,
                "ts": cur_time.isoformat(),
                "speed_kmh": (cur["speed"] or 0) * 3.6 if cur["speed"] else 0,
            })
            if cur["speed"]:
                kmh = cur["speed"] * 3.6
                speeds_kmh.append(kmh)
                if kmh > summary["max_speed_kmh"]:
                    summary["max_speed_kmh"] = kmh
            if cur["activity_type"]:
                activity_set.add(cur["activity_type"])

            if prev is not None:
                gap = (
                    cur_time -
                    (prev["captured_at"] or prev["created_at"])
                ).total_seconds()
                if gap > _JOURNEY_MAX_GAP_SECONDS:
                    # Uzilish — segmentni shu yerda tugatamiz
                    break
                d = calculate_distance_meters(
                    lat1=float(prev["latitude"]),
                    lon1=float(prev["longitude"]),
                    lat2=cur_lat, lon2=cur_lon,
                )
                total_distance += d

                # Agar 5+ minut bir joyda turdik — bu joydir
                if d < 30:
                    same_place_seconds = 0
                    look_k = k + 1
                    while look_k < n:
                        next_p = locations[look_k]
                        check_d = calculate_distance_meters(
                            lat1=cur_lat, lon1=cur_lon,
                            lat2=float(next_p["latitude"]),
                            lon2=float(next_p["longitude"]),
                        )
                        if check_d > _JOURNEY_PLACE_RADIUS_METERS:
                            break
                        next_time = (
                            next_p["captured_at"] or next_p["created_at"]
                        )
                        same_place_seconds = (next_time - cur_time).total_seconds()
                        if same_place_seconds >= _JOURNEY_PLACE_MIN_DWELL_SECONDS:
                            break
                        look_k += 1
                    if same_place_seconds >= _JOURNEY_PLACE_MIN_DWELL_SECONDS:
                        # Yangi place boshlanmoqda — segmentni shu yerda tugatamiz
                        break

            prev = cur
            k += 1

        if total_distance >= _JOURNEY_SEGMENT_MIN_DISTANCE_METERS and len(seg_points) >= 2:
            activity = _classify_segment_activity(speeds_kmh, activity_set)
            start_p = seg_points[0]
            end_p = seg_points[-1]
            seg_duration = (
                (locations[k - 1]["captured_at"] or locations[k - 1]["created_at"])
                - (locations[seg_start_idx]["captured_at"] or locations[seg_start_idx]["created_at"])
            ).total_seconds()
            items.append({
                "type": "segment",
                "activity": activity,
                "start_at": start_p["ts"],
                "end_at": end_p["ts"],
                "duration_seconds": int(max(seg_duration, 0)),
                "distance_meters": int(total_distance),
                "max_speed_kmh": round(max(speeds_kmh) if speeds_kmh else 0, 1),
                "avg_speed_kmh": round(
                    sum(speeds_kmh) / len(speeds_kmh) if speeds_kmh else 0, 1
                ),
                "start_lat": start_p["lat"],
                "start_lng": start_p["lng"],
                "end_lat": end_p["lat"],
                "end_lng": end_p["lng"],
                "polyline": seg_points,
            })
            summary["total_distance_meters"] += int(total_distance)
            summary["segments_count"] += 1
            i = k
        else:
            i = k if k > i else (i + 1)

    summary["max_speed_kmh"] = round(summary["max_speed_kmh"], 1)
    return {
        "date": target_date.isoformat(),
        "summary": summary,
        "items": items,
    }
