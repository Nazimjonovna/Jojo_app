from jojolingo.models import MistakeLog, LearningMethodRule


def detect_child_weakness(child):
    mistakes = MistakeLog.objects.filter(child=child).order_by("-created_at")[:20]

    mistake_count = {}

    for mistake in mistakes:
        key = mistake.mistake_type or "general"
        mistake_count[key] = mistake_count.get(key, 0) + 1

    if not mistake_count:
        return "general"

    return max(mistake_count, key=mistake_count.get)


def get_child_level_code(child):
    profile = getattr(child, "learning_profile", None)

    if profile and profile.current_level:
        return profile.current_level.code

    if profile:
        return profile.ai_friend_level or "A0"

    return "A0"


def get_recommended_learning_method(child):
    mistake_type = detect_child_weakness(child)
    level_code = get_child_level_code(child)

    rule = LearningMethodRule.objects.filter(
        mistake_type=mistake_type,
        level_code=level_code,
        is_active=True
    ).first()

    if not rule:
        rule = LearningMethodRule.objects.filter(
            mistake_type="general",
            level_code=level_code,
            is_active=True
        ).first()

    return {
        "mistake_type": mistake_type,
        "level_code": level_code,
        "method": rule.recommended_method if rule else "review",
        "message": rule.message_uz if rule else "Keling, yana bir marta mashq qilamiz."
    }
    
    
from jojolingo.models import MistakeLog, LearningMethodRule


def get_user_language(user):
    return getattr(user, "language", "uz_latn") or "uz_latn"


def get_rule_message(rule, lang):
    if not rule:
        return {
            "uz_latn": "Keling, yana bir marta mashq qilamiz.",
            "uz_cyrl": "Келинг, яна бир марта машқ қиламиз.",
            "ru": "Давайте попробуем ещё раз.",
            "en": "Let's practice one more time.",
            "kk": "Тағы бір рет жаттығып көрейік.",
        }.get(lang, "Keling, yana bir marta mashq qilamiz.")

    if lang == "ru":
        return rule.message_ru or rule.message_uz

    if lang == "en":
        return rule.message_en or rule.message_uz

    if lang == "kk":
        return rule.message_kk or rule.message_uz

    return rule.message_uz


def detect_child_weakness(child):
    mistakes = MistakeLog.objects.filter(
        child=child
    ).order_by("-created_at")[:20]

    mistake_count = {}

    for mistake in mistakes:
        key = mistake.mistake_type or "general"
        mistake_count[key] = mistake_count.get(key, 0) + 1

    if not mistake_count:
        return "general"

    return max(mistake_count, key=mistake_count.get)


def get_child_level_code(child):
    profile = getattr(child, "learning_profile", None)

    if profile and profile.current_level:
        return profile.current_level.code

    if profile:
        return profile.ai_friend_level or "A0"

    return "A0"


def get_recommended_learning_method(child):
    mistake_type = detect_child_weakness(child)
    level_code = get_child_level_code(child)
    lang = get_user_language(child)

    rule = LearningMethodRule.objects.filter(
        mistake_type=mistake_type,
        level_code=level_code,
        is_active=True
    ).first()

    if not rule:
        rule = LearningMethodRule.objects.filter(
            mistake_type="general",
            level_code=level_code,
            is_active=True
        ).first()

    return {
        "mistake_type": mistake_type,
        "level_code": level_code,
        "method": rule.recommended_method if rule else "review",
        "message": get_rule_message(rule, lang),
    }