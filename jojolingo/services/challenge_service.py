from django.utils import timezone

from jojolingo.models import Challenge, ChildChallenge


def get_active_challenges():
    now = timezone.now()

    return Challenge.objects.filter(
        is_active=True
    ).filter(
        starts_at__isnull=True
    ) | Challenge.objects.filter(
        is_active=True,
        starts_at__lte=now,
    )


def assign_active_challenges(child):
    challenges = get_active_challenges()

    for challenge in challenges:
        if challenge.ends_at and challenge.ends_at < timezone.now():
            continue

        ChildChallenge.objects.get_or_create(
            child=child,
            challenge=challenge,
        )


def update_challenge_progress(child, target_type, amount=1):
    assign_active_challenges(child)

    child_challenges = ChildChallenge.objects.filter(
        child=child,
        challenge__target_type=target_type,
        challenge__is_active=True,
        is_completed=False,
    ).select_related("challenge")

    completed = []

    for child_challenge in child_challenges:
        child_challenge.progress += amount

        if child_challenge.progress >= child_challenge.challenge.target_value:
            child_challenge.is_completed = True
            child_challenge.completed_at = timezone.now()
            completed.append(child_challenge.challenge)

        child_challenge.save()

    return completed