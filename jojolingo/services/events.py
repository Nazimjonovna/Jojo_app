"""
services/events.py — markaziy event dispatcher.

Nima uchun kerak:
  answer_service / progress_service ichidan to'rt xil servisni
  (streak, achievement, daily task, companion) alohida-alohida chaqirsangiz,
  kod chigallashadi. Buning o'rniga bitta emit() chaqiriladi va u hammasini
  to'g'ri tartibda ishga tushiradi, natijani frontend uchun bitta dict qilib qaytaradi.

Foydalanish (answer_service ichida):

    from .events import emit, Event

    # dars tugaganda:
    gamification = emit(Event.LESSON_COMPLETED, profile, xp_earned=15, is_perfect=True)
    # gamification dict'ini lesson-complete API javobiga qo'shib yuboring
"""
from enum import Enum

from . import (
    achievement_service,
    analytics_service,
    companion_service,
    daily_task_service,
    streak_service,
)


class Event(str, Enum):
    LESSON_COMPLETED = "lesson_completed"
    EXERCISE_ANSWERED = "exercise_answered"     # kwargs: is_correct
    WORD_REVIEWED = "word_reviewed"
    WORD_MASTERED = "word_mastered"
    PLACEMENT_COMPLETED = "placement_completed"
    XP_EARNED = "xp_earned"                     # kwargs: amount


def emit(event: Event, profile, **kwargs) -> dict:
    """Eventni qabul qilib, barcha gamification yangilanishlarini bajaradi.
    Frontend uchun yagona javob qaytaradi."""
    result = {
        "streak": None,
        "new_achievements": [],
        "daily_tasks_updated": [],
        "companion_message": None,
    }

    # ---- 0. Analytics jurnali (parent dashboard uchun) ----
    event_key = str(event.value if hasattr(event, "value") else event)
    analytics_service.record_event(profile, event_key, **kwargs)

    # ---- 1. Streak (faqat dars tugaganda) ----
    streak_result = None
    if event == Event.LESSON_COMPLETED:
        streak_result = streak_service.update_streak(profile)
        result["streak"] = {
            "current": streak_result.current_streak,
            "extended": streak_result.streak_extended,
            "freeze_used": streak_result.freeze_used,
            "lost": streak_result.streak_lost,
            "milestone": streak_result.milestone,
        }

    # ---- 2. Hisoblagichlarni yangilash (denormalizatsiya) ----
    update_fields = []
    if event == Event.LESSON_COMPLETED:
        profile.completed_lessons_count += 1
        update_fields.append("completed_lessons_count")
        if kwargs.get("is_perfect"):
            profile.perfect_lessons_count += 1
            update_fields.append("perfect_lessons_count")
    if event == Event.WORD_MASTERED:
        profile.mastered_words_count += 1
        update_fields.append("mastered_words_count")
    xp = kwargs.get("xp_earned", 0)
    if xp:
        profile.total_xp += xp
        update_fields.append("total_xp")
    if update_fields:
        profile.save(update_fields=update_fields)

    # ---- 3. Daily tasklar ----
    result["daily_tasks_updated"] = daily_task_service.apply_event(
        profile, event, **kwargs
    )

    # ---- 4. Achievementlar ----
    new_achievements = achievement_service.check_achievements(profile, event, **kwargs)
    result["new_achievements"] = [
        achievement_service.serialize(a, profile) for a in new_achievements
    ]

    # ---- 5. Companion reaktsiyasi ----
    result["companion_message"] = companion_service.react(
        profile,
        event,
        streak_result=streak_result,
        new_achievements=new_achievements,
        **kwargs,
    )

    return result