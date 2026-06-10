from jojolingo.models import (
    VocabularyItem,
    GrammarRule,
    Exercise,
)

from jojolingo.services.adaptive_service import (
    get_recommended_learning_method,
    get_child_level_code,
    get_user_language,
)


def get_text_by_lang(obj, field_prefix, lang):
    if lang == "ru":
        return getattr(obj, f"{field_prefix}_ru", "") or getattr(obj, f"{field_prefix}_uz", "")

    if lang == "en":
        return getattr(obj, f"{field_prefix}_en", "") or getattr(obj, f"{field_prefix}_uz", "")

    if lang == "kk":
        return getattr(obj, f"{field_prefix}_kk", "") or getattr(obj, f"{field_prefix}_uz", "")

    return getattr(obj, f"{field_prefix}_uz", "")


def find_related_vocabulary(exercise):
    text = f"{exercise.question_text} {exercise.correct_answer or ''}".lower()

    words = VocabularyItem.objects.filter(
        is_active=True
    )

    for item in words:
        if item.word.lower() in text:
            return item

        if item.translation_uz.lower() and item.translation_uz.lower() in text:
            return item

        if item.translation_ru.lower() and item.translation_ru.lower() in text:
            return item

        if item.translation_en.lower() and item.translation_en.lower() in text:
            return item

        if item.translation_kk.lower() and item.translation_kk.lower() in text:
            return item

    return None


def find_related_grammar(child, exercise):
    profile = getattr(child, "learning_profile", None)

    if not profile or not profile.current_course:
        return None

    level_code = get_child_level_code(child)

    return GrammarRule.objects.filter(
        course=profile.current_course,
        level_code=level_code,
        is_active=True
    ).order_by("order", "id").first()


def build_rule_based_hint(child, exercise, given_answer=None):
    lang = get_user_language(child)
    level_code = get_child_level_code(child)

    method = get_recommended_learning_method(child)
    vocab = find_related_vocabulary(exercise)
    grammar = find_related_grammar(child, exercise)

    message_parts = []

    message_parts.append(method["message"])

    if vocab:
        translation = ""

        if lang == "ru":
            translation = vocab.translation_ru or vocab.word
        elif lang == "en":
            translation = vocab.translation_en or vocab.word
        elif lang == "kk":
            translation = vocab.translation_kk or vocab.word
        else:
            translation = vocab.translation_uz or vocab.word

        message_parts.append(
            f"Kalit so‘z: {vocab.word}. Ma'nosi: {translation}."
        )

        if vocab.usage_example:
            message_parts.append(
                f"Misol: {vocab.usage_example}"
            )

    if grammar:
        explanation = get_text_by_lang(grammar, "explanation", lang)

        if explanation:
            message_parts.append(explanation)

        if grammar.examples:
            first_example = grammar.examples[0]
            message_parts.append(f"Misol: {first_example}")

    if given_answer:
        message_parts.append(
            "Javobingizni yana bir marta tekshirib ko‘ring."
        )

    if level_code == "A0":
        message_parts = message_parts[:3]

    return {
        "level_code": level_code,
        "method": method["method"],
        "message": " ".join(message_parts),
    }


def build_success_feedback(child, exercise):
    lang = get_user_language(child)

    messages = {
        "uz_latn": "Zo‘r! To‘g‘ri javob berdingiz. Keyingi savolga o‘tamiz.",
        "uz_cyrl": "Зўр! Тўғри жавоб бердингиз. Кейинги саволга ўтамиз.",
        "ru": "Отлично! Это правильный ответ. Переходим дальше.",
        "en": "Great! That is correct. Let's move to the next question.",
        "kk": "Керемет! Бұл дұрыс жауап. Келесі сұраққа өтейік.",
    }

    return messages.get(lang, messages["uz_latn"])