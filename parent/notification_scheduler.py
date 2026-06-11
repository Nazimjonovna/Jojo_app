"""NotificationRule scheduler engine.

`compute_next_run(rule, after)` — kelajakdagi yaqin urinish vaqtini hisoblaydi.
`fire_rule(rule)` — endi vaqti bo'lgan rule ni ishga tushiradi: audience'ni
hisoblab, har bir foydalanuvchiga inbox + push + (ixtiyoriy) SMS yuboradi.
`tick()` — `manage.py send_scheduled_notifications` chaqirsa, hozir vaqti
yetgan barcha rule'larni topib `fire_rule()` qiladi.

Telefoniga to'g'ridan-to'g'ri bog'liq emas — `sms_service.sms_client` va
`services.record_parent_notification` (inbox + push) yordamida amalga
oshiriladi.
"""

from __future__ import annotations

import logging
from datetime import datetime, time, timedelta

from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils import timezone

from .models import NotificationRule, NotificationRuleLog, ParentChild

logger = logging.getLogger("jojo.notif_scheduler")
User = get_user_model()


# ---------------------------------------------------------------------------
# Trigger time computation
# ---------------------------------------------------------------------------


def compute_next_run(rule: NotificationRule, after: datetime | None = None) -> datetime | None:
    """`after` (default: now) dan keyingi yaqin `next_run_at` ni qaytaradi.

    `premium_expiry` rule'lari `next_run_at` ishlatmasdan har bir bola
    uchun alohida hisoblanadi — shu sababli har soatda tekshirish kifoya
    (qaytaramiz `after + 1h`).
    """
    after = after or timezone.now()
    p = rule.trigger_params or {}
    t = rule.trigger_type

    if t == NotificationRule.TRIGGER_PREMIUM:
        # Har soatda tekshirsa yetadi — auditoriyaga qarab dinamik
        return after + timedelta(hours=1)

    if t == NotificationRule.TRIGGER_DAILY:
        hour = int(p.get("hour", 9))
        minute = int(p.get("minute", 0))
        candidate = after.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if candidate <= after:
            candidate += timedelta(days=1)
        return candidate

    if t == NotificationRule.TRIGGER_WEEKLY:
        hour = int(p.get("hour", 9))
        minute = int(p.get("minute", 0))
        target_wd = int(p.get("weekday", 0))  # 0 = Monday
        candidate = after.replace(hour=hour, minute=minute, second=0, microsecond=0)
        days_ahead = (target_wd - candidate.weekday()) % 7
        if days_ahead == 0 and candidate <= after:
            days_ahead = 7
        return candidate + timedelta(days=days_ahead)

    if t == NotificationRule.TRIGGER_MONTHLY:
        hour = int(p.get("hour", 9))
        minute = int(p.get("minute", 0))
        day = max(1, min(28, int(p.get("day", 1))))
        candidate = after.replace(day=day, hour=hour, minute=minute, second=0, microsecond=0)
        if candidate <= after:
            # next month
            if candidate.month == 12:
                candidate = candidate.replace(year=candidate.year + 1, month=1)
            else:
                candidate = candidate.replace(month=candidate.month + 1)
        return candidate

    if t == NotificationRule.TRIGGER_ONE_OFF:
        raw = p.get("run_at")
        if not raw:
            return None
        try:
            dt = datetime.fromisoformat(str(raw))
            if timezone.is_naive(dt):
                dt = timezone.make_aware(dt)
        except (TypeError, ValueError):
            return None
        if dt <= after:
            return None  # allaqachon ishlatilgan/o'tib ketgan
        return dt

    return None


# ---------------------------------------------------------------------------
# Audience resolution
# ---------------------------------------------------------------------------


