from django.db import models
from django.conf import settings
from django.utils import timezone


class Language(models.Model):
    CODE_UZ = "uz"
    CODE_RU = "ru"
    CODE_EN = "en"
    CODE_KK = "kk"

    CODE_CHOICES = (
        (CODE_UZ, "Uzbek"),
        (CODE_RU, "Russian"),
        (CODE_EN, "English"),
        (CODE_KK, "Kazakh"),
    )

    code = models.CharField(max_length=10, choices=CODE_CHOICES, unique=True)
    name = models.CharField(max_length=100)
    native_name = models.CharField(max_length=100)
    flag_icon = models.ImageField(upload_to="jojolingo/languages/", null=True, blank=True)
    is_active = models.BooleanField(default=True)

    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.native_name


class LearningCourse(models.Model):
    native_language = models.ForeignKey(
        Language,
        on_delete=models.CASCADE,
        related_name="native_courses"
    )
    learning_language = models.ForeignKey(
        Language,
        on_delete=models.CASCADE,
        related_name="learning_courses"
    )

    title = models.CharField(max_length=150)
    description = models.TextField(null=True, blank=True)

    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ("native_language", "learning_language")
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.native_language.code} -> {self.learning_language.code}"


class Level(models.Model):
    LEVEL_A0 = "A0"
    LEVEL_A1 = "A1"
    LEVEL_A2 = "A2"
    LEVEL_B1 = "B1"

    LEVEL_CHOICES = (
        (LEVEL_A0, "A0 - Starter"),
        (LEVEL_A1, "A1 - Beginner"),
        (LEVEL_A2, "A2 - Elementary"),
        (LEVEL_B1, "B1 - Intermediate"),
    )

    course = models.ForeignKey(
        LearningCourse,
        on_delete=models.CASCADE,
        related_name="levels"
    )

    code = models.CharField(max_length=10, choices=LEVEL_CHOICES)
    title = models.CharField(max_length=150)
    description = models.TextField(null=True, blank=True)

    min_xp = models.PositiveIntegerField(default=0)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ("course", "code")
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.course} - {self.code}"


class Unit(models.Model):
    course = models.ForeignKey(
        LearningCourse,
        on_delete=models.CASCADE,
        related_name="units"
    )
    level = models.ForeignKey(
        Level,
        on_delete=models.CASCADE,
        related_name="units"
    )

    title = models.CharField(max_length=150)
    description = models.TextField(null=True, blank=True)

    icon = models.ImageField(upload_to="jojolingo/units/", null=True, blank=True)
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.title


class Lesson(models.Model):
    LESSON_WORDS = "words"
    LESSON_GRAMMAR = "grammar"
    LESSON_DIALOGUE = "dialogue"
    LESSON_REVIEW = "review"
    LESSON_TEST = "test"

    LESSON_TYPE_CHOICES = (
        (LESSON_WORDS, "Words"),
        (LESSON_GRAMMAR, "Grammar"),
        (LESSON_DIALOGUE, "Dialogue"),
        (LESSON_REVIEW, "Review"),
        (LESSON_TEST, "Test"),
    )

    unit = models.ForeignKey(
        Unit,
        on_delete=models.CASCADE,
        related_name="lessons"
    )

    title = models.CharField(max_length=150)
    lesson_type = models.CharField(max_length=20, choices=LESSON_TYPE_CHOICES)

    reward_xp = models.PositiveIntegerField(default=10)
    required_accuracy = models.PositiveIntegerField(default=80)

    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.title


