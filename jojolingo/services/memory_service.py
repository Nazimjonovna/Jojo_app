from datetime import timedelta
from django.utils import timezone
from jojolingo.models import VocabularyItem
from jojolingo.models import WordProgress


def calculate_next_review(progress, is_correct):
    if is_correct:
        progress.correct_count += 1
        progress.memory_strength = min(progress.memory_strength + 0.25, 1.0)
    else:
        progress.wrong_count += 1
        progress.memory_strength = max(progress.memory_strength - 0.2, 0.0)

    progress.review_count += 1
    progress.last_reviewed_at = timezone.now()

    if progress.memory_strength < 0.25:
        progress.state = WordProgress.STATE_LEARNING
        delay = timedelta(hours=6)
    elif progress.memory_strength < 0.5:
        progress.state = WordProgress.STATE_LEARNING
        delay = timedelta(days=1)
    elif progress.memory_strength < 0.8:
        progress.state = WordProgress.STATE_KNOWN
        delay = timedelta(days=3)
    else:
        progress.state = WordProgress.STATE_MASTERED
        delay = timedelta(days=7)

    if not is_correct:
        delay = timedelta(hours=3)

    progress.next_review_at = timezone.now() + delay
    progress.save()

    return progress


def update_word_progress(child, vocabulary, is_correct):
    progress, _ = WordProgress.objects.get_or_create(
        child=child,
        vocabulary=vocabulary,
    )

    return calculate_next_review(progress, is_correct)


def get_words_for_review(child, limit=10):
    return WordProgress.objects.filter(
        child=child,
        next_review_at__lte=timezone.now(),
    ).select_related("vocabulary").order_by("next_review_at")[:limit]
    
    
def find_vocabulary_for_exercise(exercise):
    text = f"{exercise.question_text} {exercise.correct_answer or ''}".lower()

    words = VocabularyItem.objects.filter(is_active=True)

    for item in words:
        values = [
            item.word,
            item.translation_uz,
            item.translation_ru,
            item.translation_en,
            item.translation_kk,
        ]

        for value in values:
            if value and value.lower() in text:
                return item

    return None


def update_word_progress_from_exercise(child, exercise, is_correct):
    vocabulary = find_vocabulary_for_exercise(exercise)

    if not vocabulary:
        return None

    return update_word_progress(
        child=child,
        vocabulary=vocabulary,
        is_correct=is_correct,
    )