"""Telegram bot — qo'llab-quvvatlash xizmati.

Suhbat oqimi:
    1. /start  → tilni tanlash (inline keyboard)
    2. til tanlandi → ticket yaratiladi, foydalanuvchi murojaatini yozadi
    3. operator adminkadan javob beradi → bot foydalanuvchiga uzatadi
    4. operator ticket'ni `resolved` qiladi → bot 1..5 yulduzli baho so'raydi
    5. foydalanuvchi baho beradi → ticket `closed` + `rated_at` yoziladi

Til, FSM holati, baho — hammasi `CallCenterTicket` da saqlanadi, alohida
sessiya modeliga ehtiyoj yo'q (bitta chat — bitta aktiv ticket).
"""

import logging
import requests

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)
TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"


# ----------------------------------------------------------------------------
# Lokalizatsiya — bot foydalanuvchiga ko'rsatadigan matnlar
# ----------------------------------------------------------------------------

LANG_LABELS = {
    "uz_latn": "🇺🇿 O‘zbek",
    "uz_cyrl": "🇺🇿 Ўзбек",
    "ru": "🇷🇺 Русский",
    "en": "🇬🇧 English",
}


I18N = {
    "uz_latn": {
        "welcome": (
            "Assalomu alaykum! Iltimos, qulay tilingizni tanlang —\n"
            "operatorlarimiz aynan shu tilda javob beradi."
        ),
        "language_saved": (
            "✅ Til tanlandi.\n\n"
            "Savol yoki murojaatingizni yozib qoldiring — "
            "operatorlarimiz tez orada javob beradi."
        ),
        "ticket_closed_intro": (
            "Murojaatingiz hal qilindi 🎉\n\n"
            "Muammoyingiz hal etildimi? Bizning xizmatimizni 1 dan 10 "
            "ballgacha baholang:"
        ),
        "rating_thanks": "Bahoyingiz uchun rahmat! 🙏",
        "rating_skip": "Bo‘ldi, rahmat!",
        "phone_saved": "Rahmat! Raqamingiz qabul qilindi.",
        "skip_button": "O‘tkazib yuborish",
        "session_done_new": (
            "Avvalgi murojaatingiz yakunlangan. /start bosib yangi suhbat boshlang."
        ),
    },
    "uz_cyrl": {
        "welcome": (
            "Ассалому алайкум! Илтимос, қулай тилингизни танланг —\n"
            "операторларимиз айнан шу тилда жавоб беради."
        ),
        "language_saved": (
            "✅ Тил танланди.\n\n"
            "Савол ёки мурожаатингизни ёзиб қолдиринг — "
            "операторларимиз тез орада жавоб беради."
        ),
        "ticket_closed_intro": (
            "Мурожаатингиз ҳал қилинди 🎉\n\n"
            "Муаммоингиз ҳал этилдими? Бизнинг хизматимизни 1 дан 10 "
            "баллгача баҳоланг:"
        ),
        "rating_thanks": "Баҳойингиз учун раҳмат! 🙏",
        "rating_skip": "Бўлди, раҳмат!",
        "phone_saved": "Раҳмат! Рақамингиз қабул қилинди.",
        "skip_button": "Ўтказиб юбориш",
        "session_done_new": (
            "Аввалги мурожаатингиз якунланган. /start босиб янги суҳбат бошланг."
        ),
    },
    "ru": {
        "welcome": (
            "Здравствуйте! Пожалуйста, выберите удобный язык —\n"
            "наши операторы ответят именно на нём."
        ),
        "language_saved": (
            "✅ Язык выбран.\n\n"
            "Напишите ваш вопрос или обращение — "
            "оператор ответит в ближайшее время."
        ),
        "ticket_closed_intro": (
            "Ваше обращение решено 🎉\n\n"
            "Решена ли ваша проблема? Оцените нашу работу "
            "по шкале от 1 до 10:"
        ),
        "rating_thanks": "Спасибо за оценку! 🙏",
        "rating_skip": "Хорошо, спасибо!",
        "phone_saved": "Спасибо! Номер получен.",
        "skip_button": "Пропустить",
        "session_done_new": (
            "Прошлое обращение закрыто. Нажмите /start, чтобы начать новое."
        ),
    },
    "en": {
        "welcome": (
            "Hello! Please choose your preferred language —\n"
            "our operators will reply in the language you pick."
        ),
        "language_saved": (
            "✅ Language saved.\n\n"
            "Send your question or request — "
            "an operator will reply shortly."
        ),
        "ticket_closed_intro": (
            "Your request has been resolved 🎉\n\n"
            "Was your issue solved? Rate our service on a scale from "
            "1 to 10:"
        ),
        "rating_thanks": "Thanks for your rating! 🙏",
        "rating_skip": "Alright, thank you!",
        "phone_saved": "Thanks! Phone number saved.",
        "skip_button": "Skip",
        "session_done_new": (
            "Your previous request is closed. Tap /start to begin a new chat."
        ),
    },
}