class Exercise(models.Model):
    TYPE_CHOOSE = "choose"
    TYPE_MATCH = "match"
    TYPE_TRANSLATE = "translate"
    TYPE_FILL_BLANK = "fill_blank"
    TYPE_DIALOGUE = "dialogue"

    TYPE_CHOICES = (
        (TYPE_CHOOSE, "Choose correct answer"),
        (TYPE_MATCH, "Match words"),
        (TYPE_TRANSLATE, "Translate"),
        (TYPE_FILL_BLANK, "Fill in the blank"),
        (TYPE_DIALOGUE, "Dialogue"),
    )

    lesson = models.ForeignKey(
        Lesson,
        on_delete=models.CASCADE,
        related_name="exercises"
    )
    
    accepted_answers = models.JSONField(
        default=list,
        blank=True,
        help_text="Alternative correct answers, masalan: ['hi', 'hello']"
    )

    exercise_type = models.CharField(max_length=30, choices=TYPE_CHOICES)

    instruction = models.CharField(max_length=255)
    question_text = models.TextField()

    correct_answer = models.TextField(null=True, blank=True)
    explanation = models.TextField(null=True, blank=True)

    image = models.ImageField(upload_to="jojolingo/exercises/", null=True, blank=True)
    audio = models.FileField(upload_to="jojolingo/audio/", null=True, blank=True)

    difficulty = models.PositiveIntegerField(default=1)

    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    payload = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.lesson_id} - {self.exercise_type}"


class AnswerOption(models.Model):
    exercise = models.ForeignKey(
        Exercise,
        on_delete=models.CASCADE,
        related_name="options"
    )

    text = models.CharField(max_length=255)
    is_correct = models.BooleanField(default=False)

    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.text


class ChildLearningProfile(models.Model):
    child = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="learning_profile"
    )

    current_course = models.ForeignKey(
        LearningCourse,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="child_profiles"
    )

    current_level = models.ForeignKey(
        Level,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="child_profiles"
    )

    total_xp = models.PositiveIntegerField(default=0)
    streak_days = models.PositiveIntegerField(default=0)

    last_learning_date = models.DateField(null=True, blank=True)

    ai_friend_name = models.CharField(max_length=50, default="Jojo")
    ai_friend_level = models.CharField(max_length=10, default="A0")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Learning profile: {self.child_id}"


class LessonProgress(models.Model):
    child = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="lesson_progresses"
    )

    lesson = models.ForeignKey(
        Lesson,
        on_delete=models.CASCADE,
        related_name="progresses"
    )

    is_completed = models.BooleanField(default=False)

    score = models.PositiveIntegerField(default=0)
    accuracy = models.FloatField(default=0)

    earned_xp = models.PositiveIntegerField(default=0)
    attempt_count = models.PositiveIntegerField(default=0)

    completed_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("child", "lesson")

    def __str__(self):
        return f"{self.child_id} - {self.lesson_id}"


class MistakeLog(models.Model):
    child = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="mistake_logs"
    )

    exercise = models.ForeignKey(
        Exercise,
        on_delete=models.CASCADE,
        related_name="mistake_logs"
    )

    given_answer = models.TextField(null=True, blank=True)
    correct_answer = models.TextField(null=True, blank=True)

    mistake_type = models.CharField(max_length=100, null=True, blank=True)
    explanation = models.TextField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.child_id} - {self.exercise_id}"


class AIConversation(models.Model):
    child = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ai_conversations"
    )

    course = models.ForeignKey(
        LearningCourse,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ai_conversations"
    )

    lesson = models.ForeignKey(
        Lesson,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ai_conversations"
    )

    level_code = models.CharField(max_length=10, default="A0")

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"AI conversation {self.id} - child {self.child_id}"


class AIMessage(models.Model):
    ROLE_USER = "user"
    ROLE_ASSISTANT = "assistant"
    ROLE_SYSTEM = "system"

    ROLE_CHOICES = (
        (ROLE_USER, "User"),
        (ROLE_ASSISTANT, "Assistant"),
        (ROLE_SYSTEM, "System"),
    )

    conversation = models.ForeignKey(
        AIConversation,
        on_delete=models.CASCADE,
        related_name="messages"
    )

    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    content = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.conversation_id} - {self.role}"
    
    
