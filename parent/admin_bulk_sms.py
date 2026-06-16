"""Bulk SMS admin endpointlari:

Contact groups:
  GET    /admin/sms/groups/
  POST   /admin/sms/groups/
  GET    /admin/sms/groups/<id>/
  PATCH  /admin/sms/groups/<id>/
  DELETE /admin/sms/groups/<id>/

Contacts (guruh ichida):
  GET    /admin/sms/groups/<id>/contacts/
  POST   /admin/sms/groups/<id>/contacts/        # bitta yoki ro'yxat
  DELETE /admin/sms/groups/<id>/contacts/<cid>/

CSV/XLSX import:
  POST   /admin/sms/parse-numbers/               # raw matn yoki fayl → list[str]
  POST   /admin/sms/groups/<id>/import/          # parse + add to group

Campaigns:
  GET    /admin/sms/campaigns/
  POST   /admin/sms/campaigns/                   # yaratish + sync yuborish
  GET    /admin/sms/campaigns/<id>/              # detail + recipient breakdown
"""

from __future__ import annotations

import csv
import io
import re
from datetime import datetime

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    BulkSmsCampaign,
    SmsContact,
    SmsContactGroup,
    SmsSendLog,
)
from .sms_service import (
    is_valid_uz_phone,
    normalize_phone,
    sms_client,
)

User = get_user_model()


class IsAdminUser(BasePermission):
    """admin_views.IsAdminUser bilan bir xil — staff yoki superuser."""

    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and (u.is_staff or u.is_superuser))


# ----------------------------------------------------------------------------
# Yordamchi: matn yoki fayl ichidan raqamlarni ajratib olish
# ----------------------------------------------------------------------------

_NUMBER_LINE_RE = re.compile(r"[+0-9][0-9\s\-()]{6,}")


def parse_numbers_from_text(raw: str) -> list[dict]:
    """Erkin matndan raqamlarni ajratadi. Vergul / probel / qator bilan
    ajratilgan har xil format'lar qabul qilinadi.

    Qaytaradi: [{"raw": "+998 ...", "normalized": "998...", "valid": bool}]
    """
    if not raw:
        return []
    results = []
    seen = set()
    for match in _NUMBER_LINE_RE.findall(raw):
        normalized = normalize_phone(match)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        results.append({
            "raw": match.strip(),
            "normalized": normalized,
            "valid": is_valid_uz_phone(normalized),
        })
    return results


def parse_numbers_from_csv(file_bytes: bytes) -> list[dict]:
    """CSV/TSV faylidan raqamlarni ajratadi. Birinchi ustun yoki `phone`/
    `tel`/`number` ustunlari avtomatik aniqlanadi. Yangi qator
    (CR/LF/CRLF) qo'llab-quvvatlanadi."""
    try:
        text = file_bytes.decode("utf-8-sig", errors="replace")
    except Exception:
        text = file_bytes.decode("latin-1", errors="replace")
    # Avtomatik separator aniqlash: vergul / nuqta-vergul / tab
    sample = text[:2000]
    delim = ","
    if sample.count(";") > sample.count(","):
        delim = ";"
    elif sample.count("\t") > sample.count(","):
        delim = "\t"
    reader = csv.reader(io.StringIO(text), delimiter=delim)
    rows = list(reader)
    if not rows:
        return []

    header = [c.strip().lower() for c in rows[0]]
    phone_col = 0
    for i, h in enumerate(header):
        if h in ("phone", "phone_number", "tel", "telefon", "number", "raqam"):
            phone_col = i
            break

    # Birinchi qator header bo'lmasligi mumkin — birinchi katakda raqam
    # bo'lsa, hammasini ma'lumot deb hisoblaymiz.
    data_rows = rows[1:] if any(c.isalpha() for c in (rows[0][phone_col] or "")) else rows

    results = []
    seen = set()
    for row in data_rows:
        if not row or len(row) <= phone_col:
            continue
        candidate = row[phone_col] or ""
        normalized = normalize_phone(candidate)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        results.append({
            "raw": candidate.strip(),
            "normalized": normalized,
            "valid": is_valid_uz_phone(normalized),
        })
    return results


# ----------------------------------------------------------------------------
# Contact groups
# ----------------------------------------------------------------------------


def _group_to_dict(g: SmsContactGroup, *, with_counts: bool = True) -> dict:
    data = {
        "id": g.id,
        "name": g.name,
        "description": g.description,
        "owner_id": g.owner_id,
        "created_at": g.created_at.isoformat(),
        "updated_at": g.updated_at.isoformat(),
    }
    if with_counts:
        data["contacts_count"] = g.contacts.count()
    return data


