from django.db import transaction
 
from ..models import Achievement, ChildAchievement
 
# Qaysi event qaysi shartlarni tekshirishi kerak
_EVENT_CONDITIONS = {
    "lesson_completed": [
        Achievement.ConditionType.LESSONS_COMPLETED,
        Achievement.ConditionType.FIRST_LESSON,
        Achievement.ConditionType.STREAK_DAYS,
        Achievement.ConditionType.XP_TOTAL,
        Achievement.ConditionType.PERFECT_LESSONS,
    ],
    "word_mastered": [Achievement.ConditionType.WORDS_MASTERED],
    "placement_completed": [Achievement.ConditionType.PLACEMENT_DONE],
    "xp_earned": [Achievement.ConditionType.XP_TOTAL],
}
 
 
def _current_value(profile, condition_type: str) -> int:
    ct = Achievement.ConditionType
    mapping = {
        ct.LESSONS_COMPLETED: profile.completed_lessons_count,
        ct.FIRST_LESSON: profile.completed_lessons_count,
        ct.XP_TOTAL: profile.total_xp,
        ct.STREAK_DAYS: profile.current_streak,
        ct.WORDS_MASTERED: profile.mastered_words_count,
        ct.PERFECT_LESSONS: profile.perfect_lessons_count,
        ct.PLACEMENT_DONE: 1,  # event kelganining o'zi shart bajarilgani
        ct.COURSE_COMPLETED: getattr(profile, "completed_courses_count", 0),
    }
    return mapping.get(condition_type, 0)
 
 
@transaction.atomic
def check_achievements(profile, event, **kwargs) -> list[Achievement]:
    """Yangi qo'lga kiritilgan achievementlar ro'yxatini qaytaradi."""
    conditions = _EVENT_CONDITIONS.get(str(event.value if hasattr(event, "value") else event))
    if not conditions:
        return []
 
    already = set(
        ChildAchievement.objects.filter(profile=profile)
        .values_list("achievement_id", flat=True)
    )
 
    candidates = Achievement.objects.filter(
        condition_type__in=conditions, is_active=True
    ).exclude(id__in=already)
 
    earned = []
    for ach in candidates:
        if _current_value(profile, ach.condition_type) >= ach.threshold:
            ChildAchievement.objects.create(profile=profile, achievement=ach)
            if ach.xp_reward:
                profile.total_xp += ach.xp_reward
            earned.append(ach)
 
    if any(a.xp_reward for a in earned):
        profile.save(update_fields=["total_xp"])
 
    return earned
 
 
def serialize(achievement: Achievement, profile) -> dict:
    lang = getattr(profile, "native_language_code", "uz")
    return {
        "code": achievement.code,
        "title": achievement.title_for(lang),
        "description": getattr(achievement, f"description_{lang}", "") or achievement.description_uz,
        "icon": achievement.icon,
        "xp_reward": achievement.xp_reward,
    }
 
 
def list_for_profile(profile) -> list[dict]:
    """Profil sahifasi uchun: barcha achievementlar + qaysilari olingan."""
    earned = {
        ca.achievement_id: ca
        for ca in ChildAchievement.objects.filter(profile=profile)
    }
    items = []
    for ach in Achievement.objects.filter(is_active=True):
        ca = earned.get(ach.id)
        data = serialize(ach, profile)
        data.update({
            "earned": ca is not None,
            "earned_at": ca.earned_at.isoformat() if ca else None,
            "progress": min(_current_value(profile, ach.condition_type), ach.threshold),
            "threshold": ach.threshold,
        })
        items.append(data)
    return items
 
 
def mark_seen(profile):
    ChildAchievement.objects.filter(profile=profile, is_seen=False).update(is_seen=True)