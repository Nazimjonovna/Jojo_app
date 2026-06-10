from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework import status
from .services import achievement_service, companion_service, daily_task_service, analytics_service
from .models import (
    Language,
    LearningCourse,
    Lesson,
    AICompanion,
    Exercise,
    AnswerOption,
    ChildLearningProfile,
    LessonProgress,
    MistakeLog,
    Level,
    PlacementTest,
    PlacementQuestion,
    PlacementAnswerOption,
    PlacementResult,
    VocabularyItem, 
    GrammarRule,
    WordProgress,
    Achievement, 
    AICompanion, 
    ChildAchievement,
)

from .serializers import (
    LanguageSerializer,
    LearningCourseSerializer,
    CourseMapSerializer,
    LessonDetailSerializer,
    SubmitAnswerSerializer,
    ChildLearningProfileSerializer,
    MistakeLogSerializer,
    SelectCourseSerializer,
    PlacementTestSerializer,
    PlacementSubmitSerializer,
    PlacementResultSerializer,
    VocabularyItemSerializer, 
    GrammarRuleSerializer,
    LessonShortSerializer,
    RuleTutorHintSerializer,
    WordProgressSerializer,
    AchievementSerializer,
    AICompanionSerializer,
    ChildDailyTaskSerializer,
    ClaimRewardResponseSerializer,
    CompanionStateSerializer,
    SelectCompanionSerializer,
)
from .services.progress_service import (
    add_xp,
    complete_lesson,
    log_mistake,
    check_text_answer,
)
from .services.adaptive_service import get_recommended_learning_method
from .services.memory_service import (
    get_words_for_review,
    update_word_progress_from_exercise,
)
from .services.rule_tutor_service import build_rule_based_hint
from .services.answer_service import is_text_answer_correct
from .services import achievement_service, companion_service, daily_task_service
from .services.recommendation_service import (
    get_next_lesson_for_child,
    get_review_lesson_reason,
)


class LanguageListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        languages = Language.objects.filter(
            is_active=True
        ).order_by("order", "id")

        serializer = LanguageSerializer(
            languages,
            many=True,
            context={"request": request}
        )

        return Response(serializer.data, status=200)


class CourseListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        courses = LearningCourse.objects.filter(
            is_active=True
        ).select_related(
            "native_language",
            "learning_language"
        ).order_by("order", "id")

        serializer = LearningCourseSerializer(
            courses,
            many=True,
            context={"request": request}
        )

        return Response(serializer.data, status=200)


class CourseMapView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, course_id):
        course = get_object_or_404(
            LearningCourse.objects.filter(is_active=True),
            id=course_id
        )

        child = request.user

        serializer = CourseMapSerializer(
            course,
            context={
                "request": request,
                "child": child,
            }
        )

        return Response(serializer.data, status=200)


class LessonDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, lesson_id):
        lesson = get_object_or_404(
            Lesson.objects.filter(is_active=True),
            id=lesson_id
        )

        serializer = LessonDetailSerializer(
            lesson,
            context={"request": request}
        )

        return Response(serializer.data, status=200)


class SubmitExerciseAnswerView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, exercise_id):
        child = request.user

        exercise = get_object_or_404(
            Exercise.objects.filter(is_active=True),
            id=exercise_id
        )

        serializer = SubmitAnswerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        answer = serializer.validated_data.get("answer")
        selected_option_id = serializer.validated_data.get("selected_option_id")

        is_correct = False
        given_answer = ""

        if selected_option_id:
            option = AnswerOption.objects.filter(
                id=selected_option_id,
                exercise=exercise
            ).first()

            if not option:
                return Response(
                    {"detail": "Variant topilmadi"},
                    status=404
                )

            is_correct = option.is_correct
            given_answer = option.text

        else:
            given_answer = answer.strip()

            is_correct = is_text_answer_correct(
                given_answer=given_answer,
                correct_answer=exercise.correct_answer,
                accepted_answers=exercise.accepted_answers,
            )

        earned_xp = 0

        if is_correct:
            earned_xp = max(1, exercise.difficulty)
            add_xp(child, earned_xp)
        else:
            log_mistake(child, exercise, given_answer)

        word_progress = update_word_progress_from_exercise(
            child=child,
            exercise=exercise,
            is_correct=is_correct,
        )

        return Response({
            "is_correct": is_correct,
            "given_answer": given_answer,
            "correct_answer": exercise.correct_answer or "",
            "explanation": exercise.explanation or "",
            "earned_xp": earned_xp,
            "word_progress": {
                "state": word_progress.state,
                "memory_strength": word_progress.memory_strength,
                "next_review_at": word_progress.next_review_at,
            } if word_progress else None,
            "next_action": "continue" if is_correct else "try_again",
        }, status=200)


