import random
 
from django.db import models
 
from ..models import (
    AICompanion,
    ChildCompanionState,
    CompanionMessageTemplate,
)
 
Trigger = CompanionMessageTemplate.Trigger
Mood = ChildCompanionState.Mood
 
FRIENDSHIP_XP_PER_LESSON = 5
FRIENDSHIP_LEVEL_STEP = 50  # har 50 friendship_xp = +1 level
 
 
def get_or_create_state(profile) -> ChildCompanionState:
    state = getattr(profile, "companion_state", None)
    if state:
        return state
    default = AICompanion.objects.filter(is_active=True).first()
    if default is None:
        raise RuntimeError("Hech qanday AICompanion mavjud emas — seed qiling")
    return ChildCompanionState.objects.create(profile=profile, companion=default)
 
 
def select_companion(profile, companion_code: str) -> ChildCompanionState:
    companion = AICompanion.objects.get(code=companion_code, is_active=True)
    state = get_or_create_state(profile)
    state.companion = companion
    state.save(update_fields=["companion", "last_interaction"])
    return state
 
 
def react(profile, event, streak_result=None, new_achievements=None, **kwargs) -> dict | None:
    """events.emit() dan chaqiriladi. Eng muhim trigger'ni tanlab,
    bitta xabar qaytaradi (bolani xabarlar bilan ko'mib tashlamaslik uchun)."""
    event_key = str(event.value if hasattr(event, "value") else event)
    state = get_or_create_state(profile)
 
    # Trigger ustuvorligi: achievement > streak milestone > perfect > oddiy
    trigger = None
    context = {}
 
    if new_achievements:
        trigger = Trigger.ACHIEVEMENT
        context["achievement"] = new_achievements[0].title_for(
            getattr(profile, "native_language_code", "uz")
        )
    elif streak_result and streak_result.milestone:
        trigger = Trigger.STREAK_MILESTONE
        context["streak"] = streak_result.milestone
    elif event_key == "lesson_completed":
        trigger = Trigger.PERFECT_LESSON if kwargs.get("is_perfect") else Trigger.LESSON_COMPLETE
        # do'stlik XP
        state.friendship_xp += FRIENDSHIP_XP_PER_LESSON
        new_level = state.friendship_xp // FRIENDSHIP_LEVEL_STEP + 1
        if new_level > state.friendship_level:
            state.friendship_level = new_level
        state.save(update_fields=["friendship_xp", "friendship_level", "last_interaction"])
    elif event_key == "exercise_answered" and not kwargs.get("is_correct", True):
        trigger = Trigger.MISTAKE
    else:
        return None
 
    return get_message(profile, state, trigger, **context)
 
 
def get_message(profile, state: ChildCompanionState, trigger: str, **context) -> dict | None:
    lang = getattr(profile, "native_language_code", "uz")
 
    templates = list(
        CompanionMessageTemplate.objects.filter(trigger=trigger, is_active=True)
        .filter(models.Q(companion=state.companion) | models.Q(companion__isnull=True))
    )
    if not templates:
        return None
 
    weights = [t.weight for t in templates]
    template = random.choices(templates, weights=weights, k=1)[0]
 
    text = getattr(template, f"text_{lang}", "") or template.text_uz
    name = getattr(state.companion, f"name_{lang}", "") or state.companion.name_uz
    text = text.format(
        child_name=getattr(profile, "child_name", "do'stim"),
        companion_name=name,
        streak=context.get("streak", state.profile.current_streak),
        achievement=context.get("achievement", ""),
        xp=getattr(profile, "total_xp", 0),
    )
 
    # Mood yangilash
    if state.mood != template.mood_after:
        state.mood = template.mood_after
        state.save(update_fields=["mood", "last_interaction"])
 
    return {
        "companion": state.companion.code,
        "companion_name": name,
        "avatar": state.companion.avatar,
        "mood": state.mood,
        "text": text,
        "friendship_level": state.friendship_level,
    }
 
 
def greeting(profile) -> dict | None:
    """Bola ilovani ochganda: kunlik salom yoki comeback xabari."""
    from . import streak_service
    from django.utils import timezone
    from datetime import timedelta
 
    state = get_or_create_state(profile)
    last = profile.last_activity_date
    today = timezone.localdate()
 
    if last and last < today - timedelta(days=3):
        trigger = Trigger.COMEBACK
    elif streak_service.is_streak_in_danger(profile):
        trigger = Trigger.STREAK_DANGER
    else:
        trigger = Trigger.DAILY_GREETING
 
    return get_message(profile, state, trigger)
 