def t(language, key):
    """Lokalizatsiyalangan matnni qaytaradi, fallback uz_latn."""
    return (
        I18N.get(language or "", {}).get(key)
        or I18N["uz_latn"].get(key)
        or ""
    )


def _token():
    return getattr(settings, "TELEGRAM_BOT_TOKEN", "")


# ----------------------------------------------------------------------------
# Quyi darajadagi Telegram API yordamchilari
# ----------------------------------------------------------------------------

def _tg_call(method, payload):
    token = _token()
    if not token:
        logger.warning("TELEGRAM_BOT_TOKEN yo'q. Telegram chaqiriq tashlandi: %s", method)
        return None
    url = TELEGRAM_API.format(token=token, method=method)
    try:
        r = requests.post(
            url,
            json=payload,
            timeout=10,
            verify=getattr(settings, "TELEGRAM_VERIFY_SSL", True),
        )
        data = r.json()
        if not data.get("ok"):
            logger.error("Telegram %s xato: %s", method, data)
            return None
        return data.get("result")
    except requests.RequestException as e:
        logger.error("Telegram ulanish xatosi (%s): %s", method, e)
        return None


def tg_send_message(chat_id, text, reply_markup=None):
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    res = _tg_call("sendMessage", payload)
    return (res or {}).get("message_id") if res else None


def tg_edit_message(chat_id, message_id, text, reply_markup=None):
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "parse_mode": "HTML",
    }
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    return _tg_call("editMessageText", payload)


def tg_answer_callback(callback_id, text=""):
    return _tg_call("answerCallbackQuery", {
        "callback_query_id": callback_id,
        "text": text or "",
    })


# ----------------------------------------------------------------------------
# Inline keyboardlar — til tanlash & baholash
# ----------------------------------------------------------------------------

def _language_keyboard():
    """Til tanlash uchun 2x2 inline keyboard."""
    return {
        "inline_keyboard": [
            [
                {"text": LANG_LABELS["uz_latn"], "callback_data": "lang:uz_latn"},
                {"text": LANG_LABELS["uz_cyrl"], "callback_data": "lang:uz_cyrl"},
            ],
            [
                {"text": LANG_LABELS["ru"], "callback_data": "lang:ru"},
                {"text": LANG_LABELS["en"], "callback_data": "lang:en"},
            ],
        ]
    }


def _rating_keyboard(ticket_id, language):
    """1..10 raqamli baho + skip tugmasi.

    Inline keyboard 2 qatorda joylashadi (1-5, 6-10) — telegramda
    har bir tugma kichkina, lekin ko'rinarli. Pastdan "O'tkazib
    yuborish" tugmasi.
    """
    row1 = [
        {"text": str(n), "callback_data": f"rate:{ticket_id}:{n}"}
        for n in range(1, 6)
    ]
    row2 = [
        {"text": str(n), "callback_data": f"rate:{ticket_id}:{n}"}
        for n in range(6, 11)
    ]
    skip_row = [{
        "text": t(language, "skip_button"),
        "callback_data": f"rate:{ticket_id}:skip",
    }]
    return {"inline_keyboard": [row1, row2, skip_row]}