class CompleteLessonView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, lesson_id):
        child = request.user

        lesson = get_object_or_404(
            Lesson.objects.filter(is_active=True),
            id=lesson_id
        )

        score = int(request.data.get("score", 0))
        total = int(request.data.get("total", 0))

        try:
            result = complete_lesson(
                child=child,
                lesson=lesson,
                score=score,
                total=total,
            )
        except ValueError as error:
            return Response(
                {"detail": str(error)},
                status=400
            )

        return Response(result, status=200)


class MyLearningProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile, _ = ChildLearningProfile.objects.get_or_create(
            child=request.user
        )

        serializer = ChildLearningProfileSerializer(
            profile,
            context={"request": request}
        )

        return Response(serializer.data, status=200)


class MyMistakesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        mistakes = MistakeLog.objects.filter(
            child=request.user
        ).select_related(
            "exercise",
            "exercise__lesson"
        ).order_by("-created_at")[:50]

        serializer = MistakeLogSerializer(
            mistakes,
            many=True,
            context={"request": request}
        )

        return Response(serializer.data, status=200)
    
    
class CourseSelectView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        child = request.user

        serializer = SelectCourseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        course_id = serializer.validated_data["course_id"]

        course = get_object_or_404(
            LearningCourse.objects.filter(is_active=True),
            id=course_id
        )

        first_level = Level.objects.filter(
            course=course
        ).order_by("min_xp", "order", "id").first()

        profile, _ = ChildLearningProfile.objects.get_or_create(
            child=child
        )

        profile.current_course = course
        profile.current_level = first_level

        if first_level:
            profile.ai_friend_level = first_level.code

        profile.save(
            update_fields=[
                "current_course",
                "current_level",
                "ai_friend_level",
                "updated_at",
            ]
        )

        return Response({
            "message": "Course tanlandi",
            "course_id": course.id,
            "current_level": first_level.code if first_level else None,
        }, status=200)
        
        
class PlacementTestView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, course_id):
        test = PlacementTest.objects.filter(
            course_id=course_id,
            is_active=True
        ).first()

        if not test:
            return Response(
                {"detail": "Placement test topilmadi"},
                status=404
            )

        serializer = PlacementTestSerializer(
            test,
            context={"request": request}
        )

        return Response(serializer.data, status=200)


class PlacementSubmitView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        child = request.user

        serializer = PlacementSubmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        test_id = serializer.validated_data["test_id"]
        answers = serializer.validated_data["answers"]

        test = get_object_or_404(
            PlacementTest.objects.filter(is_active=True),
            id=test_id
        )

        score = 0
        total = len(answers)

        level_scores = {
            "A0": 0,
            "A1": 0,
            "A2": 0,
            "B1": 0,
        }

        for item in answers:
            question_id = item["question_id"]
            answer = item.get("answer")
            selected_option_id = item.get("selected_option_id")

            question = PlacementQuestion.objects.filter(
                id=question_id,
                test=test,
                is_active=True
            ).first()

            if not question:
                continue

            is_correct = False

            if selected_option_id:
                option = PlacementAnswerOption.objects.filter(
                    id=selected_option_id,
                    question=question
                ).first()

                if option and option.is_correct:
                    is_correct = True

            elif answer:
                is_correct = (
                    answer.strip().lower()
                    == question.correct_answer.strip().lower()
                )

            if is_correct:
                score += 1
                level_scores[question.level_code] += 1

        accuracy = round((score / total) * 100, 2) if total > 0 else 0

        assigned_level_code = "A0"

        if accuracy >= 85:
            assigned_level_code = "A2"
        elif accuracy >= 60:
            assigned_level_code = "A1"
        else:
            assigned_level_code = "A0"

        assigned_level = Level.objects.filter(
            course=test.course,
            code=assigned_level_code
        ).first()

        profile, _ = ChildLearningProfile.objects.get_or_create(
            child=child
        )

        profile.current_course = test.course
        profile.current_level = assigned_level

        if assigned_level:
            profile.ai_friend_level = assigned_level.code

        profile.save(
            update_fields=[
                "current_course",
                "current_level",
                "ai_friend_level",
                "updated_at",
            ]
        )

        result = PlacementResult.objects.create(
            child=child,
            test=test,
            score=score,
            total=total,
            accuracy=accuracy,
            assigned_level=assigned_level,
        )

        result_serializer = PlacementResultSerializer(
            result,
            context={"request": request}
        )

        return Response({
            "message": "Placement test yakunlandi",
            "level_scores": level_scores,
            "result": result_serializer.data,
        }, status=200)
        
        
class VocabularyListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        language_id = request.query_params.get("language")
        level_code = request.query_params.get("level")

        items = VocabularyItem.objects.filter(is_active=True)

        if language_id:
            items = items.filter(language_id=language_id)

        if level_code:
            items = items.filter(level_code=level_code)

        items = items.order_by("level_code", "order", "id")

        serializer = VocabularyItemSerializer(
            items,
            many=True,
            context={"request": request}
        )

        return Response(serializer.data, status=200)


class GrammarRuleListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        course_id = request.query_params.get("course")
        level_code = request.query_params.get("level")

        rules = GrammarRule.objects.filter(is_active=True)

        if course_id:
            rules = rules.filter(course_id=course_id)

        if level_code:
            rules = rules.filter(level_code=level_code)

        rules = rules.order_by("level_code", "order", "id")

        serializer = GrammarRuleSerializer(
            rules,
            many=True,
            context={"request": request}
        )

        return Response(serializer.data, status=200)


class RecommendedLearningMethodView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        result = get_recommended_learning_method(request.user)
        return Response(result, status=200)
    
    
class NextLessonView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        child = request.user

        lesson = get_next_lesson_for_child(child)

        if not lesson:
            return Response({
                "detail": "Keyingi lesson topilmadi",
                "next_lesson": None,
            }, status=200)

        reason = get_review_lesson_reason(child)

        serializer = LessonShortSerializer(
            lesson,
            context={
                "request": request,
                "child": child,
            }
        )

        return Response({
            "reason": reason,
            "next_lesson": serializer.data,
        }, status=200)
        
        
class RuleTutorHintView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = RuleTutorHintSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        exercise_id = serializer.validated_data["exercise_id"]
        given_answer = serializer.validated_data.get("given_answer")

        exercise = Exercise.objects.filter(
            id=exercise_id,
            is_active=True
        ).first()

        if not exercise:
            return Response(
                {"detail": "Exercise topilmadi"},
                status=404
            )

        result = build_rule_based_hint(
            child=request.user,
            exercise=exercise,
            given_answer=given_answer,
        )

        return Response(result, status=200)
    
    
class MyWordReviewView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        words = get_words_for_review(request.user)

        serializer = WordProgressSerializer(
            words,
            many=True,
            context={"request": request}
        )

        return Response(serializer.data, status=200)
    
    
class ChildProfileMixin:
    """Barcha gamification view'lar uchun umumiy: child profilni olish.
 
    MUHIM: get_profile() ni loyihangizdagi child auth mexanizmiga moslang.
    Masalan, child alohida token bilan login qilsa:
        return request.user.child_learning_profile
    Yoki parent token + child_id header bo'lsa:
        child_id = request.headers["X-Child-Id"]
        return ChildLearningProfile.objects.get(
            id=child_id, child__parent__user=request.user
        )
    """
    permission_classes = [IsAuthenticated]
 
    def get_profile(self, request):
        profile = getattr(request.user, "child_learning_profile", None)
        if profile is None:
            raise NotFound("Child learning profile topilmadi")
        return profile
 
    def get_serializer_context(self, request, profile) -> dict:
        return {
            "request": request,
            "lang": getattr(profile, "native_language_code", "uz"),
        }
 
 
class MyAchievementsView(ChildProfileMixin, APIView):
    """GET — barcha achievementlar, qaysilari olingani va progressi bilan."""
 
    def get(self, request):
        profile = self.get_profile(request)
 
        earned_map = {
            ca.achievement_id: ca
            for ca in ChildAchievement.objects.filter(profile=profile)
        }
        context = self.get_serializer_context(request, profile)
        context["earned_map"] = earned_map
        context["value_fn"] = lambda ach: achievement_service._current_value(
            profile, ach.condition_type
        )
 
        queryset = Achievement.objects.filter(is_active=True)
        serializer = AchievementSerializer(queryset, many=True, context=context)
 
        unseen = sum(1 for ca in earned_map.values() if not ca.is_seen)
        return Response({"achievements": serializer.data, "unseen_count": unseen})
 
 
class MarkAchievementsSeenView(ChildProfileMixin, APIView):
    """POST — 'yangi badge' popup ko'rsatilgandan keyin chaqiriladi."""
 
    def post(self, request):
        achievement_service.mark_seen(self.get_profile(request))
        return Response({"ok": True})
 
 
class MyDailyTasksView(ChildProfileMixin, APIView):
    """GET — bugungi tasklar. Birinchi chaqiruvda avtomatik yaratiladi."""
 
    def get(self, request):
        profile = self.get_profile(request)
        tasks = daily_task_service.get_or_create_today(profile)
        serializer = ChildDailyTaskSerializer(
            tasks, many=True,
            context=self.get_serializer_context(request, profile),
        )
        return Response({
            "date": str(tasks[0].date) if tasks else None,
            "tasks": serializer.data,
            "all_completed": bool(tasks) and all(t.is_completed for t in tasks),
        })
 
 
