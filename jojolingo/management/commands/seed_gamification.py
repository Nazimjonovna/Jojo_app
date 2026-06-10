"""
management/commands/seed_gamification.py

Ishlatish:  python manage.py seed_gamification
Boshlang'ich achievementlar, daily task shablonlari, companionlar
va companion xabarlarini yaratadi. Idempotent — qayta ishlatsa dublikat qilmaydi.
"""
from django.core.management.base import BaseCommand

from jojolingo.models_gamification import (
    Achievement,
    AICompanion,
    CompanionMessageTemplate,
    DailyTaskTemplate,
)


ACHIEVEMENTS = [
    # code, condition_type, threshold, xp, title_uz, title_ru, title_en
    ("first_lesson", "first_lesson", 1, 10, "Birinchi qadam", "Первый шаг", "First Step"),
    ("lessons_10", "lessons_completed", 10, 20, "10 ta dars", "10 уроков", "10 Lessons"),
    ("lessons_50", "lessons_completed", 50, 50, "50 ta dars", "50 уроков", "50 Lessons"),
    ("streak_3", "streak_days", 3, 15, "3 kunlik olov", "3 дня подряд", "3-Day Streak"),
    ("streak_7", "streak_days", 7, 30, "Bir hafta to'xtamadim!", "Неделя без перерыва!", "7-Day Streak"),
    ("streak_30", "streak_days", 30, 100, "Bir oylik qahramon", "Месяц подряд", "30-Day Streak"),
    ("xp_100", "xp_total", 100, 10, "100 XP", "100 XP", "100 XP"),
    ("xp_1000", "xp_total", 1000, 50, "1000 XP", "1000 XP", "1000 XP"),
    ("words_10", "words_mastered", 10, 15, "10 ta so'z ustasi", "Знаток 10 слов", "10 Words Mastered"),
    ("words_100", "words_mastered", 100, 60, "100 ta so'z ustasi", "Знаток 100 слов", "100 Words Mastered"),
    ("perfect_5", "perfect_lessons", 5, 25, "5 ta mukammal dars", "5 идеальных уроков", "5 Perfect Lessons"),
    ("placement_done", "placement_done", 1, 10, "Darajam aniqlandi!", "Уровень определён!", "Level Found!"),
]

DAILY_TASKS = [
    # task_type, target, xp, title_uz (with {n}), title_ru, title_en
    ("complete_lessons", 1, 10, "{n} ta dars tugat", "Заверши {n} урок", "Complete {n} lesson"),
    ("complete_lessons", 3, 25, "{n} ta dars tugat", "Заверши {n} урока", "Complete {n} lessons"),
    ("review_words", 5, 10, "{n} ta so'zni takrorla", "Повтори {n} слов", "Review {n} words"),
    ("review_words", 10, 20, "{n} ta so'zni takrorla", "Повтори {n} слов", "Review {n} words"),
    ("earn_xp", 20, 10, "{n} XP yig'", "Набери {n} XP", "Earn {n} XP"),
    ("earn_xp", 50, 20, "{n} XP yig'", "Набери {n} XP", "Earn {n} XP"),
    ("perfect_exercises", 5, 15, "{n} ta mashqni xatosiz bajar", "Реши {n} заданий без ошибок", "{n} perfect exercises"),
]

COMPANIONS = [
    ("jojo", "Jojo qushcha", "Птичка Жожо", "Jojo the Bird", "jojo_bird", "cheerful"),
    ("bori", "Bo'rivoy", "Волчонок", "Wolfie", "wolf_cub", "funny"),
]

