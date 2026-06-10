import re
import unicodedata


def normalize_answer(text):
    if text is None:
        return ""

    text = str(text).strip().lower()

    # unicode normalizatsiya
    text = unicodedata.normalize("NFKC", text)

    # apostroflarni bir xil qilish
    text = text.replace("’", "'").replace("‘", "'").replace("`", "'")

    # tinish belgilarini olib tashlash
    text = re.sub(r"[^\w\s']", " ", text, flags=re.UNICODE)

    # ortiqcha space
    text = re.sub(r"\s+", " ", text).strip()

    return text


def is_text_answer_correct(given_answer, correct_answer, accepted_answers=None):
    given = normalize_answer(given_answer)
    correct = normalize_answer(correct_answer)

    if given == correct:
        return True

    if accepted_answers:
        for answer in accepted_answers:
            if given == normalize_answer(answer):
                return True

    return False