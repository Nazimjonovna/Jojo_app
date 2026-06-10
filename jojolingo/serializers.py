from rest_framework import serializers

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
    PlacementTest,
    PlacementQuestion,
    PlacementAnswerOption,
    PlacementResult,
    VocabularyItem,
    GrammarRule,
    LearningMethodRule,
    WordProgress,
    Achievement,
    AICompanion,
    ChildAchievement,
    ChildCompanionState,
    ChildDailyTask,
)


class LanguageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Language
        fields = [
            "id",
            "code",
            "name",
            "native_name",
            "flag_icon",
            "is_active",
            "order",
        ]


class LearningCourseSerializer(serializers.ModelSerializer):
    native_language = LanguageSerializer(read_only=True)
    learning_language = LanguageSerializer(read_only=True)

    class Meta:
        model = LearningCourse
        fields = [
            "id",
            "native_language",
            "learning_language",
            "title",
            "description",
            "is_active",
            "order",
        ]


class LevelSerializer(serializers.ModelSerializer):
    class Meta:
        model = Level
        fields = [
            "id",
            "course",
            "code",
            "title",
            "description",
            "min_xp",
            "order",
        ]


class UnitShortSerializer(serializers.ModelSerializer):
    class Meta:
        model = Unit
        fields = [
            "id",
            "title",
            "description",
            "icon",
            "order",
            "is_active",
        ]


class LessonShortSerializer(serializers.ModelSerializer):
    is_locked = serializers.SerializerMethodField()
    is_completed = serializers.SerializerMethodField()

    class Meta:
        model = Lesson
        fields = [
            "id",
            "title",
            "lesson_type",
            "reward_xp",
            "required_accuracy",
            "order",
            "is_active",
            "is_locked",
            "is_completed",
        ]

    def get_is_completed(self, obj):
        child = self.context.get("child")

        if not child:
            return False

        return LessonProgress.objects.filter(
            child=child,
            lesson=obj,
            is_completed=True,
        ).exists()

    def get_is_locked(self, obj):
        child = self.context.get("child")

        if not child:
            return False

        previous_lessons = Lesson.objects.filter(
            unit=obj.unit,
            order__lt=obj.order,
            is_active=True,
        )

        if not previous_lessons.exists():
            return False

        completed_count = LessonProgress.objects.filter(
            child=child,
            lesson__in=previous_lessons,
            is_completed=True,
        ).count()

        return completed_count < previous_lessons.count()


class UnitMapSerializer(serializers.ModelSerializer):
    lessons = serializers.SerializerMethodField()

    class Meta:
        model = Unit
        fields = [
            "id",
            "title",
            "description",
            "icon",
            "order",
            "lessons",
        ]

    def get_lessons(self, obj):
        lessons = obj.lessons.filter(is_active=True).order_by("order", "id")

        return LessonShortSerializer(
            lessons,
            many=True,
            context=self.context,
        ).data


class CourseMapSerializer(serializers.ModelSerializer):
    levels = serializers.SerializerMethodField()
    units = serializers.SerializerMethodField()

    class Meta:
        model = LearningCourse
        fields = [
            "id",
            "title",
            "description",
            "native_language",
            "learning_language",
            "levels",
            "units",
        ]

    def get_levels(self, obj):
        levels = obj.levels.all().order_by("order", "id")
        return LevelSerializer(levels, many=True).data

    def get_units(self, obj):
        units = obj.units.filter(is_active=True).order_by("level__order", "order", "id")

        return UnitMapSerializer(
            units,
            many=True,
            context=self.context,
        ).data


class AnswerOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnswerOption
        fields = [
            "id",
            "text",
            "order",
        ]


class ExerciseSerializer(serializers.ModelSerializer):
    options = AnswerOptionSerializer(many=True, read_only=True)

    class Meta:
        model = Exercise
        fields = [
            "id",
            "exercise_type",
            "instruction",
            "question_text",
            "image",
            "audio",
            "difficulty",
            "order",
            "options",
        ]


