from jojolingo.models import (
    Lesson,
    LessonProgress,
    MistakeLog,
)

from jojolingo.services.analytics_service import (
    detect_learning_speed,
)


def get_child_profile(child):
    return getattr(child, "learning_profile", None)


def get_first_uncompleted(child, lessons):
    lessons = lessons.order_by(
        "unit__level__order",
        "unit__order",
        "order",
        "id",
    )

    for lesson in lessons:
        completed = LessonProgress.objects.filter(
            child=child,
            lesson=lesson,
            is_completed=True,
        ).exists()

        if not completed:
            return lesson

    return None


def get_next_lesson_for_child(child):
    profile = get_child_profile(child)

    if not profile:
        return None

    if not profile.current_course:
        return None

    lessons = Lesson.objects.filter(
        unit__course=profile.current_course,
        is_active=True,
    ).select_related(
        "unit",
        "unit__level",
    ).prefetch_related(
        "topics",
    )

    if profile.current_level:
        lessons = lessons.filter(
            unit__level=profile.current_level
        )

    if profile.interests:
        interested_lessons = lessons.filter(
            topics__name__in=profile.interests
        ).distinct()

        lesson = get_first_uncompleted(
            child,
            interested_lessons,
        )

        if lesson:
            return lesson

    return get_first_uncompleted(
        child,
        lessons,
    )


def get_review_lesson_reason(child):
    mistakes = MistakeLog.objects.filter(
        child=child
    ).order_by("-created_at")[:10]

    if mistakes.count() >= 3:
        return "mistakes_review"

    return "normal_next_lesson"


def get_adaptive_challenge_type(child):
    analytics = getattr(
        child,
        "learning_analytics",
        None,
    )

    if not analytics:
        return "normal"

    speed = detect_learning_speed(
        analytics
    )

    if speed == "fast":
        return "harder_challenge"

    if speed == "slow":
        return "review_more"

    return "normal"