# ----------------------------------------------------------------------------
# Yuqori darajadagi yordamchilar
# ----------------------------------------------------------------------------

def _normalize_phone(phone):
    if not phone:
        return phone
    phone = phone.strip().replace(" ", "")
    return phone if phone.startswith("+") else "+" + phone


def _broadcast_ticket(ticket, *, kind="updated"):
    """Adminkaga real-time event yuborish."""
    try:
        from .admin_views import _lead_to_dict
        from .realtime import broadcast_lead_changed
        broadcast_lead_changed({
            "type": kind,
            "id": ticket.id,
            "lead": _lead_to_dict(ticket),
        })
    except Exception:
        logger.exception("broadcast_lead_changed xato")


def _broadcast_comment(ticket, comment):
    try:
        from .admin_views import _comment_to_dict
        from .realtime import broadcast_lead_comment
        broadcast_lead_comment({
            "ticket_id": ticket.id,
            "comment": _comment_to_dict(comment),
        })
    except Exception:
        logger.exception("broadcast_lead_comment xato")


def _active_ticket_for_chat(chat_id):
    """Shu telegram chat uchun aktiv ticket (resolved/closed bo'lmagan)."""
    from .models import CallCenterTicket
    return (
        CallCenterTicket.objects
        .filter(telegram_chat_id=str(chat_id))
        .exclude(status__in=[CallCenterTicket.STATUS_CLOSED])
        .order_by("-updated_at")
        .first()
    )


def _create_ticket_for_chat(chat_id, *, tg_name, tg_username, linked_parent=None):
    """Yangi ticket yaratadi — til tanlashga kutadi."""
    from .models import CallCenterTicket
    return CallCenterTicket.objects.create(
        parent=linked_parent,
        source=CallCenterTicket.SOURCE_TELEGRAM,
        telegram_chat_id=str(chat_id),
        telegram_username=tg_username or "",
        telegram_name=tg_name or "",
        title=f"Telegram: {tg_name or 'foydalanuvchi'}",
        status=CallCenterTicket.STATUS_NEW,
        bot_state=CallCenterTicket.BOT_STATE_AWAITING_LANGUAGE,
    )


# ----------------------------------------------------------------------------
# Operator → user (resolved bo'lganda baho so'rash)
# ----------------------------------------------------------------------------

def request_rating(ticket):
    """Ticket resolved bo'lsa — botga baho so'rovini yuboramiz."""
    if not ticket.telegram_chat_id:
        return False
    if ticket.bot_state == ticket.BOT_STATE_AWAITING_RATING:
        return False
    lang = ticket.language or "uz_latn"
    text = t(lang, "ticket_closed_intro")
    tg_send_message(
        ticket.telegram_chat_id,
        text,
        reply_markup=_rating_keyboard(ticket.id, lang),
    )
    ticket.bot_state = ticket.BOT_STATE_AWAITING_RATING
    ticket.save(update_fields=["bot_state", "updated_at"])
    _broadcast_ticket(ticket, kind="updated")
    return True


# ----------------------------------------------------------------------------
# Webhook update handler
# ----------------------------------------------------------------------------

def handle_telegram_update(update: dict):
    """Telegram webhook'idan kelgan har qanday update'ni qayta ishlaydi."""
    if not update:
        return
    if "callback_query" in update:
        return _handle_callback(update["callback_query"])
    message = update.get("message") or update.get("edited_message")
    if message:
        return _handle_message(message)


