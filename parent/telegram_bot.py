import logging
import requests
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)
TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"


def _token():
    return getattr(settings, "TELEGRAM_BOT_TOKEN", "")


def tg_send_message(chat_id, text):
    token = _token()
    if not token:
        logger.warning("TELEGRAM_BOT_TOKEN yo'q. Xabar yuborilmadi.")
        return None
    url = TELEGRAM_API.format(token=token, method="sendMessage")
    try:
        r = requests.post(
            url,
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            timeout=10,
            verify=getattr(settings, "TELEGRAM_VERIFY_SSL", True),
        )
        data = r.json()
        if not data.get("ok"):
            logger.error("Telegram sendMessage xato: %s", data)
            return None
        return data.get("result", {}).get("message_id")
    except requests.RequestException as e:
        logger.error("Telegram ulanish xatosi: %s", e)
        return None


def _normalize_phone(phone):
    if not phone:
        return phone
    phone = phone.strip().replace(" ", "")
    return phone if phone.startswith("+") else "+" + phone


def handle_telegram_update(update: dict):
    """Telegram webhook'idan kelgan xabarni ticketga yozadi."""
    from .models import CallCenterTicket, CallCenterComment, User
    from .realtime import broadcast_lead_changed, broadcast_lead_comment

    message = update.get("message") or update.get("edited_message")
    if not message:
        return

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
    tg_username = from_user.get("username", "") or ""

    # /start — kutib olish
    if text.startswith("/start"):
        tg_send_message(
            chat_id,
            "Assalomu alaykum! Savol yoki murojaatingizni yozib qoldiring — "
            "operatorlarimiz tez orada javob beradi.",
        )
        return

    # Raqam ulashilsa, ro'yxatdagi ota-onaga bog'laymiz
    linked_parent = None
    if contact and contact.get("phone_number"):
        norm = _normalize_phone(contact["phone_number"])
        linked_parent = (
            User.objects.filter(phone=norm, role=User.ROLE_PARENT).first()
            or User.objects.filter(phone=contact["phone_number"], role=User.ROLE_PARENT).first()
        )

    # Shu chat uchun ochiq ticket — bo'lmasa yangi
    ticket = (
        CallCenterTicket.objects
        .filter(telegram_chat_id=chat_id)
        .exclude(status=CallCenterTicket.STATUS_CLOSED)
        .order_by("-updated_at")
        .first()
    )
    if not ticket:
        ticket = CallCenterTicket.objects.create(
            parent=linked_parent,
            source=CallCenterTicket.SOURCE_TELEGRAM,
            telegram_chat_id=chat_id,
            telegram_username=tg_username,
            telegram_name=tg_name,
            title=f"Telegram: {tg_name}",
            status=CallCenterTicket.STATUS_NEW,
        )
    else:
        changed = ["last_contact_at", "updated_at"]
        ticket.last_contact_at = timezone.now()
        if linked_parent and not ticket.parent_id:
            ticket.parent = linked_parent
            changed.append("parent")
        ticket.save(update_fields=changed)

    if contact:
        tg_send_message(chat_id, "Rahmat! Raqamingiz qabul qilindi.")

    if not text:
        return

    comment = CallCenterComment.objects.create(
        ticket=ticket,
        operator=None,
        comment=text,
        direction=CallCenterComment.DIRECTION_IN,
        old_status=ticket.status,
        new_status=ticket.status,
        telegram_message_id=str(message.get("message_id", "")),
    )

    # Adminkaga real-time
    try:
        from .admin_views import _comment_to_dict, _lead_to_dict
        broadcast_lead_comment({"ticket_id": ticket.id, "comment": _comment_to_dict(comment)})
        broadcast_lead_changed({"type": "updated", "id": ticket.id, "lead": _lead_to_dict(ticket)})
    except Exception:
        logger.exception("broadcast xato")