def _contact_to_dict(c: SmsContact) -> dict:
    return {
        "id": c.id,
        "group_id": c.group_id,
        "phone": c.phone,
        "phone_normalized": c.phone_normalized,
        "name": c.name,
        "notes": c.notes,
        "created_at": c.created_at.isoformat(),
    }


class AdminSmsContactGroupListCreateView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        qs = SmsContactGroup.objects.all().order_by("-updated_at")
        return Response({"results": [_group_to_dict(g) for g in qs]})

    def post(self, request):
        name = (request.data.get("name") or "").strip()
        if not name:
            return Response({"detail": "name majburiy"}, status=400)
        description = (request.data.get("description") or "").strip()
        g = SmsContactGroup.objects.create(
            name=name,
            description=description,
            owner=request.user if request.user.is_authenticated else None,
        )
        return Response(_group_to_dict(g), status=201)


class AdminSmsContactGroupDetailView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request, group_id):
        g = SmsContactGroup.objects.filter(id=group_id).first()
        if not g:
            return Response({"detail": "Topilmadi"}, status=404)
        # Detail — kontaktlar bilan birga (sayfalanmaymiz, default 500 dan
        # past bo'lishi kerak; frontend kerak bo'lsa /contacts/ chaqirsin)
        contacts = list(g.contacts.all().order_by("-created_at")[:500])
        return Response({
            **_group_to_dict(g),
            "contacts": [_contact_to_dict(c) for c in contacts],
        })

    def patch(self, request, group_id):
        g = SmsContactGroup.objects.filter(id=group_id).first()
        if not g:
            return Response({"detail": "Topilmadi"}, status=404)
        if "name" in request.data:
            name = (request.data.get("name") or "").strip()
            if not name:
                return Response({"detail": "name bo'sh"}, status=400)
            g.name = name
        if "description" in request.data:
            g.description = (request.data.get("description") or "").strip()
        g.save()
        return Response(_group_to_dict(g))

    def delete(self, request, group_id):
        g = SmsContactGroup.objects.filter(id=group_id).first()
        if not g:
            return Response({"detail": "Topilmadi"}, status=404)
        g.delete()
        return Response(status=204)


class AdminSmsContactListCreateView(APIView):
    """Guruh ichidagi kontaktlarni ko'rsatish va qo'shish.

    POST body: bitta { phone, name?, notes? } yoki { contacts: [...] }
    Mavjud raqam (normalized) takror qo'shilmaydi (unique constraint).
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request, group_id):
        if not SmsContactGroup.objects.filter(id=group_id).exists():
            return Response({"detail": "Guruh topilmadi"}, status=404)
        qs = SmsContact.objects.filter(group_id=group_id).order_by("-created_at")
        return Response({"results": [_contact_to_dict(c) for c in qs]})

    def post(self, request, group_id):
        g = SmsContactGroup.objects.filter(id=group_id).first()
        if not g:
            return Response({"detail": "Guruh topilmadi"}, status=404)

        items = request.data.get("contacts")
        if not items:
            # Bitta kontakt holati
            phone = (request.data.get("phone") or "").strip()
            if not phone:
                return Response({"detail": "phone majburiy"}, status=400)
            items = [{
                "phone": phone,
                "name": request.data.get("name") or "",
                "notes": request.data.get("notes") or "",
            }]
        elif not isinstance(items, list):
            return Response({"detail": "contacts ro'yxat bo'lishi kerak"}, status=400)

        added = 0
        skipped = 0
        for item in items:
            raw = (item.get("phone") or "").strip() if isinstance(item, dict) else str(item).strip()
            normalized = normalize_phone(raw)
            if not normalized:
                skipped += 1
                continue
            try:
                with transaction.atomic():
                    SmsContact.objects.create(
                        group=g,
                        phone=raw[:20],
                        phone_normalized=normalized[:20],
                        name=(item.get("name") if isinstance(item, dict) else "")[:120],
                        notes=(item.get("notes") if isinstance(item, dict) else "")[:255],
                    )
                added += 1
            except IntegrityError:
                # uniqueness violation — bu raqam guruhda allaqachon bor
                skipped += 1
        g.save()  # updated_at
        return Response({"added": added, "skipped": skipped, "group_id": g.id}, status=201)


class AdminSmsContactDetailView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def delete(self, request, group_id, contact_id):
        c = SmsContact.objects.filter(id=contact_id, group_id=group_id).first()
        if not c:
            return Response({"detail": "Topilmadi"}, status=404)
        c.delete()
        return Response(status=204)


# ----------------------------------------------------------------------------
# Number parsing (manual text + CSV file)
# ----------------------------------------------------------------------------


class AdminSmsParseNumbersView(APIView):
    """Raqamlarni matn yoki fayl orqali parse qiladi (validatsiya bilan).

    Frontend foydalanish:
      - foydalanuvchi textareaga raqamlar yopishtirdi → text bilan POST
      - foydalanuvchi CSV/TSV/Excel-CSV faylini yukladi → file bilan POST

    Qaytaradi: {numbers: [{raw, normalized, valid}], total, valid_count}
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    def post(self, request):
        items = []
        # Multipart bo'lsa fayl, aks holda body[text]
        upload = request.FILES.get("file")
        if upload:
            items = parse_numbers_from_csv(upload.read())
        else:
            raw = request.data.get("text") or ""
            items = parse_numbers_from_text(raw)
        valid_count = sum(1 for x in items if x["valid"])
        return Response({
            "numbers": items,
            "total": len(items),
            "valid_count": valid_count,
        })