class PlacementTest(models.Model):
    course = models.ForeignKey(
        LearningCourse,
        on_delete=models.CASCADE,
        related_name="placement_tests"
    )

    title = models.CharField(max_length=150, default="Placement Test")
    description = models.TextField(null=True, blank=True)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.course} - {self.title}"


class PlacementQuestion(models.Model):
    QUESTION_CHOOSE = "choose"
    QUESTION_TRANSLATE = "translate"
    QUESTION_FILL_BLANK = "fill_blank"

    QUESTION_TYPE_CHOICES = (
        (QUESTION_CHOOSE, "Choose"),
        (QUESTION_TRANSLATE, "Translate"),
        (QUESTION_FILL_BLANK, "Fill blank"),
    )

    test = models.ForeignKey(
        PlacementTest,
        on_delete=models.CASCADE,
        related_name="questions"
    )

    question_type = models.CharField(
        max_length=30,
        choices=QUESTION_TYPE_CHOICES,
        default=QUESTION_CHOOSE
    )

    question_text = models.TextField()
    correct_answer = models.TextField()

    level_code = models.CharField(
        max_length=10,
        choices=Level.LEVEL_CHOICES,
        default=Level.LEVEL_A0
    )

    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.test_id} - {self.level_code}"


class PlacementAnswerOption(models.Model):
    question = models.ForeignKey(
        PlacementQuestion,
        on_delete=models.CASCADE,
        related_name="options"
    )

    text = models.CharField(max_length=255)
    is_correct = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.text


class PlacementResult(models.Model):
    child = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="placement_results"
    )

    test = models.ForeignKey(
        PlacementTest,
        on_delete=models.CASCADE,
        related_name="results"
    )

    score = models.PositiveIntegerField(default=0)
    total = models.PositiveIntegerField(default=0)
    accuracy = models.FloatField(default=0)

    assigned_level = models.ForeignKey(
        Level,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="placement_results"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.child_id} - {self.test_id} - {self.accuracy}%"
    
    
class VocabularyItem(models.Model):
    language = models.ForeignKey(
        Language,
        on_delete=models.CASCADE,
        related_name="vocabulary_items"
    )

    word = models.CharField(max_length=150)
    translation_uz = models.CharField(max_length=150, blank=True, default="")
    translation_ru = models.CharField(max_length=150, blank=True, default="")
    translation_en = models.CharField(max_length=150, blank=True, default="")
    translation_kk = models.CharField(max_length=150, blank=True, default="")

    level_code = models.CharField(
        max_length=10,
        choices=Level.LEVEL_CHOICES,
        default=Level.LEVEL_A0
    )

    image = models.ImageField(
        upload_to="jojolingo/vocabulary/",
        null=True,
        blank=True
    )

    audio = models.FileField(
        upload_to="jojolingo/vocabulary/audio/",
        null=True,
        blank=True
    )

    usage_example = models.TextField(blank=True, default="")
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["level_code", "order", "id"]

    def __str__(self):
        return self.word


class GrammarRule(models.Model):
    course = models.ForeignKey(
        LearningCourse,
        on_delete=models.CASCADE,
        related_name="grammar_rules"
    )

    title = models.CharField(max_length=150)
    explanation_uz = models.TextField(blank=True, default="")
    explanation_ru = models.TextField(blank=True, default="")
    explanation_en = models.TextField(blank=True, default="")
    explanation_kk = models.TextField(blank=True, default="")

    level_code = models.CharField(
        max_length=10,
        choices=Level.LEVEL_CHOICES,
        default=Level.LEVEL_A0
    )

    examples = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["level_code", "order", "id"]

    def __str__(self):
        return self.title


