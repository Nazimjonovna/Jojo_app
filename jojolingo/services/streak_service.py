from dataclasses import dataclass
from datetime import timedelta
 
from django.utils import timezone
 
 
@dataclass
class StreakResult:
    current_streak: int
    streak_extended: bool      # bugun streak birinchi marta oshdimi (animatsiya uchun)
    freeze_used: bool
    streak_lost: bool          # streak yonib, yangidan boshlandimi
    milestone: int | None      # 3, 7, 14, 30, 50, 100 ... yetilgan bosqich
 
MILESTONES = (3, 7, 14, 30, 50, 100, 365)
 
 
def update_streak(profile) -> StreakResult:
    today = timezone.localdate()
    last = profile.last_activity_date
 
    streak_extended = False
    freeze_used = False
    streak_lost = False
 
    if last == today:
        # Bugun allaqachon hisoblangan
        return StreakResult(profile.current_streak, False, False, False, None)
 
    if last == today - timedelta(days=1):
        profile.current_streak += 1
        streak_extended = True
    elif last == today - timedelta(days=2) and profile.streak_freeze_count > 0:
        # Bir kun tushib qoldi, lekin freeze bor
        profile.streak_freeze_count -= 1
        profile.current_streak += 1
        freeze_used = True
        streak_extended = True
    else:
        streak_lost = profile.current_streak > 1
        profile.current_streak = 1
        streak_extended = True
 
    profile.last_activity_date = today
    profile.longest_streak = max(profile.longest_streak, profile.current_streak)
 
    milestone = profile.current_streak if (
        streak_extended and profile.current_streak in MILESTONES
    ) else None
 
    profile.save(update_fields=[
        "current_streak", "longest_streak",
        "last_activity_date", "streak_freeze_count",
    ])
 
    return StreakResult(
        current_streak=profile.current_streak,
        streak_extended=streak_extended,
        freeze_used=freeze_used,
        streak_lost=streak_lost,
        milestone=milestone,
    )
 
 
def is_streak_in_danger(profile) -> bool:
    """Frontend'da 'streak yonish arafasida' ogohlantirishi uchun:
    kecha o'qigan, bugun hali o'qimagan."""
    today = timezone.localdate()
    return (
        profile.current_streak > 0
        and profile.last_activity_date == today - timedelta(days=1)
    )