class AdminSmsGroupImportView(APIView):
    """CSV/XLSX faylini guruhga import qiladi."""
    permission_classes = [IsAuthenticated, IsAdminUser]

    def post(self, request, group_id):
        g = SmsContactGroup.objects.filter(id=group_id).first()
        if not g:
            return Response({"detail": "Guruh topilmadi"}, status=404)
        upload = request.FILES.get("file")
        if not upload:
            return Response({"detail": "file majburiy"}, status=400)
        items = parse_numbers_from_csv(upload.read())
        added = 0
        skipped = 0
        for item in items:
            if not item["valid"]:
                skipped += 1
                continue
            try:
                with transaction.atomic():
                    SmsContact.objects.create(
                        group=g,
                        phone=item["raw"][:20],
                        phone_normalized=item["normalized"][:20],
                    )
                added += 1
            except IntegrityError:
                skipped += 1
        g.save()
        return Response({"added": added, "skipped": skipped, "total_parsed": len(items)})


# ----------------------------------------------------------------------------
# Bulk SMS campaigns
# ----------------------------------------------------------------------------


def _campaign_to_dict(c: BulkSmsCampaign, *, with_logs: bool = False) -> dict:
    data = {
        "id": c.id,
        "title": c.title,
        "message": c.message,
        "message_ru": c.message_ru,
        "message_en": c.message_en,
        "message_uz_cyrl": c.message_uz_cyrl,
        "status": c.status,
        "source": c.source,
        "group_id": c.group_id,
        "group_name": c.group.name if c.group_id else None,
        "total": c.total,
        "sent_count": c.sent_count,
        "failed_count": c.failed_count,
        "created_by_id": c.created_by_id,
        "created_by_name": (
            c.created_by.first_name or c.created_by.phone or c.created_by.username
            if c.created_by_id else None
        ),
        "created_at": c.created_at.isoformat(),
        "started_at": c.started_at.isoformat() if c.started_at else None,
        "finished_at": c.finished_at.isoformat() if c.finished_at else None,
    }
    if with_logs:
        logs = c.logs.all().order_by("-created_at")[:1000]
        data["logs"] = [{
            "id": log.id,
            "phone": log.phone,
            "phone_normalized": log.phone_normalized,
            "success": log.success,
            "result_code": log.result_code,
            "reason": log.reason,
            "retry_count": log.retry_count,
            "created_at": log.created_at.isoformat(),
        } for log in logs]
    return data


def _resolve_recipients(payload: dict) -> tuple[list[str], str]:
    """Payload dan raqamlarni ajratib oladi.

    Tartib:
      1) `phones`: ["+998..."] — qo'lda kiritilgan ro'yxat
      2) `group_id`: int — guruhdagi barcha valid kontaktlar
      3) `numbers_text`: str — erkin matn (parse qilamiz)

    Bir nechtasi ham bo'lsa, hammasi birlashtiriladi (deduplicate qilinadi).
    Faqat is_valid_uz_phone() rost bo'lganlari qaytariladi.

    Qaytaradi: (normalized_phones, source)
    """
    phones = set()
    sources = set()

    raw_list = payload.get("phones")
    if isinstance(raw_list, list):
        for p in raw_list:
            n = normalize_phone(str(p))
            if is_valid_uz_phone(n):
                phones.add(n)
        if raw_list:
            sources.add(BulkSmsCampaign.SOURCE_MANUAL)

    group_id = payload.get("group_id")
    if group_id:
        contacts = SmsContact.objects.filter(group_id=group_id).values_list(
            "phone_normalized", flat=True,
        )
        for n in contacts:
            if is_valid_uz_phone(n):
                phones.add(n)
        sources.add(BulkSmsCampaign.SOURCE_GROUP)

    text = payload.get("numbers_text")
    if text:
        for item in parse_numbers_from_text(text):
            if item["valid"]:
                phones.add(item["normalized"])
        sources.add(BulkSmsCampaign.SOURCE_MANUAL)

    if len(sources) > 1:
        source = BulkSmsCampaign.SOURCE_MIXED
    elif sources:
        source = sources.pop()
    else:
        source = BulkSmsCampaign.SOURCE_MANUAL

    return sorted(phones), source