def resolve_audience(rule: NotificationRule):
    """Qaysi parent foydalanuvchilarga bu rule yuborilishi kerakligini
    qaytaradi. Generator: bir vaqtning o'zida ko'p user'ni xotirada saqlamaslik
    uchun `iterator()` ishlatamiz."""

    base = User.objects.filter(role=User.ROLE_PARENT, is_active=True)
    p = rule.audience_params or {}
    now = timezone.now()

    a = rule.audience
    if a == NotificationRule.AUDIENCE_ALL:
        qs = base
    elif a == NotificationRule.AUDIENCE_PREMIUM:
        qs = base.filter(is_premium=True).filter(
            Q(premium_expires_at__isnull=True) | Q(premium_expires_at__gt=now)
        )
    elif a == NotificationRule.AUDIENCE_EXPIRING:
        days = int(p.get("days", 7))
        cutoff = now + timedelta(days=days)
        qs = base.filter(
            is_premium=True,
            premium_expires_at__isnull=False,
            premium_expires_at__gt=now,
            premium_expires_at__lte=cutoff,
        )
    elif a == NotificationRule.AUDIENCE_FREE:
        qs = base.filter(Q(is_premium=False) | Q(premium_expires_at__lte=now))
    elif a == NotificationRule.AUDIENCE_NO_CHILD:
        # bola ulanmagan parents: ParentChild aktiv yozuvi yo'q
        linked = ParentChild.objects.values_list("parent_id", flat=True)
        qs = base.exclude(id__in=linked)
    else:
        qs = base.none()

    return qs.iterator(chunk_size=200)


# ---------------------------------------------------------------------------
# Premium-expiry — har bir aktiv premium parentni tekshirib o'tamiz
# ---------------------------------------------------------------------------


def _premium_expiry_targets(rule: NotificationRule):
    """Premium tugashidan `days_before` kun qolgan parent'larni qaytaradi."""
    p = rule.trigger_params or {}
    days_before = max(0, int(p.get("days_before", 3)))
    now = timezone.now()
    # `days_before` kun ichida tugaydigan, lekin allaqachon tugamagan,
    # va shu rule oxirgi marta yuborilganidan keyin yana muddati boshqacha bo'lib qolmagan.
    # Sodda implementatsiya: target oraliq [now, now + days_before+1)
    window_start = now
    window_end = now + timedelta(days=days_before + 1)
    return (
        User.objects.filter(
            role=User.ROLE_PARENT,
            is_active=True,
            is_premium=True,
            premium_expires_at__isnull=False,
            premium_expires_at__gte=window_start,
            premium_expires_at__lt=window_end,
        )
        .iterator(chunk_size=200)
    )


# ---------------------------------------------------------------------------
# Format / substitute
# ---------------------------------------------------------------------------


def _format_text(text: str, parent, *, days_left: int | None = None) -> str:
    """`{name}`, `{phone}`, `{days_left}` o'rnida foydalanuvchi qiymatlarini
    qo'yamiz. Mavjud bo'lmagan kalitlar bo'sh string'ga aylanadi."""
    ctx = {
        "name": parent.full_name or parent.first_name or "Hurmatli foydalanuvchi",
        "phone": parent.phone or "",
        "days_left": str(days_left) if days_left is not None else "",
    }
    out = text
    for k, v in ctx.items():
        out = out.replace("{" + k + "}", v)
    return out


# ---------------------------------------------------------------------------
# Firing
# ---------------------------------------------------------------------------