def _handle_callback(cq):
    """Inline tugma bosilganda."""
    from .models import CallCenterTicket
    callback_id = cq.get("id")
    data = cq.get("data") or ""
    message = cq.get("message") or {}
    chat = message.get("chat", {})
    chat_id = str(chat.get("id"))
    message_id = message.get("message_id")
    from_user = cq.get("from", {})

    # ---- Til tanlash ----
    if data.startswith("lang:"):
        lang = data.split(":", 1)[1]
        if lang not in dict(CallCenterTicket.LANGUAGE_CHOICES):
            tg_answer_callback(callback_id, "Unknown language")
            return

        ticket = _active_ticket_for_chat(chat_id)
        if not ticket:
            tg_name = (
                f"{from_user.get('first_name', '')} {from_user.get('last_name', '')}".strip()
                or "Telegram foydalanuvchi"
            )
            ticket = _create_ticket_for_chat(
                chat_id,
                tg_name=tg_name,
                tg_username=from_user.get("username") or "",
            )

        ticket.language = lang
        ticket.bot_state = CallCenterTicket.BOT_STATE_CHATTING
        ticket.save(update_fields=["language", "bot_state", "updated_at"])
        _broadcast_ticket(ticket, kind="updated")

        tg_answer_callback(callback_id, LANG_LABELS.get(lang, ""))
        if message_id:
            tg_edit_message(
                chat_id,
                message_id,
                f"{LANG_LABELS.get(lang, '')}\n\n{t(lang, 'language_saved')}",
            )
        else:
            tg_send_message(chat_id, t(lang, "language_saved"))
        return

    # ---- Baho ----
    if data.startswith("rate:"):
        parts = data.split(":")
        if len(parts) != 3:
            tg_answer_callback(callback_id)
            return
        _, raw_ticket_id, value = parts
        try:
            ticket_id = int(raw_ticket_id)
        except ValueError:
            tg_answer_callback(callback_id)
            return
        ticket = CallCenterTicket.objects.filter(id=ticket_id).first()
        if not ticket:
            tg_answer_callback(callback_id, "Ticket not found")
            return
        lang = ticket.language or "uz_latn"

        if value == "skip":
            ticket.bot_state = CallCenterTicket.BOT_STATE_DONE
            if ticket.status != CallCenterTicket.STATUS_CLOSED:
                ticket.status = CallCenterTicket.STATUS_CLOSED
                ticket.closed_at = timezone.now()
            ticket.save(update_fields=["bot_state", "status", "closed_at", "updated_at"])
            tg_answer_callback(callback_id, t(lang, "rating_skip"))
            if message_id:
                tg_edit_message(chat_id, message_id, t(lang, "rating_skip"))
            _broadcast_ticket(ticket, kind="updated")
            return

        try:
            rating = int(value)
        except ValueError:
            tg_answer_callback(callback_id)
            return
        if not 1 <= rating <= 10:
            tg_answer_callback(callback_id)
            return

        ticket.rating = rating
        ticket.rated_at = timezone.now()
        ticket.bot_state = CallCenterTicket.BOT_STATE_DONE
        if ticket.status != CallCenterTicket.STATUS_CLOSED:
            ticket.status = CallCenterTicket.STATUS_CLOSED
            ticket.closed_at = timezone.now()
        ticket.save(update_fields=[
            "rating", "rated_at", "bot_state", "status", "closed_at", "updated_at",
        ])

        # Vizual feedback — 1-10 ballik bahoda yulduzlar 1:2 nisbatda.
        stars = "⭐" * max(1, round(rating / 2))
        thanks = f"{stars}  {rating}/10\n{t(lang, 'rating_thanks')}"
        tg_answer_callback(callback_id, t(lang, "rating_thanks"))
        if message_id:
            tg_edit_message(chat_id, message_id, thanks)
        _broadcast_ticket(ticket, kind="rated")
        return

    tg_answer_callback(callback_id)


