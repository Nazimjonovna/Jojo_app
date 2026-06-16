from django.core.management.base import BaseCommand

from jojolingo.models import (
    Language,
    LearningCourse,
    Level,
    Unit,
    Lesson,
    Exercise,
    AnswerOption,
    LearningMethodRule,
    PlacementTest,
    PlacementQuestion,
    PlacementAnswerOption,
    VocabularyItem,
    Topic,
    Challenge,
    AICompanion,
)


class Command(BaseCommand):
    help = "Seed initial Jojolingo data"

    def handle(self, *args, **kwargs):
        self.create_languages()
        self.create_topics()
        self.create_courses()
        self.create_challenges()
        self.create_vocabulary_items()
        self.create_learning_method_rules()
        self.create_placement_tests()
        self.create_ai_companions()

        self.stdout.write(
            self.style.SUCCESS("Jojolingo seed data created successfully")
        )

    def create_languages(self):
        languages = [
            {"code": "uz", "name": "Uzbek", "native_name": "O‘zbekcha", "order": 1},
            {"code": "ru", "name": "Russian", "native_name": "Русский", "order": 2},
            {"code": "en", "name": "English", "native_name": "English", "order": 3},
            {"code": "kk", "name": "Kazakh", "native_name": "Қазақша", "order": 4},
        ]

        for item in languages:
            Language.objects.update_or_create(
                code=item["code"],
                defaults=item,
            )

    def create_topics(self):
        topics = [
            ("animals", "Hayvonlar", "Животные", "Animals", "Жануарлар", 1),
            ("cars", "Mashinalar", "Машины", "Cars", "Көліктер", 2),
            ("football", "Futbol", "Футбол", "Football", "Футбол", 3),
            ("space", "Kosmos", "Космос", "Space", "Ғарыш", 4),
            ("school", "Maktab", "Школа", "School", "Мектеп", 5),
            ("family", "Oila", "Семья", "Family", "Отбасы", 6),
        ]

        for name, name_uz, name_ru, name_en, name_kk, order in topics:
            Topic.objects.update_or_create(
                name=name,
                defaults={
                    "name_uz": name_uz,
                    "name_ru": name_ru,
                    "name_en": name_en,
                    "name_kk": name_kk,
                    "order": order,
                    "is_active": True,
                },
            )

    def create_courses(self):
        pairs = [
            ("uz", "en", "O‘zbekcha orqali ingliz tilini o‘rganish"),
            ("uz", "ru", "O‘zbekcha orqali rus tilini o‘rganish"),
            ("uz", "kk", "O‘zbekcha orqali qozoq tilini o‘rganish"),
            ("ru", "en", "Изучение английского через русский"),
            ("ru", "uz", "Изучение узбекского через русский"),
            ("en", "uz", "Learn Uzbek through English"),
            ("en", "ru", "Learn Russian through English"),
            ("kk", "uz", "Қазақша арқылы өзбек тілін үйрену"),
            ("kk", "en", "Қазақша арқылы ағылшын тілін үйрену"),
        ]

        for native_code, learning_code, title in pairs:
            native = Language.objects.get(code=native_code)
            learning = Language.objects.get(code=learning_code)

            course, _ = LearningCourse.objects.update_or_create(
                native_language=native,
                learning_language=learning,
                defaults={
                    "title": title,
                    "description": "Game-based language learning course",
                    "is_active": True,
                },
            )

            self.create_levels(course)
            self.create_basic_units(course)

    def create_levels(self, course):
        levels = [
            ("A0", "Starter", 0, 1),
            ("A1", "Beginner", 300, 2),
            ("A2", "Elementary", 900, 3),
            ("B1", "Intermediate", 1800, 4),
        ]

        for code, title, min_xp, order in levels:
            Level.objects.update_or_create(
                course=course,
                code=code,
                defaults={
                    "title": title,
                    "description": f"{code} level",
                    "min_xp": min_xp,
                    "order": order,
                },
            )

    def create_basic_units(self, course):
        level_a0 = Level.objects.get(course=course, code="A0")
        level_a1 = Level.objects.get(course=course, code="A1")

        unit_greetings, _ = Unit.objects.update_or_create(
            course=course,
            level=level_a0,
            title="Greetings",
            defaults={
                "description": "Learn basic greetings",
                "order": 1,
                "is_active": True,
            },
        )

        unit_numbers, _ = Unit.objects.update_or_create(
            course=course,
            level=level_a0,
            title="Numbers",
            defaults={
                "description": "Learn numbers from 1 to 10",
                "order": 2,
                "is_active": True,
            },
        )

        unit_family, _ = Unit.objects.update_or_create(
            course=course,
            level=level_a1,
            title="Family",
            defaults={
                "description": "Learn family words",
                "order": 3,
                "is_active": True,
            },
        )

        self.create_greeting_lessons(course, unit_greetings)
        self.create_number_lessons(course, unit_numbers)
        self.create_family_lessons(course, unit_family)

    def attach_topic_to_lesson(self, lesson, topic_name):
        topic = Topic.objects.filter(name=topic_name, is_active=True).first()
        if topic:
            lesson.topics.add(topic)

    def create_greeting_lessons(self, course, unit):
        lesson, _ = Lesson.objects.update_or_create(
            unit=unit,
            title="Say Hello",
            defaults={
                "lesson_type": "words",
                "reward_xp": 20,
                "required_accuracy": 70,
                "order": 1,
                "is_active": True,
            },
        )

        self.attach_topic_to_lesson(lesson, "school")

        learning = course.learning_language.code
        data = self.get_greeting_data(learning)

        for idx, item in enumerate(data, start=1):
            exercise, _ = Exercise.objects.update_or_create(
                lesson=lesson,
                order=idx,
                defaults={
                    "exercise_type": "choose",
                    "instruction": item["instruction"],
                    "question_text": item["question"],
                    "correct_answer": item["correct"],
                    "accepted_answers": item.get("accepted", []),
                    "explanation": item["explanation"],
                    "difficulty": 1,
                    "is_active": True,
                },
            )

            self.recreate_options(exercise, item["options"], item["correct"])

    def create_number_lessons(self, course, unit):
        lesson, _ = Lesson.objects.update_or_create(
            unit=unit,
            title="Numbers 1-3",
            defaults={
                "lesson_type": "words",
                "reward_xp": 20,
                "required_accuracy": 70,
                "order": 1,
                "is_active": True,
            },
        )

        self.attach_topic_to_lesson(lesson, "school")

        learning = course.learning_language.code

        numbers = {
            "uz": ["bir", "ikki", "uch"],
            "ru": ["один", "два", "три"],
            "en": ["one", "two", "three"],
            "kk": ["бір", "екі", "үш"],
        }

        items = numbers.get(learning, numbers["en"])

        for idx, correct in enumerate(items, start=1):
            exercise, _ = Exercise.objects.update_or_create(
                lesson=lesson,
                order=idx,
                defaults={
                    "exercise_type": "choose",
                    "instruction": "Choose the correct translation",
                    "question_text": f"What is number {idx}?",
                    "correct_answer": correct,
                    "accepted_answers": [correct],
                    "explanation": f"Correct answer is {correct}",
                    "difficulty": 1,
                    "is_active": True,
                },
            )

            self.recreate_options(exercise, items, correct)

    def create_family_lessons(self, course, unit):
        lesson, _ = Lesson.objects.update_or_create(
            unit=unit,
            title="Family Words",
            defaults={
                "lesson_type": "words",
                "reward_xp": 25,
                "required_accuracy": 75,
                "order": 1,
                "is_active": True,
            },
        )

        self.attach_topic_to_lesson(lesson, "family")

        learning = course.learning_language.code

        family = {
            "uz": ["ota", "ona", "aka"],
            "ru": ["папа", "мама", "брат"],
            "en": ["father", "mother", "brother"],
            "kk": ["әке", "ана", "аға"],
        }

        words = family.get(learning, family["en"])

        for idx, correct in enumerate(words, start=1):
            exercise, _ = Exercise.objects.update_or_create(
                lesson=lesson,
                order=idx,
                defaults={
                    "exercise_type": "choose",
                    "instruction": "Choose the correct word",
                    "question_text": f"Choose word #{idx}",
                    "correct_answer": correct,
                    "accepted_answers": [correct],
                    "explanation": f"Correct answer is {correct}",
                    "difficulty": 2,
                    "is_active": True,
                },
            )

            self.recreate_options(exercise, words, correct)

    def recreate_options(self, exercise, options, correct):
        AnswerOption.objects.filter(exercise=exercise).delete()

        for order, option_text in enumerate(options, start=1):
            AnswerOption.objects.create(
                exercise=exercise,
                text=option_text,
                is_correct=option_text == correct,
                order=order,
            )

    def get_greeting_data(self, learning):
        greetings = {
            "uz": {"hello": "salom", "bye": "xayr", "thanks": "rahmat"},
            "ru": {"hello": "привет", "bye": "пока", "thanks": "спасибо"},
            "en": {"hello": "hello", "bye": "bye", "thanks": "thank you"},
            "kk": {"hello": "сәлем", "bye": "сау бол", "thanks": "рақмет"},
        }

        target = greetings.get(learning, greetings["en"])

        return [
            {
                "instruction": "Choose the correct translation",
                "question": "How do you say 'hello'?",
                "correct": target["hello"],
                "accepted": [target["hello"]],
                "options": list(target.values()),
                "explanation": f"'{target['hello']}' means hello.",
            },
            {
                "instruction": "Choose the correct translation",
                "question": "How do you say 'bye'?",
                "correct": target["bye"],
                "accepted": [target["bye"]],
                "options": list(target.values()),
                "explanation": f"'{target['bye']}' means bye.",
            },
            {
                "instruction": "Choose the correct translation",
                "question": "How do you say 'thank you'?",
                "correct": target["thanks"],
                "accepted": [target["thanks"]],
                "options": list(target.values()),
                "explanation": f"'{target['thanks']}' means thank you.",
            },
        ]

    def create_vocabulary_items(self):
        data = {
            "uz": [
                ("salom", "salom", "привет", "hello", "сәлем", "A0", "Salom, do‘stim!"),
                ("xayr", "xayr", "пока", "bye", "сау бол", "A0", "Xayr, ko‘rishguncha!"),
                ("rahmat", "rahmat", "спасибо", "thank you", "рақмет", "A0", "Rahmat, Jojo!"),
                ("bir", "bir", "один", "one", "бір", "A0", "Menda bir kitob bor."),
                ("ikki", "ikki", "два", "two", "екі", "A0", "Menda ikki olma bor."),
                ("uch", "uch", "три", "three", "үш", "A0", "Uchta qush uchdi."),
                ("ota", "ota", "папа", "father", "әке", "A1", "Mening otam yaxshi inson."),
                ("ona", "ona", "мама", "mother", "ана", "A1", "Mening onam mehribon."),
                ("aka", "aka", "брат", "brother", "аға", "A1", "Mening akam bor."),
            ],
            "ru": [
                ("привет", "salom", "привет", "hello", "сәлем", "A0", "Привет, друг!"),
                ("пока", "xayr", "пока", "bye", "сау бол", "A0", "Пока, до встречи!"),
                ("спасибо", "rahmat", "спасибо", "thank you", "рақмет", "A0", "Спасибо тебе!"),
                ("один", "bir", "один", "one", "бір", "A0", "У меня один мяч."),
                ("два", "ikki", "два", "two", "екі", "A0", "У меня две книги."),
                ("три", "uch", "три", "three", "үш", "A0", "Три птицы летят."),
                ("папа", "ota", "папа", "father", "әке", "A1", "Мой папа дома."),
                ("мама", "ona", "мама", "mother", "ана", "A1", "Моя мама добрая."),
                ("брат", "aka", "брат", "brother", "аға", "A1", "У меня есть брат."),
            ],
            "en": [
                ("hello", "salom", "привет", "hello", "сәлем", "A0", "Hello, my friend!"),
                ("bye", "xayr", "пока", "bye", "сау бол", "A0", "Bye, see you!"),
                ("thank you", "rahmat", "спасибо", "thank you", "рақмет", "A0", "Thank you, Jojo!"),
                ("one", "bir", "один", "one", "бір", "A0", "I have one book."),
                ("two", "ikki", "два", "two", "екі", "A0", "I have two apples."),
                ("three", "uch", "три", "three", "үш", "A0", "Three birds fly."),
                ("father", "ota", "папа", "father", "әке", "A1", "My father is kind."),
                ("mother", "ona", "мама", "mother", "ана", "A1", "My mother is kind."),
                ("brother", "aka", "брат", "brother", "аға", "A1", "I have a brother."),
            ],
            "kk": [
                ("сәлем", "salom", "привет", "hello", "сәлем", "A0", "Сәлем, досым!"),
                ("сау бол", "xayr", "пока", "bye", "сау бол", "A0", "Сау бол, кездескенше!"),
                ("рақмет", "rahmat", "спасибо", "thank you", "рақмет", "A0", "Рақмет саған!"),
                ("бір", "bir", "один", "one", "бір", "A0", "Менде бір кітап бар."),
                ("екі", "ikki", "два", "two", "екі", "A0", "Менде екі алма бар."),
                ("үш", "uch", "три", "three", "үш", "A0", "Үш құс ұшты."),
                ("әке", "ota", "папа", "father", "әке", "A1", "Менің әкем үйде."),
                ("ана", "ona", "мама", "mother", "ана", "A1", "Менің анам мейірімді."),
                ("аға", "aka", "брат", "brother", "аға", "A1", "Менің ағам бар."),
            ],
        }

        for lang_code, words in data.items():
            language = Language.objects.get(code=lang_code)

            for order, item in enumerate(words, start=1):
                (
                    word,
                    translation_uz,
                    translation_ru,
                    translation_en,
                    translation_kk,
                    level_code,
                    usage_example,
                ) = item

                VocabularyItem.objects.update_or_create(
                    language=language,
                    word=word,
                    defaults={
                        "translation_uz": translation_uz,
                        "translation_ru": translation_ru,
                        "translation_en": translation_en,
                        "translation_kk": translation_kk,
                        "level_code": level_code,
                        "usage_example": usage_example,
                        "order": order,
                        "is_active": True,
                    },
                )

    def create_learning_method_rules(self):
        rules = [
            {
                "mistake_type": "choose",
                "level_code": "A0",
                "recommended_method": "visual",
                "message_uz": "Rasm va misol orqali yana ko‘rib chiqamiz.",
                "message_ru": "Давайте посмотрим ещё раз через картинку и пример.",
                "message_en": "Let's review it again with a picture and example.",
                "message_kk": "Сурет және мысал арқылы қайта қарайық.",
            },
            {
                "mistake_type": "translate",
                "level_code": "A0",
                "recommended_method": "repeat",
                "message_uz": "Bu so‘zni yana bir necha marta takrorlaymiz.",
                "message_ru": "Давайте повторим это слово ещё несколько раз.",
                "message_en": "Let's repeat this word a few more times.",
                "message_kk": "Бұл сөзді тағы бірнеше рет қайталайық.",
            },
            {
                "mistake_type": "fill_blank",
                "level_code": "A0",
                "recommended_method": "example",
                "message_uz": "Avval oson misolni ko‘ramiz, keyin yana urinib ko‘ramiz.",
                "message_ru": "Сначала посмотрим простой пример, затем попробуем снова.",
                "message_en": "Let's see an easy example first, then try again.",
                "message_kk": "Алдымен оңай мысалды көрейік, содан кейін қайта көрейік.",
            },
            {
                "mistake_type": "general",
                "level_code": "A0",
                "recommended_method": "review",
                "message_uz": "Keling, bugungi darsni qisqa takrorlab olamiz.",
                "message_ru": "Давайте кратко повторим сегодняшний урок.",
                "message_en": "Let's quickly review today's lesson.",
                "message_kk": "Бүгінгі сабақты қысқаша қайталайық.",
            },
        ]

        for rule in rules:
            LearningMethodRule.objects.update_or_create(
                mistake_type=rule["mistake_type"],
                level_code=rule["level_code"],
                defaults=rule,
            )

    def create_placement_tests(self):
        courses = LearningCourse.objects.filter(is_active=True)

        for course in courses:
            test, _ = PlacementTest.objects.update_or_create(
                course=course,
                title="Placement Test",
                defaults={
                    "description": "Initial test to detect child language level",
                    "is_active": True,
                },
            )

            PlacementQuestion.objects.filter(test=test).delete()

            questions = self.get_placement_questions(course)

            for idx, item in enumerate(questions, start=1):
                question = PlacementQuestion.objects.create(
                    test=test,
                    question_type=item["question_type"],
                    question_text=item["question_text"],
                    correct_answer=item["correct_answer"],
                    level_code=item["level_code"],
                    order=idx,
                    is_active=True,
                )

                for option_order, option_text in enumerate(item["options"], start=1):
                    PlacementAnswerOption.objects.create(
                        question=question,
                        text=option_text,
                        is_correct=option_text == item["correct_answer"],
                        order=option_order,
                    )

    def get_placement_questions(self, course):
        learning = course.learning_language.code

        data = {
            "en": {
                "hello": "hello",
                "bye": "bye",
                "thanks": "thank you",
                "one": "one",
                "two": "two",
                "mother": "mother",
                "father": "father",
                "i_am": "I am a student",
                "i_like": "I like apples",
            },
            "ru": {
                "hello": "привет",
                "bye": "пока",
                "thanks": "спасибо",
                "one": "один",
                "two": "два",
                "mother": "мама",
                "father": "папа",
                "i_am": "Я ученик",
                "i_like": "Я люблю яблоки",
            },
            "uz": {
                "hello": "salom",
                "bye": "xayr",
                "thanks": "rahmat",
                "one": "bir",
                "two": "ikki",
                "mother": "ona",
                "father": "ota",
                "i_am": "Men o‘quvchiman",
                "i_like": "Men olmani yaxshi ko‘raman",
            },
            "kk": {
                "hello": "сәлем",
                "bye": "сау бол",
                "thanks": "рақмет",
                "one": "бір",
                "two": "екі",
                "mother": "ана",
                "father": "әке",
                "i_am": "Мен оқушымын",
                "i_like": "Мен алманы жақсы көремін",
            },
        }

        target = data.get(learning, data["en"])

        return [
            {
                "level_code": "A0",
                "question_type": "choose",
                "question_text": "Choose: hello",
                "correct_answer": target["hello"],
                "options": [target["hello"], target["bye"], target["thanks"]],
            },
            {
                "level_code": "A0",
                "question_type": "choose",
                "question_text": "Choose: thank you",
                "correct_answer": target["thanks"],
                "options": [target["hello"], target["bye"], target["thanks"]],
            },
            {
                "level_code": "A0",
                "question_type": "choose",
                "question_text": "Choose: one",
                "correct_answer": target["one"],
                "options": [target["one"], target["two"], target["hello"]],
            },
            {
                "level_code": "A1",
                "question_type": "choose",
                "question_text": "Choose: mother",
                "correct_answer": target["mother"],
                "options": [target["mother"], target["father"], target["one"]],
            },
            {
                "level_code": "A1",
                "question_type": "choose",
                "question_text": "Choose: father",
                "correct_answer": target["father"],
                "options": [target["mother"], target["father"], target["two"]],
            },
            {
                "level_code": "A1",
                "question_type": "fill_blank",
                "question_text": "Type the word for: hello",
                "correct_answer": target["hello"],
                "options": [],
            },
            {
                "level_code": "A2",
                "question_type": "choose",
                "question_text": "Choose the sentence: I am a student",
                "correct_answer": target["i_am"],
                "options": [target["i_am"], target["i_like"], target["thanks"]],
            },
            {
                "level_code": "A2",
                "question_type": "choose",
                "question_text": "Choose the sentence: I like apples",
                "correct_answer": target["i_like"],
                "options": [target["i_like"], target["i_am"], target["bye"]],
            },
        ]
        
    def create_challenges(self):
        challenges = [
            {
                "title": "Earn 20 XP",
                "description": "Complete exercises and earn 20 XP today.",
                "challenge_type": "daily",
                "target_type": "xp",
                "target_value": 20,
                "reward_xp": 5,
            },
            {
                "title": "Complete 1 Lesson",
                "description": "Finish one lesson.",
                "challenge_type": "daily",
                "target_type": "lesson",
                "target_value": 1,
                "reward_xp": 10,
            },
            {
                "title": "Practice 5 Words",
                "description": "Answer 5 word exercises correctly.",
                "challenge_type": "daily",
                "target_type": "word",
                "target_value": 5,
                "reward_xp": 5,
            },
        ]

        for item in challenges:
            Challenge.objects.update_or_create(
                title=item["title"],
                defaults={
                    **item,
                    "is_active": True,
                },
            )
            
    def create_ai_companions(self):
        companions = [
            {
                "code": "jojo",
                "level": "A0",
                "name_uz": "Jojo",
                "name_ru": "Джоджо",
                "name_en": "Jojo",
                "name_kk": "Джоджо",
                "personality": "friendly",
                "is_active": True,
            },
            {
                "code": "miko",
                "level": "A1",
                "name_uz": "Miko",
                "name_ru": "Мико",
                "name_en": "Miko",
                "name_kk": "Мико",
                "personality": "playful",
                "is_active": True,
            },
            {
                "code": "luna",
                "level": "A1",
                "name_uz": "Luna",
                "name_ru": "Луна",
                "name_en": "Luna",
                "name_kk": "Луна",
                "personality": "calm",
                "is_active": True,
            },
        ]

        for item in companions:
            code = item.pop("code")

            AICompanion.objects.update_or_create(
                code=code,
                defaults=item,
            )