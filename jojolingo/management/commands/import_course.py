import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from jojolingo.models import (
    AnswerOption,
    Exercise,
    Language,
    LearningCourse,
    Lesson,
    Level,
    Unit,
    VocabularyItem,
)

EXERCISE_HAS_PAYLOAD = any(
    f.name == "payload" for f in Exercise._meta.get_fields()
)
PAYLOAD_REQUIRED_TYPES = ("word_bank", "match_pairs")


class Command(BaseCommand):
    help = "JSON fayldan to'liq kursni import qiladi (idempotent)"

    def add_arguments(self, parser):
        parser.add_argument("file", type=str, help="Kontent JSON fayl yo'li")
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Faqat validatsiya, DB ga yozmaydi",
        )

    def handle(self, *args, **options):
        path = Path(options["file"])
        if not path.exists():
            raise CommandError(f"Fayl topilmadi: {path}")

        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        errors = self.validate(data)
        if errors:
            for e in errors:
                self.stderr.write(self.style.ERROR(f"  ✗ {e}"))
            raise CommandError(f"Validatsiya xatolari: {len(errors)} ta")

        self.stdout.write(self.style.SUCCESS("✓ Validatsiya o'tdi"))
        if options["dry_run"]:
            self.stdout.write("Dry-run: DB ga yozilmadi")
            return

        with transaction.atomic():
            stats = self.import_data(data)

        self.stdout.write(self.style.SUCCESS(f"Import tugadi: {stats}"))


    def validate(self, data: dict) -> list[str]:
        errors = []
        vocab_words = {v["word"] for v in data.get("vocabulary", [])}

        for field in ("course", "levels"):
            if field not in data:
                errors.append(f"'{field}' bo'limi yo'q")
        if errors:
            return errors

        c = data["course"]
        for f in ("source_language", "target_language", "title_uz"):
            if not c.get(f):
                errors.append(f"course.{f} bo'sh")

        for level in data["levels"]:
            if not level.get("code"):
                errors.append("level.code bo'sh")
            for unit in level.get("units", []):
                for lesson in unit.get("lessons", []):
                    lcode = lesson.get("code", "?")

                    for w in lesson.get("new_words", []) + lesson.get("review_words", []):
                        if w not in vocab_words:
                            errors.append(f"{lcode}: '{w}' vocabulary'da yo'q")

                    for ex in lesson.get("exercises", []):
                        loc = f"{lcode} ex#{ex.get('order')}"
                        ex_type = ex.get("type")

                        if ex_type in PAYLOAD_REQUIRED_TYPES and not EXERCISE_HAS_PAYLOAD:
                            errors.append(
                                f"{loc}: '{ex_type}' uchun Exercise modeliga "
                                f"payload JSONField qo'shish kerak (fayl boshidagi eslatmaga qarang)"
                            )

                        if ex_type == "multiple_choice":
                            opts = ex.get("options", [])
                            if not any(o.get("correct") for o in opts):
                                errors.append(f"{loc}: to'g'ri javob belgilanmagan")
                            if len(opts) < 2:
                                errors.append(f"{loc}: kamida 2 ta variant kerak")
                        elif ex_type in ("translate", "fill_blank", "listen", "word_bank"):
                            if not ex.get("correct_answers"):
                                errors.append(f"{loc}: correct_answers bo'sh")
                        elif ex_type == "match_pairs":
                            if len(ex.get("pairs", [])) < 2:
                                errors.append(f"{loc}: kamida 2 juftlik kerak")
                        else:
                            errors.append(f"{loc}: noma'lum type '{ex_type}'")

                        if ex.get("word") and ex["word"] not in vocab_words:
                            errors.append(f"{loc}: '{ex['word']}' vocabulary'da yo'q")
        return errors


    def import_data(self, data: dict) -> dict:
        stats = {"vocab": 0, "levels": 0, "units": 0, "lessons": 0, "exercises": 0}
        c = data["course"]
        source_code = c["source_language"]   # bolaning ona tili (masalan uz)
        target_code = c["target_language"]   # o'rganilayotgan til (masalan en)

        native_lang, _ = Language.objects.get_or_create(
            code=source_code, defaults={"name": source_code}
        )
        learning_lang, _ = Language.objects.get_or_create(
            code=target_code, defaults={"name": target_code}
        )

        course, _ = LearningCourse.objects.update_or_create(
            native_language=native_lang,
            learning_language=learning_lang,
            defaults=dict(
                title=c.get("title_uz", ""),
                description=c.get("description_uz", ""),
                is_active=True,
            ),
        )

        # ---- Vocabulary: o'rganilayotgan tilga bog'lanadi ----
        vocab_map = {}
        for i, v in enumerate(data.get("vocabulary", [])):
            translations = {
                f"translation_{source_code}": v.get("translation", "")
            }
            # JSON'da boshqa tillar ham berilgan bo'lsa (translation_ru, ...):
            for lang in ("uz", "ru", "en", "kk"):
                key = f"translation_{lang}"
                if v.get(key):
                    translations[key] = v[key]

            item, _ = VocabularyItem.objects.update_or_create(
                language=learning_lang,
                word=v["word"],
                defaults=dict(
                    level_code=v.get("level_code", ""),
                    usage_example=v.get("example", ""),
                    image=v.get("image", ""),
                    audio=v.get("audio", ""),
                    order=v.get("order", i),
                    is_active=True,
                    **translations,
                ),
            )
            vocab_map[v["word"]] = item
            stats["vocab"] += 1

        # ---- Levels / Units / Lessons / Exercises ----
        for lv in data["levels"]:
            level, _ = Level.objects.update_or_create(
                course=course,
                code=lv["code"],
                defaults=dict(
                    title=lv.get("title_uz", lv["code"]),
                    description=lv.get("description_uz", ""),
                    min_xp=lv.get("min_xp", 0),
                    order=lv.get("order", 0),
                ),
            )
            stats["levels"] += 1

            for u in lv.get("units", []):
                unit, _ = Unit.objects.update_or_create(
                    course=course,
                    level=level,
                    order=u.get("order", 0),
                    defaults=dict(
                        title=u.get("title_uz", ""),
                        description=u.get("description_uz", ""),
                        icon=u.get("icon", ""),
                        is_active=True,
                    ),
                )
                stats["units"] += 1

                for ls in u.get("lessons", []):
                    lesson_defaults = dict(
                        title=ls.get("title_uz", ""),
                        reward_xp=ls.get("xp_reward", 10),
                        is_active=True,
                    )
                    if "lesson_type" in ls:
                        lesson_defaults["lesson_type"] = ls["lesson_type"]
                    elif ls.get("is_review"):
                        lesson_defaults["lesson_type"] = "review"
                    if "required_accuracy" in ls:
                        lesson_defaults["required_accuracy"] = ls["required_accuracy"]

                    lesson, _ = Lesson.objects.update_or_create(
                        unit=unit,
                        order=ls.get("order", 0),
                        defaults=lesson_defaults,
                    )
                    stats["lessons"] += 1

                    stats["exercises"] += self._import_exercises(
                        lesson, ls.get("exercises", [])
                    )
        return stats

    def _import_exercises(self, lesson, exercises: list) -> int:
        count = 0
        for ex in exercises:
            ex_type = ex["type"]
            accepted = ex.get("correct_answers", [])

            # correct_answer (bitta asosiy javob)
            if ex_type == "multiple_choice":
                correct = next(
                    (o["text"] for o in ex.get("options", []) if o.get("correct")), ""
                )
            else:
                correct = accepted[0] if accepted else ""

            defaults = dict(
                exercise_type=ex_type,
                instruction=ex.get("instruction_uz", ""),
                question_text=ex.get("prompt_uz", ""),
                correct_answer=correct,
                accepted_answers=accepted,
                explanation=ex.get("hint_uz", ""),
                image=ex.get("image", ""),
                audio=ex.get("audio", ""),
                is_active=True,
            )
            if "difficulty" in ex:
                defaults["difficulty"] = ex["difficulty"]
            if EXERCISE_HAS_PAYLOAD:
                defaults["payload"] = {
                    k: ex[k] for k in ("word_bank", "pairs") if k in ex
                }

            exercise, _ = Exercise.objects.update_or_create(
                lesson=lesson,
                order=ex["order"],
                defaults=defaults,
            )

            # multiple_choice variantlari — AnswerOption (related_name='options')
            if ex_type == "multiple_choice":
                exercise.options.all().delete()
                AnswerOption.objects.bulk_create([
                    AnswerOption(
                        exercise=exercise,
                        text=o["text"],
                        is_correct=o.get("correct", False),
                        order=i,
                    )
                    for i, o in enumerate(ex.get("options", []))
                ])
            count += 1
        return count