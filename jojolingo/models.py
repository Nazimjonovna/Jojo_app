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