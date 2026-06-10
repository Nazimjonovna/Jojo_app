from jojolingo.models import Lesson, LessonProgress, MistakeLog


def get_child_profile(child):
    return getattr(child, "learning_profile", None)


def get_next_lesson_for_child(child):
    profile = get_child_profile(child)

    if not profile or not profile.current_course:
        return None

    course = profile.current_course
    level = profile.current_level

    lessons = Lesson.objects.filter(
        unit__course=course,
        is_active=True,
    ).select_related(
        "unit",
        "unit__level",
    )

    if level:
        lessons = lessons.filter(unit__level=level)

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


def get_review_lesson_reason(child):
    mistakes = MistakeLog.objects.filter(
        child=child
    ).order_by("-created_at")[:10]

    if mistakes.count() >= 3:
        return "mistakes_review"

    return "normal_next_lesson"