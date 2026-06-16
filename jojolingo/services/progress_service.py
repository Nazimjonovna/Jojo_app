from django.utils import timezone

from jojolingo.models import (
    Level,
    ChildLearningProfile,
    LessonProgress,
    MistakeLog,
)

from jojolingo.services.events import emit, Event


def get_or_create_learning_profile(child):
    profile, _ = ChildLearningProfile.objects.get_or_create(child=child)
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


def add_xp(child, xp):
    profile = get_or_create_learning_profile(child)

    if xp <= 0:
        return {
            "profile": profile,
            "gamification": None,
        }

    gamification = emit(
        Event.XP_EARNED,
        profile,
        xp_earned=xp,
    )

    update_child_level(profile)

    return {
        "profile": profile,
        "gamification": gamification,
    }


def complete_lesson(child, lesson, score, total, time_spent_seconds=0):
    if total <= 0:
        raise ValueError("total noto‘g‘ri")

    profile = get_or_create_learning_profile(child)

    accuracy = round((score / total) * 100, 2)
    is_completed = accuracy >= lesson.required_accuracy
    is_perfect = score == total and total > 0

    earned_xp = lesson.reward_xp if is_completed else 0

    progress, _ = LessonProgress.objects.get_or_create(
        child=child,
        lesson=lesson,
    )

    already_completed = progress.is_completed

    progress.score = max(progress.score, score)
    progress.accuracy = max(progress.accuracy, accuracy)
    progress.attempt_count += 1

    gamification = None

    if is_completed:
        progress.is_completed = True
        progress.completed_at = timezone.now()
        progress.earned_xp = max(progress.earned_xp, earned_xp)

        if not already_completed:
            gamification = emit(
                Event.LESSON_COMPLETED,
                profile,
                xp_earned=earned_xp,
                is_perfect=is_perfect,
                accuracy=accuracy,
                lesson_id=lesson.id,
                time_spent_seconds=time_spent_seconds,
            )
            update_child_level(profile)

    progress.save()

    return {
        "lesson_id": lesson.id,
        "is_completed": is_completed,
        "already_completed": already_completed,
        "score": score,
        "total": total,
        "accuracy": accuracy,
        "earned_xp": 0 if already_completed else earned_xp,
        "required_accuracy": lesson.required_accuracy,
        "gamification": gamification,
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