"""Markazlashtirilgan til hal qilish — har bir requestga `request.language`
o'rnatamiz. Tartib (eng baland prioritetdan eng pastgacha):

1. URL query string  — `?lang=ru`
2. `Accept-Language` header (birinchi qabul qilingan til kalit)
3. Foydalanuvchining profilidagi `language` ustuni
4. Default — `uz`

Frontendlar (parent/kids) doim Accept-Language yuborishi tavsiya etiladi —
shu sababli middleware faqat normalize qiladi va serializer'larga yetkazadi.
"""

SUPPORTED = {"uz", "ru", "en"}
DEFAULT = "uz"


def normalize_lang(value):
    if not value:
        return None
    v = str(value).strip().lower()
    # Accept-Language quality value'larini ignor qilamiz: "ru-RU,en;q=0.9"
    v = v.split(",")[0].split(";")[0].strip()
    # uz_Latn, uz-Latn, uz-cyrl -> uz
    if v.startswith("uz"):
        return "uz"
    if v.startswith("ru"):
        return "ru"
    if v.startswith("en"):
        return "en"
    return None


def resolve_language(request):
    # 1) Query
    q = request.GET.get("lang") if hasattr(request, "GET") else None
    lang = normalize_lang(q)
    if lang in SUPPORTED:
        return lang
    # 2) Accept-Language header
    header = request.META.get("HTTP_ACCEPT_LANGUAGE") if hasattr(request, "META") else None
    lang = normalize_lang(header)
    if lang in SUPPORTED:
        return lang
    # 3) Profile
    user = getattr(request, "user", None)
    if user is not None and getattr(user, "is_authenticated", False):
        lang = normalize_lang(getattr(user, "language", None))
        if lang in SUPPORTED:
            return lang
    return DEFAULT


class LanguageResolutionMiddleware:
    """Har bir requestga `request.language` ('uz' | 'ru' | 'en') o'rnatadi.

    Serializer va viewlar shu kalitni o'qib mos tildagi maydonni tanlaydi.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.language = resolve_language(request)
        return self.get_response(request)


def localized(instance, base_field, lang=None):
    """Modelning `_uz/_ru/_en` variantlaridan tanlangan tilga mos qiymatni
    qaytaradi. Maydon yo'q yoki bo'sh bo'lsa, asl (base) maydonga qaytadi.

    Misol:
        localized(plan, 'name', 'ru')  ->  plan.name_ru yoki plan.name
    """
    lang = (lang or DEFAULT).lower()
    if lang not in SUPPORTED:
        lang = DEFAULT
    # uz uchun asosiy maydon
    if lang == "uz":
        return getattr(instance, base_field, "") or ""
    suffix_field = f"{base_field}_{lang}"
    value = getattr(instance, suffix_field, None)
    if value:
        return value
    # Tarjima yo'q bo'lsa uz ga qaytamiz
    return getattr(instance, base_field, "") or ""


class LocalizedSerializerMixin:
    """Serializer'ga qo'shilsa, `Meta.localized_fields` ro'yxatidagi
    maydonlarni `request.language` asosida _uz/_ru/_en variantidan
    avtomatik tanlaydi.

    Foydalanish:
        class MySer(LocalizedSerializerMixin, serializers.ModelSerializer):
            class Meta:
                model = MyModel
                fields = ["id", "name", "description", ...]
                localized_fields = ["name", "description"]
    """

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get("request") if hasattr(self, "context") else None
        lang = getattr(request, "language", DEFAULT) if request is not None else DEFAULT
        fields = getattr(getattr(self, "Meta", None), "localized_fields", None) or []
        for f in fields:
            if f in data:
                data[f] = localized(instance, f, lang)
        return data