# trigger, mood_after, text_uz, text_ru, text_en
MESSAGES = [
    ("daily_greeting", "happy", "Salom {child_name}! Bugun nima o'rganamiz?", "Привет, {child_name}! Что выучим сегодня?", "Hi {child_name}! What shall we learn today?"),
    ("daily_greeting", "excited", "{child_name}, men seni kutib turgandim!", "{child_name}, я тебя ждал!", "{child_name}, I was waiting for you!"),
    ("lesson_complete", "happy", "Zo'r ish, {child_name}! Yana bittasini bajaramizmi?", "Отлично, {child_name}! Ещё один?", "Great job, {child_name}! One more?"),
    ("lesson_complete", "happy", "Barakalla! Sen bilan o'rganish juda qiziq!", "Молодец! С тобой учиться весело!", "Well done! Learning with you is fun!"),
    ("perfect_lesson", "proud", "Vooy! Bitta ham xato yo'q! Sen superqahramonsan!", "Вау! Ни одной ошибки! Ты супергерой!", "Wow! Not a single mistake! You're a superhero!"),
    ("mistake", "happy", "Hechqisi yo'q! Xatolardan o'rganamiz. Yana urinib ko'r!", "Ничего страшного! На ошибках учатся. Попробуй ещё!", "It's okay! We learn from mistakes. Try again!"),
    ("mistake", "happy", "Men ham ba'zan xato qilaman. Birga to'g'rilaymiz!", "Я тоже иногда ошибаюсь. Исправим вместе!", "I make mistakes too. Let's fix it together!"),
    ("streak_milestone", "excited", "{streak} kun ketma-ket! Olovimiz kuchaymoqda! 🔥", "{streak} дней подряд! Наш огонь растёт! 🔥", "{streak} days in a row! Our fire is growing! 🔥"),
    ("streak_danger", "worried", "{child_name}, olovimiz o'chib qolmasin! Bitta kichkina dars qilamizmi?", "{child_name}, не дадим огню погаснуть! Один маленький урок?", "{child_name}, don't let our fire go out! One tiny lesson?"),
    ("achievement", "proud", "Yangi mukofot: {achievement}! Men sen bilan faxrlanaman!", "Новая награда: {achievement}! Я горжусь тобой!", "New badge: {achievement}! I'm proud of you!"),
    ("comeback", "excited", "{child_name}, qaytib kelding! Men seni juda sog'indim!", "{child_name}, ты вернулся! Я так скучал!", "{child_name}, you're back! I missed you so much!"),
    ("daily_tasks_done", "proud", "Bugungi hamma vazifa bajarildi! Sen ajoyibsan!", "Все задания на сегодня выполнены! Ты молодец!", "All tasks done for today! You're amazing!"),
]


class Command(BaseCommand):
    help = "Gamification boshlang'ich ma'lumotlarini yuklaydi"

    def handle(self, *args, **options):
        created = {"achievements": 0, "tasks": 0, "companions": 0, "messages": 0}

        for i, (code, ct, th, xp, uz, ru, en) in enumerate(ACHIEVEMENTS):
            _, was_created = Achievement.objects.get_or_create(
                code=code,
                defaults=dict(
                    condition_type=ct, threshold=th, xp_reward=xp,
                    title_uz=uz, title_ru=ru, title_en=en, order=i,
                ),
            )
            created["achievements"] += was_created

        for tt, target, xp, uz, ru, en in DAILY_TASKS:
            _, was_created = DailyTaskTemplate.objects.get_or_create(
                task_type=tt, target_value=target,
                defaults=dict(xp_reward=xp, title_uz=uz, title_ru=ru, title_en=en),
            )
            created["tasks"] += was_created

        for code, uz, ru, en, avatar, pers in COMPANIONS:
            _, was_created = AICompanion.objects.get_or_create(
                code=code,
                defaults=dict(name_uz=uz, name_ru=ru, name_en=en,
                              avatar=avatar, personality=pers),
            )
            created["companions"] += was_created

        for trigger, mood, uz, ru, en in MESSAGES:
            _, was_created = CompanionMessageTemplate.objects.get_or_create(
                trigger=trigger, text_uz=uz,
                defaults=dict(mood_after=mood, text_ru=ru, text_en=en),
            )
            created["messages"] += was_created

        self.stdout.write(self.style.SUCCESS(f"Seed tugadi: {created}"))