class LearningMethodRule(models.Model):
    METHOD_REPEAT = "repeat"
    METHOD_VISUAL = "visual"
    METHOD_EXAMPLE = "example"
    METHOD_DIALOGUE = "dialogue"
    METHOD_GAME = "game"
    METHOD_REVIEW = "review"

    METHOD_CHOICES = (
        (METHOD_REPEAT, "Repeat"),
        (METHOD_VISUAL, "Visual"),
        (METHOD_EXAMPLE, "Example"),
        (METHOD_DIALOGUE, "Dialogue"),
        (METHOD_GAME, "Game"),
        (METHOD_REVIEW, "Review"),
    )

    mistake_type = models.CharField(max_length=100)
    level_code = models.CharField(max_length=10, default="A0")
    recommended_method = models.CharField(max_length=30, choices=METHOD_CHOICES)

    message_uz = models.TextField()
    message_ru = models.TextField(blank=True, default="")
    message_en = models.TextField(blank=True, default="")
    message_kk = models.TextField(blank=True, default="")

    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.level_code} - {self.mistake_type} - {self.recommended_method}"
    
    
class WordProgress(models.Model):
    STATE_NEW = "new"
    STATE_LEARNING = "learning"
    STATE_KNOWN = "known"
    STATE_MASTERED = "mastered"

    STATE_CHOICES = (
        (STATE_NEW, "New"),
        (STATE_LEARNING, "Learning"),
        (STATE_KNOWN, "Known"),
        (STATE_MASTERED, "Mastered"),
    )

    child = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="word_progresses"
    )

    vocabulary = models.ForeignKey(
        VocabularyItem,
        on_delete=models.CASCADE,
        related_name="progresses"
    )

    state = models.CharField(
        max_length=20,
        choices=STATE_CHOICES,
        default=STATE_NEW
    )

    correct_count = models.PositiveIntegerField(default=0)
    wrong_count = models.PositiveIntegerField(default=0)

    review_count = models.PositiveIntegerField(default=0)
    memory_strength = models.FloatField(default=0.0)

    next_review_at = models.DateTimeField(null=True, blank=True)
    last_reviewed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("child", "vocabulary")
        ordering = ["next_review_at", "-updated_at"]

    def __str__(self):
        return f"{self.child_id} - {self.vocabulary.word} - {self.state}"
    
    
class Achievement(models.Model):
    class ConditionType(models.TextChoices):
        LESSONS_COMPLETED = "lessons_completed", "Tugatilgan darslar soni"
        XP_TOTAL = "xp_total", "Jami XP"
        STREAK_DAYS = "streak_days", "Streak kunlari"
        WORDS_MASTERED = "words_mastered", "O'zlashtirilgan so'zlar"
        PERFECT_LESSONS = "perfect_lessons", "Xatosiz darslar"
        PLACEMENT_DONE = "placement_done", "Placement test tugatildi"
        COURSE_COMPLETED = "course_completed", "Kurs tugatildi"
        FIRST_LESSON = "first_lesson", "Birinchi dars"
 
    code = models.SlugField(max_length=64, unique=True)  # masalan: "streak_7"
    condition_type = models.CharField(max_length=32, choices=ConditionType.choices)
    threshold = models.PositiveIntegerField(default=1)   # masalan streak_days uchun 7
 
    # Ko'p tilli matnlar (interfeys tili = bolaning ona tili)
    title_uz = models.CharField(max_length=120)
    title_ru = models.CharField(max_length=120, blank=True)
    title_en = models.CharField(max_length=120, blank=True)
    title_kk = models.CharField(max_length=120, blank=True)
 
    description_uz = models.CharField(max_length=255, blank=True)
    description_ru = models.CharField(max_length=255, blank=True)
    description_en = models.CharField(max_length=255, blank=True)
    description_kk = models.CharField(max_length=255, blank=True)
 
    icon = models.CharField(max_length=64, blank=True)   # frontend asset nomi
    xp_reward = models.PositiveIntegerField(default=0)
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
 
    class Meta:
        ordering = ["order", "threshold"]
        indexes = [models.Index(fields=["condition_type", "is_active"])]
 
    def __str__(self):
        return self.code
 
    def title_for(self, lang_code: str) -> str:
        return getattr(self, f"title_{lang_code}", "") or self.title_uz
 
 
