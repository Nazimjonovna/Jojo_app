from django.utils import timezone

from .models import SubscriptionPlan, UserSubscription


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
    active_subscription = get_active_subscription(user)

    if active_subscription:
        user.is_premium = True
        user.premium_expires_at = active_subscription.expires_at
    else:
        user.is_premium = False
        user.premium_expires_at = None

        UserSubscription.objects.filter(
            user=user,
            status__in=[
                UserSubscription.STATUS_TRIAL,
                UserSubscription.STATUS_ACTIVE,
            ],
            expires_at__lte=timezone.now(),
        ).update(status=UserSubscription.STATUS_EXPIRED)

    user.save(update_fields=["is_premium", "premium_expires_at"])

    return active_subscription


def get_active_trial_plan():
    return SubscriptionPlan.objects.filter(
        is_trial=True,
        is_active=True,
        trial_days__gt=0,
    ).order_by("order", "id").first()


def get_paid_plans():
    return SubscriptionPlan.objects.filter(
        is_trial=False,
        is_active=True,
    ).order_by("order", "price")


def give_free_trial_if_new_user(user):
    if user.role != user.ROLE_PARENT:
        return None

    if UserSubscription.objects.filter(
        user=user,
        source=UserSubscription.SOURCE_TRIAL,
    ).exists():
        return None

    trial_plan = get_active_trial_plan()

    if not trial_plan:
        return None

    now = timezone.now()
    expires_at = trial_plan.calculate_expires_at(start_date=now)

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