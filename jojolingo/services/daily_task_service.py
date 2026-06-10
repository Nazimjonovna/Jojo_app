import random
 
from django.db import transaction
from django.utils import timezone
 
from ..models import ChildDailyTask, DailyTaskTemplate
 
TASKS_PER_DAY = 3
 
# Event -> qaysi task turi progressini oshiradi
_EVENT_TASK_MAP = {
    "lesson_completed": DailyTaskTemplate.TaskType.COMPLETE_LESSONS,
    "word_reviewed": DailyTaskTemplate.TaskType.REVIEW_WORDS,
}
 
 
@transaction.atomic
def get_or_create_today(profile) -> list[ChildDailyTask]:
    today = timezone.localdate()
    existing = list(
        ChildDailyTask.objects.filter(profile=profile, date=today)
        .select_related("template")
    )
    if existing:
        return existing
 
    templates = list(DailyTaskTemplate.objects.filter(is_active=True))
    # Level filtri (oddiy string solishtirish A0 < A1 < A2 < B1 uchun ishlaydi)
    level = getattr(profile, "current_level", None)
    if level:
        templates = [
            t for t in templates
            if (not t.min_level or t.min_level <= level)
            and (not t.max_level or level <= t.max_level)
        ]
    if not templates:
        return []
 
    # Har xil task_type'lardan tanlashga harakat qilamiz
    chosen: list[DailyTaskTemplate] = []
    by_type: dict[str, list[DailyTaskTemplate]] = {}
    for t in templates:
        by_type.setdefault(t.task_type, []).append(t)
 
    types = list(by_type.keys())
    random.shuffle(types)
    for task_type in types[:TASKS_PER_DAY]:
        pool = by_type[task_type]
        weights = [t.weight for t in pool]
        chosen.append(random.choices(pool, weights=weights, k=1)[0])
 
    # Tur yetmasa, qolganini takror turlardan to'ldiramiz
    while len(chosen) < min(TASKS_PER_DAY, len(templates)):
        extra = random.choice(templates)
        if extra not in chosen:
            chosen.append(extra)
 
    tasks = [
        ChildDailyTask(
            profile=profile,
            template=t,
            date=today,
            target=t.target_value,
            xp_reward=t.xp_reward,
        )
        for t in chosen
    ]
    ChildDailyTask.objects.bulk_create(tasks)
    return list(
        ChildDailyTask.objects.filter(profile=profile, date=today)
        .select_related("template")
    )
 
 
def apply_event(profile, event, **kwargs) -> list[dict]:
    """Event kelganda bugungi tasklar progressini oshiradi.
    O'zgargan tasklar ro'yxatini (dict) qaytaradi."""
    event_key = str(event.value if hasattr(event, "value") else event)
 
    tasks = get_or_create_today(profile)
    updated = []
 
    for task in tasks:
        if task.is_completed:
            continue
 
        increment = 0
        task_type = task.template.task_type
 
        if _EVENT_TASK_MAP.get(event_key) == task_type:
            increment = 1
        elif task_type == DailyTaskTemplate.TaskType.EARN_XP:
            increment = kwargs.get("xp_earned", 0)
        elif (
            task_type == DailyTaskTemplate.TaskType.PERFECT_EXERCISES
            and event_key == "exercise_answered"
            and kwargs.get("is_correct")
        ):
            increment = 1
 
        if not increment:
            continue
 
        task.progress = min(task.progress + increment, task.target)
        fields = ["progress"]
        if task.progress >= task.target:
            task.completed_at = timezone.now()
            fields.append("completed_at")
        task.save(update_fields=fields)
        updated.append(serialize(task, profile))
 
    return updated
 
 
@transaction.atomic
def claim_reward(profile, task_id: int) -> dict:
    task = ChildDailyTask.objects.select_for_update().get(
        id=task_id, profile=profile
    )
    if not task.is_completed:
        raise ValueError("Task hali tugatilmagan")
    if task.reward_claimed:
        raise ValueError("Mukofot allaqachon olingan")
 
    task.reward_claimed = True
    task.save(update_fields=["reward_claimed"])
    profile.total_xp += task.xp_reward
    profile.save(update_fields=["total_xp"])
    return {"xp_added": task.xp_reward, "total_xp": profile.total_xp}
 
 
def serialize(task: ChildDailyTask, profile) -> dict:
    lang = getattr(profile, "native_language_code", "uz")
    title = getattr(task.template, f"title_{lang}", "") or task.template.title_uz
    return {
        "id": task.id,
        "type": task.template.task_type,
        "title": title.format(n=task.target),
        "progress": task.progress,
        "target": task.target,
        "completed": task.is_completed,
        "xp_reward": task.xp_reward,
        "reward_claimed": task.reward_claimed,
    }
 