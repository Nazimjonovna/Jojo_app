"""SMSFLY (https://api.smsfly.uz) integratsiyasi.

API:
  POST /check-key           — kalit haqiqiyligini tekshirish
  POST /send                — bitta xabar yuborish
  POST /send-bulk           — bir nechta raqamga (<10000)
  POST /send-bulk-template  — shablon + dinamik o'zgaruvchilar bilan

Telefon raqami `998...` shaklida bo'lishi shart (+ va 00 belgilarisiz).
Javob: `{"success": bool, "reason": str, "resultCode": int}`.
`resultCode == 0` — muvaffaqiyatli.

Foydalanish:
    from .sms_service import sms_client
    sms_client.send_otp("+998901234567", "123456", user_id=1)

Muhim:
  - Har bir yuborish urinishi `SmsSendLog` ga yoziladi (success/fail bilan).
  - `SESSION_NOT_BOUND` xatosi uchun 1 marta avtomatik retry qilinadi.
  - Broadcast `send_bulk` natijasini per-phone log qiladi (umumiy bo'lsa-da).
"""

from __future__ import annotations

import logging
import re
import time
from typing import Iterable

import requests
from django.conf import settings

logger = logging.getLogger("jojo.sms")

# O'zbek mobil prefiksilarini hardcode qilmasligimiz uchun sabab: yangi
# operatorlar (50 - Mobi-UZ, 33 - UMS rebrandi, 20 - Perfectum yangi seriya
# va h.k.) muntazam qo'shilib turadi. Yagona qattiq tekshiruv:
#   - 998 + 9 raqam = 12 ta raqam
#   - faqat raqamlar
#   - aniq test/anomaliya patternlari (998900000000, hammasi nol kabi)


class SmsFlyError(Exception):
    """SMSFLY xato javobi yoki tarmoq xatosi."""

    def __init__(self, reason: str, result_code: int = -1):
        super().__init__(reason)
        self.reason = reason
        self.result_code = result_code


_PHONE_DIGITS_RE = re.compile(r"\D+")


def normalize_phone(raw: str) -> str:
    """`+998 90 123-45-67` → `998901234567`.

    Tartib:
      1. Faqat raqamlarni qoldiramiz.
      2. Boshida `00` bo'lsa olib tashlaymiz (xalqaro yozuv).
      3. 9 raqamli local (`901234567`) bo'lsa boshiga `998` qo'shamiz.

    Qaytaradi `str` — `998xxxxxxxxx` ko'rinishida (12 ta raqam) yoki
    invalid bo'lsa qanday bo'lsa shunday qaytaradi (caller validatsiya qiladi).
    """
    if not raw:
        return ""
    digits = _PHONE_DIGITS_RE.sub("", str(raw))
    if digits.startswith("00"):
        digits = digits[2:]
    # 9 raqamli local (901234567) bo'lsa `998` qo'shamiz.
    if len(digits) == 9 and digits.startswith("9"):
        digits = "998" + digits
    return digits


def is_valid_uz_phone(normalized: str) -> bool:
    """Normalized phone (998xxxxxxxxx) O'zbek raqami formatigami?

    Faqat fundamental tekshiruv:
      - aniq 12 ta raqam
      - 998 bilan boshlanadi
      - hammasi bir xil raqam emas (anomaliya: 998900000000 va h.k.)

    Operator prefiksi ro'yxati bu yerda yo'q — Uzbektelekomda yangi
    seriyalar tez-tez chiqadi (50, 33 yangilangan kabi). Operator rad qilsa
    SMSFLY o'zining xato kodi orqali xabar beradi.
    """
    if not normalized or not normalized.isdigit() or len(normalized) != 12:
        return False
    if not normalized.startswith("998"):
        return False
    suffix = normalized[3:]
    if suffix == suffix[0] * 9:
        return False
    return True


