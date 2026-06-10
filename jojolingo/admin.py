from django.contrib import admin

from .models import (
    Language,
    LearningCourse,
    Level,
    Unit,
    Lesson,
    Exercise,
    AnswerOption,
    ChildLearningProfile,
    LessonProgress,
    MistakeLog,
    AIConversation,
    AIMessage,
    PlacementTest,
    PlacementQuestion,
    PlacementAnswerOption,
    PlacementResult,
    VocabularyItem,
    GrammarRule,
    LearningMethodRule,
)


@admin.register(Language)
class LanguageAdmin(admin.ModelAdmin):
    list_display = ("id", "code", "name", "native_name", "is_active", "order")
    list_filter = ("is_active",)
    search_fields = ("code", "name", "native_name")
    ordering = ("order", "id")


@admin.register(LearningCourse)
class LearningCourseAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "native_language",
        "learning_language",
        "title",
        "is_active",
        "order",
    )
    list_filter = ("is_active", "native_language", "learning_language")
    search_fields = ("title", "description")
    ordering = ("order", "id")


@admin.register(Level)
class LevelAdmin(admin.ModelAdmin):
    list_display = ("id", "course", "code", "title", "min_xp", "order")
    list_filter = ("course", "code")
    search_fields = ("title", "description")
    ordering = ("course", "order", "id")


@admin.register(Unit)
class UnitAdmin(admin.ModelAdmin):
    list_display = ("id", "course", "level", "title", "is_active", "order")
    list_filter = ("is_active", "course", "level")
    search_fields = ("title", "description")
    ordering = ("course", "level", "order", "id")


class AnswerOptionInline(admin.TabularInline):
    model = AnswerOption
    extra = 4


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "unit",
        "title",
        "lesson_type",
        "reward_xp",
        "required_accuracy",
        "is_active",
        "order",
    )
    list_filter = ("lesson_type", "is_active", "unit")
    search_fields = ("title",)
    ordering = ("unit", "order", "id")


@admin.register(Exercise)
class ExerciseAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "lesson",
        "exercise_type",
        "instruction",
        "difficulty",
        "is_active",
        "order",
    )
    list_filter = ("exercise_type", "is_active", "difficulty", "lesson")
    search_fields = (
        "instruction",
        "question_text",
        "correct_answer",
    )
    ordering = ("lesson", "order", "id")
    inlines = [AnswerOptionInline]

    fieldsets = (
        ("Basic", {
            "fields": (
                "lesson",
                "exercise_type",
                "instruction",
                "question_text",
                "difficulty",
                "order",
                "is_active",
            )
        }),
        ("Answer", {
            "fields": (
                "correct_answer",
                "accepted_answers",
                "explanation",
            )
        }),
        ("Media", {
            "fields": (
                "image",
                "audio",
            )
        }),
    )


@admin.register(AnswerOption)
class AnswerOptionAdmin(admin.ModelAdmin):
    list_display = ("id", "exercise", "text", "is_correct", "order")
    list_filter = ("is_correct",)
    search_fields = ("text",)
    ordering = ("exercise", "order", "id")


@admin.register(ChildLearningProfile)
class ChildLearningProfileAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "child",
        "current_course",
        "current_level",
        "total_xp",
        "streak_days",
        "ai_friend_name",
        "ai_friend_level",
    )
    list_filter = ("current_course", "current_level")
    search_fields = ("child__phone", "child__full_name", "ai_friend_name")


@admin.register(LessonProgress)
class LessonProgressAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "child",
        "lesson",
        "is_completed",
        "score",
        "accuracy",
        "earned_xp",
        "attempt_count",
        "completed_at",
    )
    list_filter = ("is_completed", "lesson")
    search_fields = ("child__phone", "child__full_name", "lesson__title")


@admin.register(MistakeLog)
class MistakeLogAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "child",
        "exercise",
        "given_answer",
        "correct_answer",
        "mistake_type",
        "created_at",
    )
    list_filter = ("mistake_type",)
    search_fields = (
        "child__phone",
        "child__full_name",
        "given_answer",
        "correct_answer",
        "explanation",
    )


class AIMessageInline(admin.TabularInline):
    model = AIMessage
    extra = 0


@admin.register(AIConversation)
class AIConversationAdmin(admin.ModelAdmin):
    list_display = ("id", "child", "course", "lesson", "level_code", "created_at")
    list_filter = ("course", "lesson", "level_code")
    search_fields = ("child__phone", "child__full_name")
    inlines = [AIMessageInline]


@admin.register(AIMessage)
class AIMessageAdmin(admin.ModelAdmin):
    list_display = ("id", "conversation", "role", "created_at")
    list_filter = ("role",)
    search_fields = ("content",)
    
    
class PlacementAnswerOptionInline(admin.TabularInline):
    model = PlacementAnswerOption
    extra = 4


@admin.register(PlacementTest)
class PlacementTestAdmin(admin.ModelAdmin):
    list_display = ("id", "course", "title", "is_active", "created_at")
    list_filter = ("course", "is_active")
    search_fields = ("title", "description")


@admin.register(PlacementQuestion)
class PlacementQuestionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "test",
        "question_type",
        "level_code",
        "question_text",
        "is_active",
        "order",
    )
    list_filter = ("test", "question_type", "level_code", "is_active")
    search_fields = ("question_text", "correct_answer")
    inlines = [PlacementAnswerOptionInline]


@admin.register(PlacementAnswerOption)
class PlacementAnswerOptionAdmin(admin.ModelAdmin):
    list_display = ("id", "question", "text", "is_correct", "order")
    list_filter = ("is_correct",)


@admin.register(PlacementResult)
class PlacementResultAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "child",
        "test",
        "score",
        "total",
        "accuracy",
        "assigned_level",
        "created_at",
    )
    list_filter = ("test", "assigned_level")
    
    
@admin.register(VocabularyItem)
class VocabularyItemAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "language",
        "word",
        "level_code",
        "is_active",
        "order",
    )
    list_filter = ("language", "level_code", "is_active")
    search_fields = (
        "word",
        "translation_uz",
        "translation_ru",
        "translation_en",
        "translation_kk",
        "usage_example",
    )
    ordering = ("language", "level_code", "order", "id")


@admin.register(GrammarRule)
class GrammarRuleAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "course",
        "title",
        "level_code",
        "is_active",
        "order",
    )
    list_filter = ("course", "level_code", "is_active")
    search_fields = (
        "title",
        "explanation_uz",
        "explanation_ru",
        "explanation_en",
        "explanation_kk",
    )
    ordering = ("course", "level_code", "order", "id")


@admin.register(LearningMethodRule)
class LearningMethodRuleAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "mistake_type",
        "level_code",
        "recommended_method",
        "is_active",
    )
    list_filter = ("level_code", "recommended_method", "is_active")
    search_fields = (
        "mistake_type",
        "message_uz",
        "message_ru",
        "message_en",
        "message_kk",
    )   