class ChildAchievement(models.Model):
    profile = models.ForeignKey(
        "jojolingo.ChildLearningProfile",
        on_delete=models.CASCADE,
        related_name="achievements",
    )
    achievement = models.ForeignKey(Achievement, on_delete=models.CASCADE)
    earned_at = models.DateTimeField(auto_now_add=True)
    is_seen = models.BooleanField(default=False)  # "yangi badge" popup uchun
 
    class Meta:
        unique_together = [("profile", "achievement")]
        ordering = ["-earned_at"]
 
 
class DailyTaskTemplate(models.Model):
    class TaskType(models.TextChoices):
        COMPLETE_LESSONS = "complete_lessons", "N ta dars tugat"
        REVIEW_WORDS = "review_words", "N ta so'zni takrorla"
        EARN_XP = "earn_xp", "N XP yig'"
        PERFECT_EXERCISES = "perfect_exercises", "N ta mashqni xatosiz bajar"
 
    task_type = models.CharField(max_length=32, choices=TaskType.choices)
    target_value = models.PositiveIntegerField()
    xp_reward = models.PositiveIntegerField(default=10)
 
    title_uz = models.CharField(max_length=120)
    title_ru = models.CharField(max_length=120, blank=True)
    title_en = models.CharField(max_length=120, blank=True)
    title_kk = models.CharField(max_length=120, blank=True)
 
    # Qaysi levellarga mos: bo'sh bo'lsa hammaga
    min_level = models.CharField(max_length=8, blank=True)   # "A0"
    max_level = models.CharField(max_length=8, blank=True)   # "B1"
    weight = models.PositiveIntegerField(default=1)           # random tanlovda og'irlik
    is_active = models.BooleanField(default=True)
 
    def __str__(self):
        return f"{self.task_type}:{self.target_value}"
 
 
class ChildDailyTask(models.Model):
    profile = models.ForeignKey(
        "jojolingo.ChildLearningProfile",
        on_delete=models.CASCADE,
        related_name="daily_tasks",
    )
    template = models.ForeignKey(DailyTaskTemplate, on_delete=models.CASCADE)
    date = models.DateField(default=timezone.localdate)
    progress = models.PositiveIntegerField(default=0)
    target = models.PositiveIntegerField()           # template'dan nusxa (template o'zgarsa task buzilmaydi)
    xp_reward = models.PositiveIntegerField()        # nusxa
    completed_at = models.DateTimeField(null=True, blank=True)
    reward_claimed = models.BooleanField(default=False)
 
    class Meta:
        unique_together = [("profile", "template", "date")]
        indexes = [models.Index(fields=["profile", "date"])]
 
    @property
    def is_completed(self) -> bool:
        return self.completed_at is not None
 
 
class AICompanion(models.Model):
    """Tanlash mumkin bo'lgan personajlar: masalan Jojo qushcha, Bo'ri bolasi..."""
    code = models.SlugField(max_length=32, unique=True)
    name_uz = models.CharField(max_length=64)
    name_ru = models.CharField(max_length=64, blank=True)
    name_en = models.CharField(max_length=64, blank=True)
    name_kk = models.CharField(max_length=64, blank=True)
    avatar = models.CharField(max_length=64)          # frontend asset
    personality = models.CharField(max_length=32, default="cheerful")  # cheerful / calm / funny
    is_active = models.BooleanField(default=True)
 
    def __str__(self):
        return self.code
 
 
