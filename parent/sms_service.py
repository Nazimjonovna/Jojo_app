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
    sms_client.send_otp("+998901234567", "123456")
"""

from __future__ import annotations

import logging
import re
from typing import Iterable

import requests
from django.conf import settings

logger = logging.getLogger("jojo.sms")


class SmsFlyError(Exception):
    """SMSFLY xato javobi yoki tarmoq xatosi."""

    def __init__(self, reason: str, result_code: int = -1):
        super().__init__(reason)
        self.reason = reason
        self.result_code = result_code


def normalize_phone(raw: str) -> str:
    """`+998901234567` yoki `998901234567` -> `998901234567`.

    Faqat raqamlarni qoldiramiz; agar `0` bilan boshlansa (00...) ham
    olib tashlaymiz. Yakuniy son uzunligi 12 ta bo'lishi kerak (UZ).
    """
    digits = re.sub(r"\D", "", raw or "")
    # Ba'zilar `00998...` yozadi.
    if digits.startswith("00"):
        digits = digits[2:]
    # 9 raqamli local (901234567) bo'lsa `998` qo'shamiz.
    if len(digits) == 9 and digits.startswith("9"):
        digits = "998" + digits
    return digits


class SmsFlyClient:
    """SMSFLY REST API kliyenti.

    Kalit `settings.SMSFLY_KEY` orqali olinadi. Agar bo'sh bo'lsa,
    `send_*` metodlari xatoga uchratmasdan log yozib qaytadi
    (development uchun qulay)."""

    BASE_URL = "https://api.smsfly.uz"
    TIMEOUT = 12  # soniya

    # SMSFLY natija kodlari
    RESULT_OK = 0
    RESULT_BLOCKED = 2
    RESULT_LIMIT_EXCEEDED = 3
    RESULT_MISSING_FIELDS = 4
    RESULT_TOO_MANY_NUMBERS_1 = 100
    RESULT_TOO_MANY_NUMBERS_2 = 101

    def __init__(self, key: str | None = None):
        self._key = key or getattr(settings, "SMSFLY_KEY", "") or ""

    @property
    def enabled(self) -> bool:
        return bool(self._key)

    # ------------------------------------------------------------------
    # Low-level HTTP
    # ------------------------------------------------------------------

    def _post(self, path: str, payload: dict) -> dict:
        body = dict(payload)
        body["key"] = self._key
        url = f"{self.BASE_URL}{path}"
        try:
            r = requests.post(url, json=body, timeout=self.TIMEOUT)
        except requests.RequestException as e:
            logger.warning("SMSFLY network error %s: %s", path, e)
            raise SmsFlyError(f"network: {e}")
        try:
            data = r.json()
        except ValueError:
            logger.warning("SMSFLY non-json response (%s): %s", r.status_code, r.text[:200])
            raise SmsFlyError(f"http_{r.status_code}_invalid_json")
        success = bool(data.get("success"))
        reason = str(data.get("reason") or "")
        result_code = int(data.get("resultCode") or -1)
        if not success:
            logger.warning(
                "SMSFLY %s failed: reason=%s code=%s",
                path, reason, result_code,
            )
            raise SmsFlyError(reason or "unknown_error", result_code=result_code)
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

    def send(self, phone: str, message: str) -> bool:
        """Bitta foydalanuvchiga xabar yuborish."""
        if not self.enabled:
            logger.info("[SMS DEV] %s: %s", phone, message)
            return True
        normalized = normalize_phone(phone)
        if len(normalized) < 11:
            logger.warning("SMSFLY skip — bad phone format: %s", phone)
            return False
        try:
            self._post("/send", {"phone": normalized, "message": message})
            return True
        except SmsFlyError as e:
            logger.warning("SMSFLY send failed phone=%s: %s", normalized, e)
            return False

    def send_otp(self, phone: str, code: str) -> bool:
        """Verifikatsiya kodini yuborish."""
        text = f"JoJo: tasdiqlash kodi {code}. Kodni hech kimga bermang."
        return self.send(phone, text)

    def send_bulk(self, phones: Iterable[str], message: str) -> bool:
        """Bir necha raqamga bir xil matn yuborish (<10000 ta)."""
        if not self.enabled:
            phone_list = list(phones)
            logger.info("[SMS DEV BULK] %d ta raqamga: %s", len(phone_list), message)
            return True
        nums = [normalize_phone(p) for p in phones]
        nums = [n for n in nums if len(n) >= 11]
        if not nums:
            return False
        # SMSFLY limit — 10000
        for i in range(0, len(nums), 10000):
            chunk = nums[i:i + 10000]
            try:
                self._post("/send-bulk", {"message": message, "phones": chunk})
            except SmsFlyError as e:
                logger.warning("SMSFLY bulk chunk failed: %s", e)
                return False
        return True

    def send_template(
        self,
        message_template: str,
        recipients: list[dict],
    ) -> bool:
        """Har bir raqamga dinamik o'zgaruvchili xabar yuborish.

        `message_template` ichida `%var_name` shaklida o'zgaruvchilar.
        `recipients` — `[{"phone": "...", "variables": {"name": "..."}}]`.
        """
        if not self.enabled:
            logger.info("[SMS DEV TEMPLATE] %d recipients", len(recipients))
            return True
        normalized = []
        for r in recipients:
            phone = normalize_phone(r.get("phone") or "")
            if len(phone) < 11:
                continue
            normalized.append({"phone": phone, "variables": r.get("variables") or {}})
        if not normalized:
            return False
        try:
            self._post("/send-bulk-template", {
                "message": message_template,
                "messages": normalized,
            })
            return True
        except SmsFlyError as e:
            logger.warning("SMSFLY template failed: %s", e)
            return False


# Singleton — ko'p joydan `from .sms_service import sms_client` qilib chaqirish uchun.
sms_client = SmsFlyClient()
