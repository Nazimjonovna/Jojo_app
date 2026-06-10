from datetime import timedelta
 
from django.db.models import Avg, Count, F, Sum
from django.utils import timezone
 
from ..models import ChildDailyActivity
 
 
def record_event(profile, event_key: str, **kwargs) -> None:
    """Har bir o'quv eventida kunlik jurnalga yozadi."""
    today = timezone.localdate()
    activity, _ = ChildDailyActivity.objects.get_or_create(
        profile=profile, date=today
    )
 
    updates = {}
    if event_key == "lesson_completed":
        updates["lessons_completed"] = F("lessons_completed") + 1
        if kwargs.get("time_spent_seconds"):
            updates["time_spent_seconds"] = (
                F("time_spent_seconds") + int(kwargs["time_spent_seconds"])
            )
    elif event_key == "exercise_answered":
        updates["exercises_answered"] = F("exercises_answered") + 1
        if kwargs.get("is_correct"):
            updates["correct_answers"] = F("correct_answers") + 1
        else:
            updates["wrong_answers"] = F("wrong_answers") + 1
    elif event_key == "word_reviewed":
        updates["words_reviewed"] = F("words_reviewed") + 1
 
    xp = kwargs.get("xp_earned", 0)
    if xp:
        updates["xp_earned"] = F("xp_earned") + xp
 
    if updates:
        ChildDailyActivity.objects.filter(id=activity.id).update(**updates)
 
 
def get_overview(profile) -> dict:
    """Bola kartochkasi: asosiy ko'rsatkichlar bir qarashda."""
    last_30 = _activity_qs(profile, days=30).aggregate(
        xp=Sum("xp_earned"),
        lessons=Sum("lessons_completed"),
        time=Sum("time_spent_seconds"),
        active_days=Count("id"),
    )
    return {
        "current_level": getattr(profile, "current_level", None),
        "total_xp": profile.total_xp,
        "current_streak": profile.current_streak,
        "longest_streak": profile.longest_streak,
        "words_mastered": profile.mastered_words_count,
        "lessons_completed_total": profile.completed_lessons_count,
        "achievements_earned": profile.achievements.count(),
        "last_activity_date": profile.last_activity_date,
        "last_30_days": {
            "xp": last_30["xp"] or 0,
            "lessons": last_30["lessons"] or 0,
            "active_days": last_30["active_days"],
            "time_spent_minutes": round((last_30["time"] or 0) / 60),
        },
    }
 
 
def get_activity_chart(profile, days: int = 7) -> list[dict]:
    """Grafik uchun: har bir kun (faolliksiz kunlar 0 bilan to'ldiriladi)."""
    today = timezone.localdate()
    start = today - timedelta(days=days - 1)
 
    rows = {
        a.date: a
        for a in _activity_qs(profile, days=days)
    }
 
    chart = []
    for i in range(days):
        day = start + timedelta(days=i)
        a = rows.get(day)
        chart.append({
            "date": str(day),
            "xp": a.xp_earned if a else 0,
            "lessons": a.lessons_completed if a else 0,
            "time_minutes": round(a.time_spent_seconds / 60) if a else 0,
            "accuracy": a.accuracy if a else None,
        })
    return chart
 
 
def get_mistake_report(profile, days: int = 30, limit: int = 10) -> dict:
    """Eng ko'p xato qilinadigan joylar — ota-onaga 'qayerda qiynalayapti'."""
    from ..models import MistakeLog  # MOSLANG: import yo'li
 
    since = timezone.now() - timedelta(days=days)
    qs = MistakeLog.objects.filter(
        profile=profile,            # MOSLANG: FK nomi (child / profile)
        created_at__gte=since,      # MOSLANG: timestamp maydoni
    )
 
    # MOSLANG: guruhlash maydonlari — exercise__lesson__unit nomlari
    by_topic = (
        qs.values(topic=F("exercise__lesson__unit__title"))
        .annotate(count=Count("id"))
        .order_by("-count")[:limit]
    )
    by_type = (
        qs.values(error_type=F("mistake_type"))   # MOSLANG: xato turi maydoni
        .annotate(count=Count("id"))
        .order_by("-count")
    )
 
    total = qs.count()
    answered = _activity_qs(profile, days=days).aggregate(
        t=Sum("exercises_answered")
    )["t"] or 0
 
    return {
        "period_days": days,
        "total_mistakes": total,
        "error_rate_percent": round(total / answered * 100, 1) if answered else 0,
        "by_topic": list(by_topic),
        "by_type": list(by_type),
    }
 
 
def get_word_report(profile) -> dict:
    """So'z boyligi: yangi / o'rganilmoqda / o'zlashtirilgan taqsimoti."""
    from ..models import WordProgress  # MOSLANG: import yo'li
 
    qs = WordProgress.objects.filter(profile=profile)  # MOSLANG: FK nomi
 
    # MOSLANG: status maydoni nomi va qiymatlari
    breakdown = dict(
        qs.values_list("status").annotate(c=Count("id"))
    )
    due_today = qs.filter(
        next_review_at__lte=timezone.now()   # MOSLANG: spaced repetition maydoni
    ).count()
 
    return {
        "total_words_seen": qs.count(),
        "breakdown": breakdown,          # {"new": 12, "learning": 40, "mastered": 25}
        "due_for_review_today": due_today,
    }
 
 
def get_weekly_summary(profile) -> dict:
    """Haftalik xulosa — push notification / email uchun ham ishlatsa bo'ladi."""
    this_week = _aggregate_period(profile, days=7)
    prev_week = _aggregate_period(profile, days=7, offset=7)
 
    def trend(cur, prev):
        if not prev:
            return None
        return round((cur - prev) / prev * 100)
 
    return {
        "this_week": this_week,
        "previous_week": prev_week,
        "trends_percent": {
            "xp": trend(this_week["xp"], prev_week["xp"]),
            "lessons": trend(this_week["lessons"], prev_week["lessons"]),
            "time_minutes": trend(
                this_week["time_minutes"], prev_week["time_minutes"]
            ),
        },
    }
 
 
def _activity_qs(profile, days: int, offset: int = 0):
    end = timezone.localdate() - timedelta(days=offset)
    start = end - timedelta(days=days - 1)
    return ChildDailyActivity.objects.filter(
        profile=profile, date__gte=start, date__lte=end
    )
 
 
def _aggregate_period(profile, days: int, offset: int = 0) -> dict:
    agg = _activity_qs(profile, days, offset).aggregate(
        xp=Sum("xp_earned"),
        lessons=Sum("lessons_completed"),
        time=Sum("time_spent_seconds"),
        active_days=Count("id"),
        correct=Sum("correct_answers"),
        wrong=Sum("wrong_answers"),
    )
    correct = agg["correct"] or 0
    wrong = agg["wrong"] or 0
    return {
        "xp": agg["xp"] or 0,
        "lessons": agg["lessons"] or 0,
        "time_minutes": round((agg["time"] or 0) / 60),
        "active_days": agg["active_days"],
        "accuracy_percent": (
            round(correct / (correct + wrong) * 100, 1) if (correct + wrong) else None
        ),
    }