class SmsFlyClient:
    """SMSFLY REST API kliyenti.

    Kalit `settings.SMSFLY_KEY` yoki `SMSFLY_API_KEY` orqali olinadi.
    Agar bo'sh bo'lsa, `send_*` metodlari xatoga uchratmasdan log yozib
    qaytadi (development uchun qulay)."""

    BASE_URL = "https://api.smsfly.uz"
    TIMEOUT = 12  # soniya

    # SMSFLY natija kodlari
    RESULT_OK = 0
    RESULT_BLOCKED = 2
    RESULT_LIMIT_EXCEEDED = 3
    RESULT_MISSING_FIELDS = 4
    RESULT_TOO_MANY_NUMBERS_1 = 100
    RESULT_TOO_MANY_NUMBERS_2 = 101

    # Bu sabablarda biz qayta urinib ko'ramiz — bir martalik tarmoq/sessiya
    # muammosi bo'lishi mumkin
    RETRYABLE_REASONS = {"SESSION_NOT_BOUND", "TIMEOUT", "NETWORK"}

    def __init__(self, key: str | None = None):
        self._key = (
            key
            or getattr(settings, "SMSFLY_API_KEY", "")
            or getattr(settings, "SMSFLY_KEY", "")
            or ""
        )

    @property
    def enabled(self) -> bool:
        return bool(self._key)

    # ------------------------------------------------------------------
    # Quyi darajadagi HTTP
    # ------------------------------------------------------------------

    def _post(self, path: str, payload: dict) -> dict:
        body = dict(payload)
        body["key"] = self._key
        url = f"{self.BASE_URL}{path}"
        try:
            r = requests.post(url, json=body, timeout=self.TIMEOUT)
        except requests.RequestException as e:
            logger.warning("SMSFLY network error %s: %s", path, e)
            raise SmsFlyError("NETWORK", result_code=-1)
        try:
            data = r.json()
        except ValueError:
            logger.warning(
                "SMSFLY non-json response (%s): %s",
                r.status_code, r.text[:200],
            )
            raise SmsFlyError(f"INVALID_JSON_{r.status_code}", result_code=-1)
        success = bool(data.get("success"))
        reason = str(data.get("reason") or "")
        result_code = int(data.get("resultCode") or -1)
        if not success:
            logger.warning(
                "SMSFLY %s failed: reason=%s code=%s",
                path, reason, result_code,
            )
            raise SmsFlyError(reason or "UNKNOWN_ERROR", result_code=result_code)
        return {"success": True, "reason": reason, "result_code": result_code}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check_key(self) -> bool:
        """Kalit haqiqiyligini tekshiradi."""
        if not self.enabled:
            return False
        try:
            self._post("/check-key", {})
            return True
        except SmsFlyError:
            return False

    def send(
        self,
        phone: str,
        message: str,
        *,
        kind: str = "other",
        user_id: int | None = None,
        max_retries: int = 1,
    ) -> bool:
        """Bitta foydalanuvchiga xabar yuborish.

        SESSION_NOT_BOUND/TIMEOUT/NETWORK xatolari uchun `max_retries`
        marta qayta urinib ko'radi (default 1 ta qayta urinish).
        Har bir urinish `SmsSendLog` ga yoziladi.
        """
        normalized = normalize_phone(phone)

        # Strict validatsiya — log qilamiz lekin SMSFLY ga yubormaymiz
        if not is_valid_uz_phone(normalized):
            self._log(
                phone=phone, normalized=normalized, kind=kind, message=message,
                success=False, result_code=-2, reason="INVALID_PHONE",
                retry_count=0, user_id=user_id,
            )
            logger.warning("SMSFLY skip — invalid UZ phone: %s -> %s", phone, normalized)
            return False

        if not self.enabled:
            logger.info("[SMS DEV] %s: %s", normalized, message)
            self._log(
                phone=phone, normalized=normalized, kind=kind, message=message,
                success=True, result_code=0, reason="DEV_MODE",
                retry_count=0, user_id=user_id,
            )
            return True

        attempt = 0
        last_reason = ""
        last_code = -1
        while attempt <= max_retries:
            try:
                self._post("/send", {"phone": normalized, "message": message})
                self._log(
                    phone=phone, normalized=normalized, kind=kind, message=message,
                    success=True, result_code=0, reason="OK",
                    retry_count=attempt, user_id=user_id,
                )
                return True
            except SmsFlyError as e:
                last_reason = e.reason
                last_code = e.result_code
                # Faqat retryable sabablarda qayta urinamiz
                if e.reason in self.RETRYABLE_REASONS and attempt < max_retries:
                    attempt += 1
                    time.sleep(0.8)
                    continue
                # Boshqa xatolar yoki retries tugadi
                self._log(
                    phone=phone, normalized=normalized, kind=kind, message=message,
                    success=False, result_code=last_code, reason=last_reason[:120],
                    retry_count=attempt, user_id=user_id,
                )
                logger.warning(
                    "SMSFLY send failed phone=%s reason=%s (after %s retries)",
                    normalized, last_reason, attempt,
                )
                return False
        return False

    def send_otp(self, phone: str, code: str, *, user_id: int | None = None) -> bool:
        """Verifikatsiya kodini yuborish."""
        text = f"JoJo: tasdiqlash kodi {code}. Kodni hech kimga bermang."
        return self.send(phone, text, kind="otp", user_id=user_id)

    def send_bulk_per_phone(
        self,
        phones: Iterable[str],
        message: str,
        *,
        kind: str = "broadcast",
    ) -> dict:
        """Bir nechta raqamga bittadan yuborish — per-phone log + retry bilan.

        Bulk endpoint o'rniga har bir raqam alohida yuboriladi. Sekinroq, lekin:
          - har bir raqam alohida loglanadi
          - SESSION_NOT_BOUND da retry ishlaydi
          - failed raqamlar reason bilan qaytadi
        """
        sent, failed = [], []
        for phone in phones:
            ok = self.send(phone, message, kind=kind)
            normalized = normalize_phone(phone)
            if ok:
                sent.append(normalized)
            else:
                # Eng yangi log yozuvidan reason olamiz
                reason = self._last_reason(normalized) or "UNKNOWN"
                failed.append({"phone": phone, "normalized": normalized, "reason": reason})
        return {"sent": sent, "failed": failed, "total": len(sent) + len(failed)}

    def send_bulk(self, phones: Iterable[str], message: str) -> bool:
        """SMSFLY native bulk endpoint — eski API qaytadan ishlatishi mumkin.

        DEPRECATED: per-phone log yo'q. Yangi kod `send_bulk_per_phone` ishlatsin.
        """
        if not self.enabled:
            phone_list = list(phones)
            logger.info("[SMS DEV BULK] %d ta raqamga: %s", len(phone_list), message)
            return True
        nums = [normalize_phone(p) for p in phones]
        nums = [n for n in nums if is_valid_uz_phone(n)]
        if not nums:
            return False
        for i in range(0, len(nums), 10000):
            chunk = nums[i:i + 10000]
            try:
                self._post("/send-bulk", {"message": message, "phones": chunk})
            except SmsFlyError as e:
                logger.warning("SMSFLY bulk chunk failed: %s", e)
                return False
        return True

    # ------------------------------------------------------------------
    # Log yordamchilari
    # ------------------------------------------------------------------

    def _log(
        self,
        *,
        phone: str,
        normalized: str,
        kind: str,
        message: str,
        success: bool,
        result_code: int,
        reason: str,
        retry_count: int,
        user_id: int | None,
    ):
        try:
            from .models import SmsSendLog
            SmsSendLog.objects.create(
                phone=str(phone)[:20],
                phone_normalized=normalized[:20],
                kind=kind,
                message=message[:5000],
                success=success,
                result_code=result_code,
                reason=reason,
                retry_count=retry_count,
                related_user_id=user_id,
            )
        except Exception:
            logger.exception("SmsSendLog yozib bo'lmadi")

    def _last_reason(self, normalized: str) -> str:
        try:
            from .models import SmsSendLog
            last = SmsSendLog.objects.filter(
                phone_normalized=normalized, success=False,
            ).order_by("-created_at").first()
            return last.reason if last else ""
        except Exception:
            return ""


# Singleton — ko'p joydan `from .sms_service import sms_client` qilib chaqirish uchun.
sms_client = SmsFlyClient()
