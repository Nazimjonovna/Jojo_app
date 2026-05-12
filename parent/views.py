from datetime import timedelta
from drf_yasg.utils import swagger_auto_schema
from django.contrib.auth import authenticate
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .models import (
    User,
    OTPCode,
    PairingCode,
    ParentChild,
    ChildLocation,
    ChildLastLocation,
    DeviceToken,
    SafeRoute,
    ChildRouteAssignment,
    RouteAlert,
    generate_numeric_code,
)
from .serializers import (
    SendOTPSerializer,
    VerifyOTPSerializer,
    ParentRegisterSerializer,
    ParentLoginSerializer,
    UserSerializer,
    UpdateLanguageSerializer,
    PairingCodeSerializer,
    ChildRegisterByCodeSerializer,
    ChildSerializer,
    ChildLocationSerializer,
    ChildLastLocationSerializer,
    DeviceTokenSerializer,
    SafeRouteSerializer,
    ChildRouteAssignmentSerializer,
    RouteAlertSerializer,
)
from .services import process_child_location


def get_tokens_for_user(user):
    refresh = RefreshToken.for_user(user)

    return {
        "refresh": str(refresh),
        "access": str(refresh.access_token),
    }


def send_sms_code(phone, code):
    """
    Bu yerga Eskiz, Play Mobile yoki boshqa SMS provider integratsiya qilasan.

    Hozircha test uchun print qilyapti.
    Productionda code response ichida qaytmasligi kerak.
    """
    print(f"SMS CODE for {phone}: {code}")
    return True


class SendOTPView(APIView):
    permission_classes = [AllowAny]

    @swagger_auto_schema(request_body=SendOTPSerializer, tags=['register'])
    def post(self, request):
        serializer = SendOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone = serializer.validated_data["phone"]
        last_otp = OTPCode.objects.filter(
            phone=phone
        ).order_by("-created_at").first()

        if last_otp:
            seconds = (timezone.now() - last_otp.created_at).total_seconds()

            if seconds < 60:
                time_left = int(60 - seconds)

                return Response(
                    {
                        "status": False,
                        "detail": f"SMS kodni qayta yuborish uchun {time_left} sekund kuting.",
                        "time_left": time_left
                    },
                    status=status.HTTP_429_TOO_MANY_REQUESTS
                )

        code = generate_numeric_code(6)

        OTPCode.objects.create(
            phone=phone,
            code=code,
            expires_at=timezone.now() + timedelta(minutes=5)
        )

        send_sms_code(phone, code)

        return Response(
            {
                "status": True,
                "detail": "SMS kod yuborildi.",
                "code": code,  # TEST UCHUN. Productionda olib tashlanadi.
                "lifetime": "5 minutes"
            },
            status=status.HTTP_200_OK
        )