class ClaimDailyTaskView(ChildProfileMixin, APIView):
    """POST — tugatilgan task mukofotini olish."""
 
    def post(self, request, task_id: int):
        profile = self.get_profile(request)
        try:
            result = daily_task_service.claim_reward(profile, task_id)
        except daily_task_service.ChildDailyTask.DoesNotExist:
            raise NotFound("Task topilmadi")
        except ValueError as e:
            raise ValidationError({"detail": str(e)})
 
        serializer = ClaimRewardResponseSerializer(result)
        return Response(serializer.data)
 
 
class CompanionListView(ChildProfileMixin, APIView):
    """GET — tanlash mumkin bo'lgan personajlar ro'yxati."""
 
    def get(self, request):
        profile = self.get_profile(request)
        serializer = AICompanionSerializer(
            AICompanion.objects.filter(is_active=True), many=True,
            context=self.get_serializer_context(request, profile),
        )
        return Response({"companions": serializer.data})
 
 
class MyCompanionView(ChildProfileMixin, APIView):
    """GET — bolaning joriy companion holati + salomlashish xabari.
    Ilova ochilganda chaqiriladi (home screen)."""
 
    def get(self, request):
        profile = self.get_profile(request)
        state = companion_service.get_or_create_state(profile)
        greeting = companion_service.greeting(profile)
 
        serializer = CompanionStateSerializer(
            state, context=self.get_serializer_context(request, profile)
        )
        return Response({"companion": serializer.data, "greeting": greeting})
 
 
class SelectCompanionView(ChildProfileMixin, APIView):
    """POST {"companion_code": "jojo"} — personaj tanlash/almashtirish."""
 
    def post(self, request):
        profile = self.get_profile(request)
        serializer = SelectCompanionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
 
        companion = get_object_or_404(
            AICompanion,
            code=serializer.validated_data["companion_code"],
            is_active=True,
        )
        state = companion_service.select_companion(profile, companion.code)
        out = CompanionStateSerializer(
            state, context=self.get_serializer_context(request, profile)
        )
        return Response({"ok": True, "companion": out.data}, status=status.HTTP_200_OK)
    
    
class ParentChildMixin:
    permission_classes = [IsAuthenticated]
 
    def get_child_profile(self, request, profile_id: int):
        try:
            return ChildLearningProfile.objects.get(
                id=profile_id,
                child__parent__user=request.user,  # MOSLANG: lookup zanjiri
            )
        except ChildLearningProfile.DoesNotExist:
            raise NotFound("Bola profili topilmadi")
 
    def get_int_param(self, request, name: str, default: int,
                      allowed: tuple[int, ...]) -> int:
        try:
            value = int(request.query_params.get(name, default))
        except (TypeError, ValueError):
            raise ValidationError({name: "butun son bo'lishi kerak"})
        if value not in allowed:
            raise ValidationError({name: f"ruxsat etilgan qiymatlar: {allowed}"})
        return value
 
 
class ParentChildrenListView(ParentChildMixin, APIView):
     
    def get(self, request):
 
        profiles = ChildLearningProfile.objects.filter(
            child__parent__user=request.user  # MOSLANG
        ).select_related("child")
 
        children = []
        for profile in profiles:
            overview = analytics_service.get_overview(profile)
            children.append({
                "profile_id": profile.id,
                "child_name": getattr(profile, "child_name", None)
                              or getattr(profile.child, "name", ""),  # MOSLANG
                "course": str(getattr(profile, "course", "")),         # MOSLANG
                **overview,
            })
        return Response({"children": children})
 
 
class ChildOverviewView(ParentChildMixin, APIView):
    def get(self, request, profile_id: int):
        profile = self.get_child_profile(request, profile_id)
        return Response(analytics_service.get_overview(profile))
 
 
class ChildActivityView(ParentChildMixin, APIView):
    def get(self, request, profile_id: int):
        profile = self.get_child_profile(request, profile_id)
        days = self.get_int_param(request, "days", default=7, allowed=(7, 30, 90))
        return Response({
            "days": days,
            "chart": analytics_service.get_activity_chart(profile, days=days),
        })
 
 
class ChildMistakesView(ParentChildMixin, APIView):
    def get(self, request, profile_id: int):
        profile = self.get_child_profile(request, profile_id)
        days = self.get_int_param(request, "days", default=30, allowed=(7, 30, 90))
        return Response(analytics_service.get_mistake_report(profile, days=days))
 
 
class ChildWordsView(ParentChildMixin, APIView):
    def get(self, request, profile_id: int):
        profile = self.get_child_profile(request, profile_id)
        return Response(analytics_service.get_word_report(profile))
 
 
class ChildWeeklySummaryView(ParentChildMixin, APIView):
    def get(self, request, profile_id: int):
        profile = self.get_child_profile(request, profile_id)
        return Response(analytics_service.get_weekly_summary(profile))