def _handle_message(message):
    """Oddiy text / contact xabari."""
    from .models import CallCenterTicket, CallCenterComment, User

    chat = message.get("chat", {})
    chat_id = str(chat.get("id"))
    from_user = message.get("from", {})
    text = (message.get("text") or message.get("caption") or "").strip()
    contact = message.get("contact")

    tg_name = (
        f"{from_user.get('first_name', '')} {from_user.get('last_name', '')}".strip()
        or chat.get("title")
        or "Telegram foydalanuvchi"
    )
    tg_username = from_user.get("username") or ""

    # /start — yangi sessiya, til tanlatamiz
    if text.startswith("/start"):
        ticket = _active_ticket_for_chat(chat_id)
        if not ticket:
            ticket = _create_ticket_for_chat(
                chat_id,
                tg_name=tg_name,
                tg_username=tg_username,
            )
            _broadcast_ticket(ticket, kind="created")
        else:
            ticket.bot_state = CallCenterTicket.BOT_STATE_AWAITING_LANGUAGE
            ticket.save(update_fields=["bot_state", "updated_at"])
            _broadcast_ticket(ticket, kind="updated")

        # Operator chat panel'ida foydalanuvchi /start bosganini ko'rsin —
        # aks holda yangi tikkitlar chat paneli bo'sh ko'rinadi va operator
        # "tizim ishlamayapti" deb gumon qiladi.
        try:
            start_comment = CallCenterComment.objects.create(
                ticket=ticket,
                operator=None,
                comment=text or "/start",
                direction=CallCenterComment.DIRECTION_IN,
                old_status=ticket.status,
                new_status=ticket.status,
                telegram_message_id=str(message.get("message_id", "")),
            )
            _broadcast_comment(ticket, start_comment)
        except Exception:
            # Comment seed muvaffaqiyatsiz bo'lsa ham asosiy oqim davom etsin.
            pass

        lang_hint = ticket.language or "uz_latn"
        welcome_text = t(lang_hint, "welcome")
        tg_send_message(
            chat_id,
            welcome_text,
            reply_markup=_language_keyboard(),
        )
        # Bot tomondan yuborilgan xush kelibsiz xabarini ham ticketga yozamiz —
        # admin chat tarixi to'liq bo'lsin (haqiqiy Telegram chat bilan moslashsin).
        try:
            bot_comment = CallCenterComment.objects.create(
                ticket=ticket,
                operator=None,
                comment=welcome_text,
                direction=CallCenterComment.DIRECTION_OUT,
                old_status=ticket.status,
                new_status=ticket.status,
            )
            _broadcast_comment(ticket, bot_comment)
        except Exception:
            pass
        _broadcast_ticket(ticket, kind="updated")
        return

    # Raqam ulashilsa — parent bilan bog'laymiz
    linked_parent = None
    if contact and contact.get("phone_number"):
        norm = _normalize_phone(contact["phone_number"])
        linked_parent = (
            User.objects.filter(phone=norm, role=User.ROLE_PARENT).first()
            or User.objects.filter(phone=contact["phone_number"], role=User.ROLE_PARENT).first()
        )

    ticket = _active_ticket_for_chat(chat_id)
    if not ticket:
        ticket = _create_ticket_for_chat(
            chat_id,
            tg_name=tg_name,
            tg_username=tg_username,
            linked_parent=linked_parent,
        )
        _broadcast_ticket(ticket, kind="created")
        # Yangi foydalanuvchi — tilni tanlatamiz
        tg_send_message(
            chat_id,
            t("uz_latn", "welcome"),
            reply_markup=_language_keyboard(),
        )

    # Mavjud ticket'ni yangilash
    changed = ["last_contact_at", "updated_at"]
    ticket.last_contact_at = timezone.now()
    if linked_parent and not ticket.parent_id:
        ticket.parent = linked_parent
        changed.append("parent")
    ticket.save(update_fields=changed)

    if contact:
        tg_send_message(chat_id, t(ticket.language or "uz_latn", "phone_saved"))

    if not text:
        return

    # Til tanlanmagan bo'lsa, oddiy xabarni hali ham yozib olamiz
    # (operator ko'rsin), lekin foydalanuvchini tilni tanlashga undaymiz.
    if ticket.bot_state == CallCenterTicket.BOT_STATE_AWAITING_LANGUAGE and not ticket.language:
        tg_send_message(
            chat_id,
            t("uz_latn", "welcome"),
            reply_markup=_language_keyboard(),
        )

    # /start emas matn — chatga yozamiz
    comment = CallCenterComment.objects.create(
        ticket=ticket,
        operator=None,
        comment=text,
        direction=CallCenterComment.DIRECTION_IN,
        old_status=ticket.status,
        new_status=ticket.status,
        telegram_message_id=str(message.get("message_id", "")),
    )
    _broadcast_comment(ticket, comment)
    _broadcast_ticket(ticket, kind="updated")