class VerifyOTPView(APIView):
    permission_classes = [AllowAny]

    @swagger_auto_schema(request_body=VerifyOTPSerializer, tags = ['register'])
    def post(self, request):
        serializer = VerifyOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        phone = serializer.validated_data["phone"]
        code = serializer.validated_data["code"]

        otp = OTPCode.objects.filter(
            phone=phone,
            code=code,
            is_used=False
        ).order_by("-created_at").first()

        if not otp:
            return Response(
                {
                    "status": False,
                    "detail": "SMS kod noto‘g‘ri."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        if otp.is_expired():
            return Response(
                {
                    "status": False,
                    "detail": "SMS kod muddati tugagan."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        otp.is_used = True
        otp.save(update_fields=["is_used"])

        return Response(
            {
                "status": True,
                "detail": "SMS kod tasdiqlandi."
            },
            status=status.HTTP_200_OK
        )


class ParentRegisterView(APIView):
    permission_classes = [AllowAny]

    @swagger_auto_schema(request_body=ParentRegisterSerializer, tags=['register'])
    def post(self, request):
        serializer = ParentRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone = serializer.validated_data["phone"]
        verified_otp = OTPCode.objects.filter(
            phone=phone,
            is_used=True
        ).order_by("-created_at").first()
        if not verified_otp:
            return Response(
                {
                    "status": False,
                    "detail": "Avval SMS kodni tasdiqlang."
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        if User.objects.filter(phone=phone).exists():
            return Response(
                {
                    "status": False,
                    "detail": "Bu telefon raqam bilan user allaqachon ro‘yxatdan o‘tgan."
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        user = serializer.save()
        tokens = get_tokens_for_user(user)
        return Response(
            {
                "status": True,
                "detail": "Parent muvaffaqiyatli ro‘yxatdan o‘tdi.",
                "user": UserSerializer(user).data,
                "tokens": tokens,
            },
            status=status.HTTP_201_CREATED
        )


class ParentLoginView(APIView):
    permission_classes = [AllowAny]

    @swagger_auto_schema(request_body=ParentLoginSerializer, tags = ['register'])
    def post(self, request):
        serializer = ParentLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        phone = serializer.validated_data["phone"]
        password = serializer.validated_data["password"]

        user = authenticate(
            request=request,
            username=phone,
            password=password
        )

        if not user:
            return Response(
                {
                    "status": False,
                    "detail": "Telefon raqam yoki parol noto‘g‘ri."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        if user.role != User.ROLE_PARENT:
            return Response(
                {
                    "status": False,
                    "detail": "Bu akkaunt parent emas."
                },
                status=status.HTTP_403_FORBIDDEN
            )

        tokens = get_tokens_for_user(user)

        return Response(
            {
                "status": True,
                "detail": "Login muvaffaqiyatli.",
                "user": UserSerializer(user).data,
                "tokens": tokens,
            },
            status=status.HTTP_200_OK
        )


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(tags = ['info'])
    def get(self, request):
        return Response(
            {
                "status": True,
                "user": UserSerializer(request.user).data
            },
            status=status.HTTP_200_OK
        )


class UpdateLanguageView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(request_body=UpdateLanguageSerializer, tags = ['settings'])
    def patch(self, request):
        serializer = UpdateLanguageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        request.user.language = serializer.validated_data["language"]
        request.user.save(update_fields=["language"])

        return Response(
            {
                "status": True,
                "detail": "Til muvaffaqiyatli o‘zgartirildi.",
                "user": UserSerializer(request.user).data
            },
            status=status.HTTP_200_OK
        )


class CreatePairingCodeView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(tags = ['info'])
    def post(self, request):
        if request.user.role != User.ROLE_PARENT:
            return Response(
                {
                    "status": False,
                    "detail": "Faqat parent pairing code yaratishi mumkin."
                },
                status=status.HTTP_403_FORBIDDEN
            )

        code = generate_numeric_code(6)

        while PairingCode.objects.filter(code=code, is_used=False).exists():
            code = generate_numeric_code(6)

        pairing = PairingCode.objects.create(
            parent=request.user,
            code=code,
            expires_at=timezone.now() + timedelta(minutes=10)
        )

        return Response(
            {
                "status": True,
                "detail": "Pairing code yaratildi.",
                "pairing": PairingCodeSerializer(pairing).data
            },
            status=status.HTTP_201_CREATED
        )


class ChildRegisterByCodeView(APIView):
    permission_classes = [AllowAny]

    @swagger_auto_schema(request_body=ChildRegisterByCodeSerializer, tags = ['register'])
    def post(self, request):
        serializer = ChildRegisterByCodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        code = serializer.validated_data["pairing_code"]
        child_name = serializer.validated_data["child_name"]
        language = serializer.validated_data["language"]

        pairing = PairingCode.objects.filter(
            code=code,
            is_used=False
        ).first()

        if not pairing:
            return Response(
                {
                    "status": False,
                    "detail": "Pairing code noto‘g‘ri yoki ishlatilgan."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        if pairing.is_expired():
            return Response(
                {
                    "status": False,
                    "detail": "Pairing code muddati tugagan."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        child_username = f"child_{generate_numeric_code(10)}"

        child = User.objects.create_user(
            username=child_username,
            password=generate_numeric_code(12),
            first_name=child_name,
            role=User.ROLE_CHILD,
            language=language
        )

        ParentChild.objects.create(
            parent=pairing.parent,
            child=child
        )

        pairing.is_used = True
        pairing.save(update_fields=["is_used"])

        tokens = get_tokens_for_user(child)

        return Response(
            {
                "status": True,
                "detail": "Child muvaffaqiyatli ulandi.",
                "child": ChildSerializer(child).data,
                "tokens": tokens,
            },
            status=status.HTTP_201_CREATED
        )


class MyChildrenView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(tags = ['info'])
    def get(self, request):
        if request.user.role != User.ROLE_PARENT:
            return Response(
                {
                    "status": False,
                    "detail": "Faqat parent bolalar ro‘yxatini ko‘ra oladi."
                },
                status=status.HTTP_403_FORBIDDEN
            )

        links = ParentChild.objects.filter(
            parent=request.user
        ).select_related("child")

        children = [link.child for link in links]

        return Response(
            {
                "status": True,
                "children": ChildSerializer(children, many=True).data
            },
            status=status.HTTP_200_OK
        )


class ParentRouteListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(tags = ['location'])
    def get(self, request):
        if request.user.role != User.ROLE_PARENT:
            return Response(
                {
                    "status": False,
                    "detail": "Faqat parent route ro‘yxatini ko‘ra oladi."
                },
                status=status.HTTP_403_FORBIDDEN
            )

        routes = SafeRoute.objects.filter(
            parent=request.user
        ).prefetch_related("points").order_by("-created_at")

        return Response(
            {
                "status": True,
                "routes": SafeRouteSerializer(routes, many=True).data,
            },
            status=status.HTTP_200_OK
        )

    @swagger_auto_schema(request_body=SafeRouteSerializer, tags = ['location'])
    def post(self, request):
        if request.user.role != User.ROLE_PARENT:
            return Response(
                {
                    "status": False,
                    "detail": "Faqat parent route yaratishi mumkin."
                },
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = SafeRouteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        route = serializer.save(parent=request.user)

        return Response(
            {
                "status": True,
                "detail": "Marshrut yaratildi.",
                "route": SafeRouteSerializer(route).data,
            },
            status=status.HTTP_201_CREATED
        )


class ParentRouteDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(tags = ['location'])
    def get_object(self, request, route_id):
        try:
            return SafeRoute.objects.get(
                id=route_id,
                parent=request.user
            )
        except SafeRoute.DoesNotExist:
            return None

    @swagger_auto_schema(tags = ['location'])
    def get(self, request, route_id):
        route = self.get_object(request, route_id)

        if not route:
            return Response(
                {
                    "status": False,
                    "detail": "Route topilmadi."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        return Response(
            {
                "status": True,
                "route": SafeRouteSerializer(route).data,
            },
            status=status.HTTP_200_OK
        )

    @swagger_auto_schema(request_body=SafeRouteSerializer, tags = ['location'])
    def patch(self, request, route_id):
        route = self.get_object(request, route_id)

        if not route:
            return Response(
                {
                    "status": False,
                    "detail": "Route topilmadi."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = SafeRouteSerializer(
            route,
            data=request.data,
            partial=True
        )
        serializer.is_valid(raise_exception=True)
        route = serializer.save()

        return Response(
            {
                "status": True,
                "detail": "Route yangilandi.",
                "route": SafeRouteSerializer(route).data,
            },
            status=status.HTTP_200_OK
        )

    @swagger_auto_schema(tags = ['location']) 
    def delete(self, request, route_id):
        route = self.get_object(request, route_id)

        if not route:
            return Response(
                {
                    "status": False,
                    "detail": "Route topilmadi."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        route.delete()

        return Response(
            {
                "status": True,
                "detail": "Route o‘chirildi.",
            },
            status=status.HTTP_200_OK
        )


class AssignRouteToChildView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(request_body=ChildRouteAssignmentSerializer, tags = ['location'])
    def post(self, request):
        if request.user.role != User.ROLE_PARENT:
            return Response(
                {
                    "status": False,
                    "detail": "Faqat parent route biriktirishi mumkin."
                },
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = ChildRouteAssignmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        child = serializer.validated_data["child"]
        route = serializer.validated_data["route"]

        has_access = ParentChild.objects.filter(
            parent=request.user,
            child=child
        ).exists()

        if not has_access:
            return Response(
                {
                    "status": False,
                    "detail": "Bu child sizga tegishli emas."
                },
                status=status.HTTP_403_FORBIDDEN
            )

        if route.parent_id != request.user.id:
            return Response(
                {
                    "status": False,
                    "detail": "Bu route sizga tegishli emas."
                },
                status=status.HTTP_403_FORBIDDEN
            )

        assignment = serializer.save(parent=request.user)

        return Response(
            {
                "status": True,
                "detail": "Route childga biriktirildi.",
                "assignment": ChildRouteAssignmentSerializer(assignment).data,
            },
            status=status.HTTP_201_CREATED
        )


class ParentChildAssignmentsView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(tags = ['location'])  
    def get(self, request, child_id):
        if request.user.role != User.ROLE_PARENT:
            return Response(
                {
                    "status": False,
                    "detail": "Faqat parent ko‘ra oladi."
                },
                status=status.HTTP_403_FORBIDDEN
            )

        has_access = ParentChild.objects.filter(
            parent=request.user,
            child_id=child_id
        ).exists()

        if not has_access:
            return Response(
                {
                    "status": False,
                    "detail": "Bu child sizga tegishli emas."
                },
                status=status.HTTP_403_FORBIDDEN
            )

        assignments = ChildRouteAssignment.objects.filter(
            parent=request.user,
            child_id=child_id
        ).select_related("route").order_by("-created_at")

        return Response(
            {
                "status": True,
                "assignments": ChildRouteAssignmentSerializer(
                    assignments,
                    many=True
                ).data,
            },
            status=status.HTTP_200_OK
        )


class ChildActiveRoutesView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(tags = ['location'])
    def get(self, request):
        if request.user.role != User.ROLE_CHILD:
            return Response(
                {
                    "status": False,
                    "detail": "Faqat child o‘z routelarini ko‘ra oladi."
                },
                status=status.HTTP_403_FORBIDDEN
            )

        assignments = ChildRouteAssignment.objects.filter(
            child=request.user,
            status=ChildRouteAssignment.STATUS_ACTIVE,
            route__is_active=True,
        ).select_related("route").prefetch_related("route__points")

        return Response(
            {
                "status": True,
                "assignments": ChildRouteAssignmentSerializer(
                    assignments,
                    many=True
                ).data,
            },
            status=status.HTTP_200_OK
        )


class SendChildLocationView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(request_body=ChildLocationSerializer, tags = ['location'])
    def post(self, request):
        if request.user.role != User.ROLE_CHILD:
            return Response(
                {
                    "status": False,
                    "detail": "Faqat child location yuborishi mumkin."
                },
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = ChildLocationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        location, realtime_payload = process_child_location(
            child=request.user,
            latitude=serializer.validated_data["latitude"],
            longitude=serializer.validated_data["longitude"],
            accuracy=serializer.validated_data.get("accuracy"),
            battery_level=serializer.validated_data.get("battery_level"),
            speed=serializer.validated_data.get("speed"),
            heading=serializer.validated_data.get("heading"),
            source=ChildLocation.SOURCE_REST,
        )

        return Response(
            {
                "status": True,
                "detail": "Location saqlandi va real-time yuborildi.",
                "location": ChildLocationSerializer(location).data,
                "realtime_payload": realtime_payload,
            },
            status=status.HTTP_201_CREATED
        )


class ChildLastLocationView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(tags = ['location'])
    def get(self, request, child_id):
        if request.user.role != User.ROLE_PARENT:
            return Response(
                {
                    "status": False,
                    "detail": "Faqat parent location ko‘ra oladi."
                },
                status=status.HTTP_403_FORBIDDEN
            )

        has_access = ParentChild.objects.filter(
            parent=request.user,
            child_id=child_id
        ).exists()

        if not has_access:
            return Response(
                {
                    "status": False,
                    "detail": "Bu child sizga tegishli emas."
                },
                status=status.HTTP_403_FORBIDDEN
            )

        try:
            location = ChildLastLocation.objects.get(child_id=child_id)
        except ChildLastLocation.DoesNotExist:
            return Response(
                {
                    "status": False,
                    "detail": "Location hali yuborilmagan."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        return Response(
            {
                "status": True,
                "location": ChildLastLocationSerializer(location).data
            },
            status=status.HTTP_200_OK
        )


class ChildLocationHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(request_body=ChildLocationSerializer, tags = ['location'])
    def get(self, request, child_id):
        if request.user.role != User.ROLE_PARENT:
            return Response(
                {
                    "status": False,
                    "detail": "Faqat parent location history ko‘ra oladi."
                },
                status=status.HTTP_403_FORBIDDEN
            )

        has_access = ParentChild.objects.filter(
            parent=request.user,
            child_id=child_id
        ).exists()

        if not has_access:
            return Response(
                {
                    "status": False,
                    "detail": "Bu child sizga tegishli emas."
                },
                status=status.HTTP_403_FORBIDDEN
            )

        locations = ChildLocation.objects.filter(
            child_id=child_id
        ).order_by("-created_at")[:100]

        return Response(
            {
                "status": True,
                "locations": ChildLocationSerializer(locations, many=True).data
            },
            status=status.HTTP_200_OK
        )


class RouteAlertListView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(tags = ['location'])
    def get(self, request):
        if request.user.role != User.ROLE_PARENT:
            return Response(
                {
                    "status": False,
                    "detail": "Faqat parent alertlarni ko‘ra oladi."
                },
                status=status.HTTP_403_FORBIDDEN
            )

        alerts = RouteAlert.objects.filter(
            assignment__parent=request.user
        ).select_related(
            "child",
            "assignment",
            "assignment__route",
        ).order_by("-created_at")[:100]

        return Response(
            {
                "status": True,
                "alerts": RouteAlertSerializer(alerts, many=True).data,
            },
            status=status.HTTP_200_OK
        )


class DeviceTokenView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(request_body=DeviceTokenSerializer, tags = ['token'])
    def post(self, request):
        serializer = DeviceTokenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        token = serializer.validated_data["token"]
        device_type = serializer.validated_data["device_type"]

        device, created = DeviceToken.objects.update_or_create(
            token=token,
            defaults={
                "user": request.user,
                "device_type": device_type,
                "is_active": True,
            }
        )

        return Response(
            {
                "status": True,
                "detail": "FCM token saqlandi.",
                "device": DeviceTokenSerializer(device).data,
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK
        )