class AdminBulkSmsCampaignListCreateView(APIView):
    """Kampaniyalar ro'yxati + yangi kampaniya yaratish (yuboriladi)."""
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        qs = BulkSmsCampaign.objects.all().select_related("group", "created_by").order_by("-created_at")
        page_size = max(1, min(int(request.query_params.get("page_size", 50)), 200))
        offset = max(0, int(request.query_params.get("offset", 0)))
        total = qs.count()
        items = [_campaign_to_dict(c) for c in qs[offset:offset + page_size]]
        return Response({
            "count": total,
            "offset": offset,
            "page_size": page_size,
            "results": items,
        })

    def post(self, request):
        title = (request.data.get("title") or "").strip()
        message = (request.data.get("message") or "").strip()
        if not message:
            return Response({"detail": "message majburiy"}, status=400)

        phones, source = _resolve_recipients(request.data)
        if not phones:
            return Response({"detail": "Yuborish uchun yaroqli raqamlar topilmadi"}, status=400)

        group_id = request.data.get("group_id") or None
        try:
            group_id = int(group_id) if group_id else None
        except (TypeError, ValueError):
            group_id = None

        campaign = BulkSmsCampaign.objects.create(
            title=title[:160],
            message=message[:5000],
            message_ru=(request.data.get("message_ru") or "").strip()[:5000],
            message_en=(request.data.get("message_en") or "").strip()[:5000],
            message_uz_cyrl=(request.data.get("message_uz_cyrl") or "").strip()[:5000],
            status=BulkSmsCampaign.STATUS_SENDING,
            source=source,
            group_id=group_id,
            total=len(phones),
            created_by=request.user if request.user.is_authenticated else None,
            started_at=timezone.now(),
        )

        # Per-recipient til: har bir foydalanuvchi User.language ga qarab
        # mos matn oladi. Telefon → User mapping bir marotaba.
        from django.contrib.auth import get_user_model
        UserModel = get_user_model()
        users_by_phone = {
            u.phone: u for u in UserModel.objects
            .filter(phone__in=list(phones))
            .only("id", "phone", "language")
        }

        def pick_message_for(phone):
            u = users_by_phone.get(phone)
            lang_value = (u.language if u else "") or ""
            v = lang_value.lower()
            if v.startswith("ru") and campaign.message_ru:
                return campaign.message_ru, u.id if u else None
            if v.startswith("en") and campaign.message_en:
                return campaign.message_en, u.id if u else None
            if "cyr" in v and campaign.message_uz_cyrl:
                return campaign.message_uz_cyrl, u.id if u else None
            return campaign.message, u.id if u else None

        # Sinxron yuborish — per phone, har biri SmsSendLog ga yoziladi.
        sent = 0
        failed = []
        for phone in phones:
            text, uid = pick_message_for(phone)
            ok = sms_client.send(
                phone, text,
                kind=SmsSendLog.KIND_BULK,
                campaign_id=campaign.id,
                user_id=uid,
            )
            if ok:
                sent += 1
            else:
                # Eng yangi log dan reason olamiz
                last = SmsSendLog.objects.filter(
                    phone_normalized=phone, campaign_id=campaign.id,
                ).order_by("-created_at").first()
                failed.append({
                    "phone": phone,
                    "reason": last.reason if last else "UNKNOWN",
                })

        campaign.sent_count = sent
        campaign.failed_count = len(failed)
        campaign.status = BulkSmsCampaign.STATUS_DONE
        campaign.finished_at = timezone.now()
        campaign.save(update_fields=[
            "sent_count", "failed_count", "status", "finished_at",
        ])

        return Response({
            "campaign": _campaign_to_dict(campaign),
            "failed_sample": failed[:20],
        }, status=201)


class AdminBulkSmsCampaignDetailView(APIView):
    """Bitta kampaniyaning to'liq holati + per-recipient loglari."""
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request, campaign_id):
        c = BulkSmsCampaign.objects.filter(id=campaign_id).select_related(
            "group", "created_by",
        ).first()
        if not c:
            return Response({"detail": "Topilmadi"}, status=404)
        return Response(_campaign_to_dict(c, with_logs=True))