class ChildCompanionState(models.Model):
    class Mood(models.TextChoices):
        HAPPY = "happy", "Xursand"
        EXCITED = "excited", "Hayajonda"
        SLEEPY = "sleepy", "Uyqusiragan"      # bola uzoq kirmasa
        WORRIED = "worried", "Xavotirda"       # streak yonish arafasida
        PROUD = "proud", "Faxrlanmoqda"        # achievement olganda
 
    profile = models.OneToOneField(
        "jojolingo.ChildLearningProfile",
        on_delete=models.CASCADE,
        related_name="companion_state",
    )
    companion = models.ForeignKey(AICompanion, on_delete=models.PROTECT)
    mood = models.CharField(max_length=16, choices=Mood.choices, default=Mood.HAPPY)
    friendship_xp = models.PositiveIntegerField(default=0)   # bola o'qigan sari "do'stlik" oshadi
    friendship_level = models.PositiveIntegerField(default=1)
    last_interaction = models.DateTimeField(auto_now=True)
 
 
class CompanionMessageTemplate(models.Model):
    """Rule-based xabarlar. Keyinchalik local AI shu template'lar uslubida
    javob generatsiya qiladi — hozircha tayyor matnlardan tanlaymiz."""
 
    class Trigger(models.TextChoices):
        DAILY_GREETING = "daily_greeting", "Kunlik salomlashish"
        LESSON_COMPLETE = "lesson_complete", "Dars tugadi"
        PERFECT_LESSON = "perfect_lesson", "Xatosiz dars"
        MISTAKE = "mistake", "Xato qilindi"
        STREAK_MILESTONE = "streak_milestone", "Streak bosqichi"
        STREAK_DANGER = "streak_danger", "Streak yonish arafasida"
        ACHIEVEMENT = "achievement", "Achievement olindi"
        COMEBACK = "comeback", "Uzoq tanaffusdan qaytdi"
        DAILY_TASKS_DONE = "daily_tasks_done", "Kunlik tasklar tugadi"
 
    companion = models.ForeignKey(
        AICompanion, on_delete=models.CASCADE, null=True, blank=True,
        help_text="Bo'sh bo'lsa — barcha personajlar uchun umumiy",
    )
    trigger = models.CharField(max_length=32, choices=Trigger.choices)
 
    # Placeholderlar: {child_name}, {streak}, {xp}, {word}, {companion_name}
    text_uz = models.CharField(max_length=255)
    text_ru = models.CharField(max_length=255, blank=True)
    text_en = models.CharField(max_length=255, blank=True)
    text_kk = models.CharField(max_length=255, blank=True)
 
    mood_after = models.CharField(  # xabar bilan birga companion mood'i shu holatga o'tadi
        max_length=16, choices=ChildCompanionState.Mood.choices,
        default=ChildCompanionState.Mood.HAPPY,
    )
    weight = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)
 
    class Meta:
        indexes = [models.Index(fields=["trigger", "is_active"])]
 
    def __str__(self):
        return f"{self.trigger}: {self.text_uz[:40]}"
 
 
class ChildDailyActivity(models.Model):
    profile = models.ForeignKey(
        "jojolingo.ChildLearningProfile",
        on_delete=models.CASCADE,
        related_name="daily_activities",
    )
    date = models.DateField(default=timezone.localdate)
 
    xp_earned = models.PositiveIntegerField(default=0)
    lessons_completed = models.PositiveIntegerField(default=0)
    exercises_answered = models.PositiveIntegerField(default=0)
    correct_answers = models.PositiveIntegerField(default=0)
    wrong_answers = models.PositiveIntegerField(default=0)
    words_reviewed = models.PositiveIntegerField(default=0)
    time_spent_seconds = models.PositiveIntegerField(default=0)
 
    class Meta:
        unique_together = [("profile", "date")]
        indexes = [models.Index(fields=["profile", "date"])]
        ordering = ["-date"]
 
    def __str__(self):
        return f"{self.profile_id} @ {self.date}"
 
    @property
    def accuracy(self) -> float:
        total = self.correct_answers + self.wrong_answers
        return round(self.correct_answers / total * 100, 1) if total else 0.0
 