class LessonDetailSerializer(serializers.ModelSerializer):
    exercises = serializers.SerializerMethodField()

    class Meta:
        model = Lesson
        fields = [
            "id",
            "title",
            "lesson_type",
            "reward_xp",
            "required_accuracy",
            "order",
            "exercises",
        ]

    def get_exercises(self, obj):
        exercises = obj.exercises.filter(is_active=True).order_by("order", "id")

        return ExerciseSerializer(
            exercises,
            many=True,
            context=self.context,
        ).data


class SubmitAnswerSerializer(serializers.Serializer):
    answer = serializers.CharField(required=False, allow_blank=True)
    selected_option_id = serializers.IntegerField(required=False)

    def validate(self, attrs):
        answer = attrs.get("answer")
        selected_option_id = attrs.get("selected_option_id")

        if not answer and not selected_option_id:
            raise serializers.ValidationError(
                "answer yoki selected_option_id yuborilishi kerak"
            )

        return attrs


class SubmitAnswerResultSerializer(serializers.Serializer):
    is_correct = serializers.BooleanField()
    correct_answer = serializers.CharField()
    explanation = serializers.CharField(allow_blank=True)
    earned_xp = serializers.IntegerField()
    next_action = serializers.CharField()


class ChildLearningProfileSerializer(serializers.ModelSerializer):
    current_course = LearningCourseSerializer(read_only=True)
    current_level = LevelSerializer(read_only=True)

    class Meta:
        model = ChildLearningProfile
        fields = [
            "id",
            "child",
            "current_course",
            "current_level",
            "total_xp",
            "streak_days",
            "last_learning_date",
            "ai_friend_name",
            "ai_friend_level",
            "created_at",
            "updated_at",
        ]


class MistakeLogSerializer(serializers.ModelSerializer):
    exercise = ExerciseSerializer(read_only=True)

    class Meta:
        model = MistakeLog
        fields = [
            "id",
            "exercise",
            "given_answer",
            "correct_answer",
            "mistake_type",
            "explanation",
            "created_at",
        ]
        
        
class SelectCourseSerializer(serializers.Serializer):
    course_id = serializers.IntegerField()
    
    
class PlacementAnswerOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlacementAnswerOption
        fields = [
            "id",
            "text",
            "order",
        ]


class PlacementQuestionSerializer(serializers.ModelSerializer):
    options = PlacementAnswerOptionSerializer(many=True, read_only=True)

    class Meta:
        model = PlacementQuestion
        fields = [
            "id",
            "question_type",
            "question_text",
            "level_code",
            "order",
            "options",
        ]


class PlacementTestSerializer(serializers.ModelSerializer):
    questions = serializers.SerializerMethodField()

    class Meta:
        model = PlacementTest
        fields = [
            "id",
            "course",
            "title",
            "description",
            "questions",
        ]

    def get_questions(self, obj):
        questions = obj.questions.filter(is_active=True).order_by("order", "id")

        return PlacementQuestionSerializer(
            questions,
            many=True,
            context=self.context,
        ).data


class PlacementSubmitAnswerSerializer(serializers.Serializer):
    question_id = serializers.IntegerField()
    answer = serializers.CharField(required=False, allow_blank=True)
    selected_option_id = serializers.IntegerField(required=False)


class PlacementSubmitSerializer(serializers.Serializer):
    test_id = serializers.IntegerField()
    answers = PlacementSubmitAnswerSerializer(many=True)


class PlacementResultSerializer(serializers.ModelSerializer):
    assigned_level = LevelSerializer(read_only=True)

    class Meta:
        model = PlacementResult
        fields = [
            "id",
            "test",
            "score",
            "total",
            "accuracy",
            "assigned_level",
            "created_at",
        ]
        

class VocabularyItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = VocabularyItem
        fields = [
            "id",
            "language",
            "word",
            "translation_uz",
            "translation_ru",
            "translation_en",
            "translation_kk",
            "level_code",
            "image",
            "audio",
            "usage_example",
            "order",
            "is_active",
        ]


class GrammarRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = GrammarRule
        fields = [
            "id",
            "course",
            "title",
            "explanation_uz",
            "explanation_ru",
            "explanation_en",
            "explanation_kk",
            "level_code",
            "examples",
            "is_active",
            "order",
        ]


class LearningMethodRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = LearningMethodRule
        fields = [
            "id",
            "mistake_type",
            "level_code",
            "recommended_method",
            "message_uz",
            "message_ru",
            "message_en",
            "message_kk",
            "is_active",
        ]
        
        
class RuleTutorHintSerializer(serializers.Serializer):
    exercise_id = serializers.IntegerField()
    given_answer = serializers.CharField(required=False, allow_blank=True)
    
    
class WordProgressSerializer(serializers.ModelSerializer):
    vocabulary = VocabularyItemSerializer(read_only=True)

    class Meta:
        model = WordProgress
        fields = [
            "id",
            "vocabulary",
            "state",
            "correct_count",
            "wrong_count",
            "review_count",
            "memory_strength",
            "next_review_at",
            "last_reviewed_at",
        ]
        
        
class _MultilingualMixin:
    """title_uz / title_ru / ... maydonlaridan kontekstdagi lang bo'yicha tanlaydi."""
 
    def _lang(self) -> str:
        return self.context.get("lang", "uz")
 
    def _pick(self, obj, prefix: str) -> str:
        return getattr(obj, f"{prefix}_{self._lang()}", "") or getattr(obj, f"{prefix}_uz", "")
 
 
class AchievementSerializer(_MultilingualMixin, serializers.ModelSerializer):
    title = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()
    earned = serializers.SerializerMethodField()
    earned_at = serializers.SerializerMethodField()
    progress = serializers.SerializerMethodField()
 
    class Meta:
        model = Achievement
        fields = [
            "code", "title", "description", "icon", "xp_reward",
            "threshold", "progress", "earned", "earned_at",
        ]
 
    # context: {"lang": "uz", "earned_map": {achievement_id: ChildAchievement},
    #           "value_fn": callable(achievement) -> int}
    def get_title(self, obj):
        return self._pick(obj, "title")
 
    def get_description(self, obj):
        return self._pick(obj, "description")
 
    def _earned_obj(self, obj) -> ChildAchievement | None:
        return self.context.get("earned_map", {}).get(obj.id)
 
    def get_earned(self, obj) -> bool:
        return self._earned_obj(obj) is not None
 
    def get_earned_at(self, obj):
        ca = self._earned_obj(obj)
        return ca.earned_at if ca else None
 
    def get_progress(self, obj) -> int:
        value_fn = self.context.get("value_fn")
        if value_fn is None:
            return 0
        return min(value_fn(obj), obj.threshold)
 
 
class ChildDailyTaskSerializer(_MultilingualMixin, serializers.ModelSerializer):
    type = serializers.CharField(source="template.task_type", read_only=True)
    title = serializers.SerializerMethodField()
    completed = serializers.BooleanField(source="is_completed", read_only=True)
 
    class Meta:
        model = ChildDailyTask
        fields = [
            "id", "type", "title", "progress", "target",
            "completed", "xp_reward", "reward_claimed",
        ]
 
    def get_title(self, obj):
        return self._pick(obj.template, "title").format(n=obj.target)
 
 
class ClaimRewardResponseSerializer(serializers.Serializer):
    xp_added = serializers.IntegerField()
    total_xp = serializers.IntegerField()
 
 
class AICompanionSerializer(_MultilingualMixin, serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
 
    class Meta:
        model = AICompanion
        fields = ["code", "name", "avatar", "personality"]
 
    def get_name(self, obj):
        return self._pick(obj, "name")
 
 
class CompanionStateSerializer(_MultilingualMixin, serializers.ModelSerializer):
    code = serializers.CharField(source="companion.code", read_only=True)
    name = serializers.SerializerMethodField()
    avatar = serializers.CharField(source="companion.avatar", read_only=True)
 
    class Meta:
        model = ChildCompanionState
        fields = ["code", "name", "avatar", "mood", "friendship_level", "friendship_xp"]
 
    def get_name(self, obj):
        return self._pick(obj.companion, "name")
 
 
class SelectCompanionSerializer(serializers.Serializer):
    companion_code = serializers.SlugField(max_length=32)