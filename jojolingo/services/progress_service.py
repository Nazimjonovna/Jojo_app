from django.utils import timezone

from jojolingo.models import (
    Level,
    ChildLearningProfile,
    LessonProgress,
    MistakeLog,
)


def get_or_create_learning_profile(child):
    profile, _ = ChildLearningProfile.objects.get_or_create(
        child=child
    )
    return profile


def update_streak(profile):
    today = timezone.now().date()

    if not profile.last_learning_date:
        profile.streak_days = 1
        profile.last_learning_date = today
        return profile

    if profile.last_learning_date == today:
        return profile

    yesterday = today - timezone.timedelta(days=1)

    if profile.last_learning_date == yesterday:
        profile.streak_days += 1
    else:
        profile.streak_days = 1

    profile.last_learning_date = today
    return profile


def add_xp(child, xp):
    profile = get_or_create_learning_profile(child)

    if xp <= 0:
        return profile

    profile.total_xp += xp
    profile = update_streak(profile)
    profile.save(
        update_fields=[
            "total_xp",
            "streak_days",
            "last_learning_date",
            "updated_at",
        ]
    )

    update_child_level(profile)

    return profile


def update_child_level(profile):
    if not profile.current_course:
        return profile

    level = Level.objects.filter(
        course=profile.current_course,
        min_xp__lte=profile.total_xp,
    ).order_by("-min_xp").first()

    if level and profile.current_level_id != level.id:
        profile.current_level = level
        profile.ai_friend_level = level.code
        profile.save(
            update_fields=[
                "current_level",
                "ai_friend_level",
                "updated_at",
            ]
        )

    return profile


def complete_lesson(child, lesson, score, total):
    if total <= 0:
        raise ValueError("total noto‘g‘ri")

    accuracy = round((score / total) * 100, 2)
    is_completed = accuracy >= lesson.required_accuracy

    earned_xp = lesson.reward_xp if is_completed else 0

    progress, _ = LessonProgress.objects.get_or_create(
        child=child,
        lesson=lesson,
    )

    already_completed = progress.is_completed

    progress.score = score
    progress.accuracy = accuracy
    progress.attempt_count += 1

    if is_completed:
        progress.is_completed = True
        progress.completed_at = timezone.now()
        progress.earned_xp = max(progress.earned_xp, earned_xp)

    progress.save()

    if is_completed and not already_completed:
        add_xp(child, earned_xp)

    return {
        "lesson_id": lesson.id,
        "is_completed": is_completed,
        "already_completed": already_completed,
        "score": score,
        "total": total,
        "accuracy": accuracy,
        "earned_xp": 0 if already_completed else earned_xp,
        "required_accuracy": lesson.required_accuracy,
    }


def log_mistake(child, exercise, given_answer):
    return MistakeLog.objects.create(
        child=child,
        exercise=exercise,
        given_answer=given_answer,
        correct_answer=exercise.correct_answer or "",
        mistake_type=exercise.exercise_type,
        explanation=exercise.explanation or "",
    )


def check_text_answer(given_answer, correct_answer):
    if given_answer is None or correct_answer is None:
        return False

    return given_answer.strip().lower() == correct_answer.strip().lower()