def fire_rule(rule: NotificationRule) -> NotificationRuleLog:
    """Rule'ni hozir ishga tushiradi va NotificationRuleLog yaratadi."""
    from .services import record_parent_notification
    from .sms_service import sms_client

    push_sent = 0
    sms_sent = 0
    recipients = 0
    sms_phones: list[str] = []
    error_detail = ""

    try:
        if rule.trigger_type == NotificationRule.TRIGGER_PREMIUM:
            iterator = _premium_expiry_targets(rule)
        else:
            iterator = resolve_audience(rule)

        for parent in iterator:
            recipients += 1
            days_left = None
            if rule.trigger_type == NotificationRule.TRIGGER_PREMIUM and parent.premium_expires_at:
                delta = parent.premium_expires_at - timezone.now()
                days_left = max(0, delta.days)
            # Parent tili bo'yicha tegishli matnni tanlaymiz; bo'sh bo'lsa uz.
            parent_lang = (getattr(parent, "language", "") or "uz").lower()
            if parent_lang.startswith("ru"):
                base_title = rule.title_ru or rule.title
                base_body = rule.body_ru or rule.body
            elif parent_lang.startswith("en"):
                base_title = rule.title_en or rule.title
                base_body = rule.body_en or rule.body
            else:
                base_title = rule.title
                base_body = rule.body
            title = _format_text(base_title, parent, days_left=days_left)
            body = _format_text(base_body, parent, days_left=days_left)

            if rule.send_push:
                try:
                    notif = record_parent_notification(
                        parent=parent,
                        child=None,
                        category=rule.category or "system",
                        title=title,
                        body=body,
                        data={"rule_id": rule.id},
                    )
                    # Boshqa tillarni ham yozib qo'yamiz — parent tilni o'zgartirsa
                    # tarixdagi xabar ham mos tilda ko'rinadi.
                    if notif:
                        changed = False
                        if rule.title_ru:
                            tr = _format_text(rule.title_ru, parent, days_left=days_left)
                            if tr != notif.title_ru:
                                notif.title_ru = tr
                                changed = True
                        if rule.title_en:
                            tr = _format_text(rule.title_en, parent, days_left=days_left)
                            if tr != notif.title_en:
                                notif.title_en = tr
                                changed = True
                        if rule.body_ru:
                            tr = _format_text(rule.body_ru, parent, days_left=days_left)
                            if tr != notif.body_ru:
                                notif.body_ru = tr
                                changed = True
                        if rule.body_en:
                            tr = _format_text(rule.body_en, parent, days_left=days_left)
                            if tr != notif.body_en:
                                notif.body_en = tr
                                changed = True
                        if changed:
                            notif.save(update_fields=["title_ru", "title_en", "body_ru", "body_en"])
                    push_sent += 1
                except Exception as e:
                    logger.warning("rule %s push failed for %s: %s", rule.id, parent.id, e)

            if rule.send_sms and parent.phone:
                sms_phones.append(parent.phone)
                # Per-parent SMS uchun individual matn kerak (template'da
                # `{name}` bor bo'lishi mumkin). Bittadan yuboramiz.
                if sms_client.send(
                    parent.phone,
                    f"{title}\n{body}"[:500],
                    kind="rule",
                    user_id=parent.id,
                ):
                    sms_sent += 1

        success = True
    except Exception as e:
        logger.exception("rule %s fire failed: %s", rule.id, e)
        success = False
        error_detail = str(e)[:500]

    now = timezone.now()
    rule.last_run_at = now
    if rule.trigger_type == NotificationRule.TRIGGER_ONE_OFF:
        rule.is_active = False
        rule.next_run_at = None
    else:
        rule.next_run_at = compute_next_run(rule, after=now)
    rule.save(update_fields=["last_run_at", "next_run_at", "is_active"])

    return NotificationRuleLog.objects.create(
        rule=rule,
        recipients_count=recipients,
        push_sent=push_sent,
        sms_sent=sms_sent,
        success=success,
        detail=error_detail,
    )


# ---------------------------------------------------------------------------
# Tick — cron entry point
# ---------------------------------------------------------------------------


def tick():
    """Hozir vaqti yetgan barcha rule'larni topib ishga tushiradi.

    Har daqiqa cron orqali chaqirilishi mumkin. Ko'p workerli sharoitda
    bir rule ikki marta yuborilmasligi uchun `select_for_update`
    ishlatamiz."""
    from django.db import transaction
    now = timezone.now()
    fired = 0
    with transaction.atomic():
        due = (
            NotificationRule.objects
            .select_for_update(skip_locked=True)
            .filter(is_active=True, next_run_at__isnull=False, next_run_at__lte=now)
            [:50]
        )
        for rule in due:
            fire_rule(rule)
            fired += 1
    return fired
