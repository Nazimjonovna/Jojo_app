from datetime import timedelta

from django.contrib.auth import authenticate
from django.utils import timezone

from drf_yasg.utils import swagger_auto_schema

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
    CreateChildPairingSerializer,
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


def save_user_device(user, device_id, token, device_type="android"):
    if not device_id:
        return {
            "error": True,
            "detail": "device_id majburiy."
        }

    if not token:
        return {
            "error": True,
            "detail": "Firebase token majburiy."
        }

    if user.role == User.ROLE_CHILD:
        active_device = DeviceToken.objects.filter(
            user=user,
            is_active=True,
        ).exclude(
            device_id=device_id,
        ).first()

        if active_device:
            return {
                "error": True,
                "detail": "Bu child akkaunt boshqa qurilmada aktiv. Avval birinchi device_id dan logout qiling.",
                "active_device_id": active_device.device_id,
            }

    device, created = DeviceToken.objects.update_or_create(
        user=user,
        device_id=device_id,
        defaults={
            "token": token,
            "device_type": device_type,
            "is_active": True,
            "last_login_at": timezone.now(),
        },
    )

    return {
        "error": False,
        "device": device,
        "created": created,
    }


class SendOTPView(APIView):
    permission_classes = [AllowAny]

    @swagger_auto_schema(request_body=SendOTPSerializer, tags=["register"])
    def post(self, request):
        serializer = SendOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        phone = serializer.validated_data["phone"]

        last_otp = OTPCode.objects.filter(
            phone=phone
        ).order_by("-created_at").first()

        if last_otp and hasattr(last_otp, "is_blocked") and last_otp.is_blocked():
            time_left = last_otp.block_time_left_seconds()

            return Response(
                {
                    "status": False,
                    "detail": "Juda ko‘p noto‘g‘ri urinish. Keyinroq qayta urinib ko‘ring.",
                    "blocked": True,
                    "time_left_seconds": time_left,
                    "time_left_minutes": round(time_left / 60, 1),
                },
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )

        if last_otp:
            seconds = (timezone.now() - last_otp.created_at).total_seconds()

            if seconds < 60:
                time_left = int(60 - seconds)

                return Response(
                    {
                        "status": False,
                        "detail": f"SMS kodni qayta yuborish uchun {time_left} sekund kuting.",
                        "time_left": time_left,
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
                "code": code,
                "lifetime": "5 minutes",
            },
            status=status.HTTP_200_OK
        )


class VerifyOTPView(APIView):
    permission_classes = [AllowAny]

    @swagger_auto_schema(request_body=VerifyOTPSerializer, tags=["register"])
    def post(self, request):
        serializer = VerifyOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        phone = serializer.validated_data["phone"]
        code = serializer.validated_data["code"]

        otp = OTPCode.objects.filter(
            phone=phone,
            is_used=False,
        ).order_by("-created_at").first()

        if not otp:
            return Response(
                {
                    "status": False,
                    "detail": "Aktiv SMS kod topilmadi. Yangi kod oling."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if otp.is_blocked():
            time_left = otp.block_time_left_seconds()

            return Response(
                {
                    "status": False,
                    "detail": "Juda ko‘p noto‘g‘ri urinish. 30 minutdan keyin qayta urinib ko‘ring.",
                    "blocked": True,
                    "time_left_seconds": time_left,
                    "time_left_minutes": round(time_left / 60, 1),
                },
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        if otp.is_expired():
            return Response(
                {
                    "status": False,
                    "detail": "SMS kod muddati tugagan."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        now = timezone.now()

        # 1 soatdan keyin attempt oynasi reset bo‘ladi
        if otp.first_attempt_at and now - otp.first_attempt_at > timedelta(hours=1):
            otp.attempt_count = 0
            otp.first_attempt_at = None
            otp.blocked_until = None
            otp.save(
                update_fields=[
                    "attempt_count",
                    "first_attempt_at",
                    "blocked_until",
                ]
            )

        # Kod noto‘g‘ri bo‘lsa attempt sanaymiz
        if otp.code != code:
            if not otp.first_attempt_at:
                otp.first_attempt_at = now

            otp.attempt_count += 1
            attempts_left = max(3 - otp.attempt_count, 0)

            if otp.attempt_count >= 3:
                otp.blocked_until = now + timedelta(minutes=30)
                otp.save(
                    update_fields=[
                        "attempt_count",
                        "first_attempt_at",
                        "blocked_until",
                    ]
                )

                return Response(
                    {
                        "status": False,
                        "detail": "3 marta noto‘g‘ri kod kiritildi. 30 minutga bloklandi.",
                        "blocked": True,
                        "time_left_seconds": 30 * 60,
                        "time_left_minutes": 30,
                    },
                    status=status.HTTP_429_TOO_MANY_REQUESTS,
                )

            otp.save(update_fields=["attempt_count", "first_attempt_at"])

            return Response(
                {
                    "status": False,
                    "detail": "SMS kod noto‘g‘ri.",
                    "attempts_left": attempts_left,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Kod to‘g‘ri bo‘lsa faqat tasdiqlaymiz.
        # Token bu endpointda qaytmaydi.
        otp.is_used = True
        otp.save(update_fields=["is_used"])

        is_registered = User.objects.filter(
            phone=phone,
            role=User.ROLE_PARENT,
        ).exists()

        return Response(
            {
                "status": True,
                "is_registered": is_registered,
                "detail": "SMS kod tasdiqlandi. Token olish uchun parent/register endpointini chaqiring."
            },
            status=status.HTTP_200_OK,
        )

# class VerifyOTPView(APIView):
#     permission_classes = [AllowAny]

#     @swagger_auto_schema(request_body=VerifyOTPSerializer, tags=["register"])
#     def post(self, request):
#         serializer = VerifyOTPSerializer(data=request.data)
#         serializer.is_valid(raise_exception=True)

#         phone = serializer.validated_data["phone"]
#         code = serializer.validated_data["code"]

#         otp = OTPCode.objects.filter(
#             phone=phone,
#             is_used=False
#         ).order_by("-created_at").first()

#         if not otp:
#             return Response(
#                 {
#                     "status": False,
#                     "detail": "Aktiv SMS kod topilmadi. Yangi kod oling."
#                 },
#                 status=status.HTTP_400_BAD_REQUEST
#             )

#         if hasattr(otp, "is_blocked") and otp.is_blocked():
#             time_left = otp.block_time_left_seconds()

#             return Response(
#                 {
#                     "status": False,
#                     "detail": "Juda ko‘p noto‘g‘ri urinish. 30 minutdan keyin qayta urinib ko‘ring.",
#                     "blocked": True,
#                     "time_left_seconds": time_left,
#                     "time_left_minutes": round(time_left / 60, 1),
#                 },
#                 status=status.HTTP_429_TOO_MANY_REQUESTS
#             )

#         if otp.is_expired():
#             return Response(
#                 {
#                     "status": False,
#                     "detail": "SMS kod muddati tugagan."
#                 },
#                 status=status.HTTP_400_BAD_REQUEST
#             )

#         now = timezone.now()

#         if hasattr(otp, "first_attempt_at"):
#             if otp.first_attempt_at and now - otp.first_attempt_at > timedelta(hours=1):
#                 otp.attempt_count = 0
#                 otp.first_attempt_at = None
#                 otp.blocked_until = None
#                 otp.save(
#                     update_fields=[
#                         "attempt_count",
#                         "first_attempt_at",
#                         "blocked_until",
#                     ]
#                 )

#         if otp.code != code:
#             if hasattr(otp, "attempt_count"):
#                 if not otp.first_attempt_at:
#                     otp.first_attempt_at = now

#                 otp.attempt_count += 1
#                 attempts_left = max(5 - otp.attempt_count, 0)

#                 if otp.attempt_count >= 5:
#                     otp.blocked_until = now + timedelta(minutes=30)
#                     otp.save(
#                         update_fields=[
#                             "attempt_count",
#                             "first_attempt_at",
#                             "blocked_until",
#                         ]
#                     )

#                     return Response(
#                         {
#                             "status": False,
#                             "detail": "5 marta noto‘g‘ri kod kiritildi. 30 minutga bloklandi.",
#                             "blocked": True,
#                             "time_left_seconds": 30 * 60,
#                             "time_left_minutes": 30,
#                         },
#                         status=status.HTTP_429_TOO_MANY_REQUESTS
#                     )

#                 otp.save(update_fields=["attempt_count", "first_attempt_at"])

#                 return Response(
#                     {
#                         "status": False,
#                         "detail": "SMS kod noto‘g‘ri.",
#                         "attempts_left": attempts_left,
#                     },
#                     status=status.HTTP_400_BAD_REQUEST
#                 )

#             return Response(
#                 {
#                     "status": False,
#                     "detail": "SMS kod noto‘g‘ri."
#                 },
#                 status=status.HTTP_400_BAD_REQUEST
#             )

#         otp.is_used = True
#         otp.save(update_fields=["is_used"])

#         user = User.objects.filter(
#             phone=phone,
#             role=User.ROLE_PARENT
#         ).first()

#         if user:
#             tokens = get_tokens_for_user(user)

#             return Response(
#                 {
#                     "status": True,
#                     "is_registered": True,
#                     "detail": "SMS kod tasdiqlandi. User avval ro‘yxatdan o‘tgan.",
#                     "user": UserSerializer(user).data,
#                     "tokens": tokens,
#                 },
#                 status=status.HTTP_200_OK
#             )

#         return Response(
#             {
#                 "status": True,
#                 "is_registered": False,
#                 "detail": "SMS kod tasdiqlandi. Endi register qiling."
#             },
#             status=status.HTTP_200_OK
#         )


class ParentRegisterView(APIView):
    permission_classes = [AllowAny]

    @swagger_auto_schema(request_body=ParentRegisterSerializer, tags=["register"])
    def post(self, request):
        serializer = ParentRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        phone = serializer.validated_data["phone"]
        device_id = serializer.validated_data["device_id"]
        token = serializer.validated_data["token"]
        device_type = serializer.validated_data.get("device_type", "android")

        verified_otp = OTPCode.objects.filter(
            phone=phone,
            is_used=True,
        ).order_by("-created_at").first()

        if not verified_otp:
            return Response(
                {
                    "status": False,
                    "detail": "Avval SMS kodni tasdiqlang."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        existing_user = User.objects.filter(
            phone=phone,
            role=User.ROLE_PARENT,
        ).first()

        if existing_user:
            device_result = save_user_device(
                user=existing_user,
                device_id=device_id,
                token=token,
                device_type=device_type,
            )

            if device_result.get("error"):
                return Response(
                    {
                        "status": False,
                        "detail": device_result["detail"],
                        "active_device_id": device_result.get("active_device_id"),
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            tokens = get_tokens_for_user(existing_user)

            return Response(
                {
                    "status": True,
                    "is_registered": True,
                    "detail": "User avval ro‘yxatdan o‘tgan. Token qaytarildi.",
                    "user": UserSerializer(existing_user).data,
                    "device": DeviceTokenSerializer(device_result["device"]).data,
                    "tokens": tokens,
                },
                status=status.HTTP_200_OK,
            )

        user = serializer.save()

        device_result = save_user_device(
            user=user,
            device_id=device_id,
            token=token,
            device_type=device_type,
        )

        if device_result.get("error"):
            user.delete()

            return Response(
                {
                    "status": False,
                    "detail": device_result["detail"],
                    "active_device_id": device_result.get("active_device_id"),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        tokens = get_tokens_for_user(user)

        return Response(
            {
                "status": True,
                "is_registered": False,
                "detail": "Parent muvaffaqiyatli ro‘yxatdan o‘tdi.",
                "user": UserSerializer(user).data,
                "device": DeviceTokenSerializer(device_result["device"]).data,
                "tokens": tokens,
            },
            status=status.HTTP_201_CREATED,
        )


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(tags=["info"])
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

    @swagger_auto_schema(request_body=UpdateLanguageSerializer, tags=["settings"])
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

    @swagger_auto_schema(request_body=CreateChildPairingSerializer, tags=["child"])
    def post(self, request):
        if request.user.role != User.ROLE_PARENT:
            return Response(
                {
                    "status": False,
                    "detail": "Faqat parent bola qo‘sha oladi."
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = CreateChildPairingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        code = generate_numeric_code(6)

        while PairingCode.objects.filter(code=code, is_used=False).exists():
            code = generate_numeric_code(6)

        pairing = PairingCode.objects.create(
            parent=request.user,
            code=code,
            expires_at=timezone.now() + timedelta(minutes=10),
            child_name=serializer.validated_data["child_name"],
            child_gender=serializer.validated_data["child_gender"],
            child_age=serializer.validated_data["child_age"],
            child_avatar=serializer.validated_data.get("child_avatar"),
        )

        return Response(
            {
                "status": True,
                "detail": "Bola qo‘shish kodi yaratildi.",
                "pairing": PairingCodeSerializer(pairing).data,
                "qr_payload": {
                    "type": "jojo_child_pairing",
                    "code": pairing.code,
                },
            },
            status=status.HTTP_201_CREATED,
        )


class ChildRegisterByCodeView(APIView):
    permission_classes = [AllowAny]

    @swagger_auto_schema(request_body=ChildRegisterByCodeSerializer, tags=["child"])
    def post(self, request):
        serializer = ChildRegisterByCodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        code = serializer.validated_data["pairing_code"]
        device_id = serializer.validated_data["device_id"]
        token = serializer.validated_data["token"]
        device_type = serializer.validated_data.get("device_type", "android")

        pairing = PairingCode.objects.filter(
            code=code,
            is_used=False,
        ).first()

        if not pairing:
            return Response(
                {
                    "status": False,
                    "detail": "Pairing code noto‘g‘ri yoki ishlatilgan."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if pairing.is_expired():
            return Response(
                {
                    "status": False,
                    "detail": "Pairing code muddati tugagan."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        child_username = f"child_{generate_numeric_code(10)}"

        child = User.objects.create_user(
            phone=f"+998CHILD{generate_numeric_code(8)}",
            username=child_username,
            full_name=pairing.child_name,
            first_name=pairing.child_name,
            role=User.ROLE_CHILD,
            gender=pairing.child_gender,
            age=pairing.child_age,
            language=pairing.parent.language,
            avatar=pairing.child_avatar,
        )

        ParentChild.objects.create(
            parent=pairing.parent,
            child=child,
        )

        device_result = save_user_device(
            user=child,
            device_id=device_id,
            token=token,
            device_type=device_type,
        )

        if device_result.get("error"):
            child.delete()

            return Response(
                {
                    "status": False,
                    "detail": device_result["detail"],
                    "active_device_id": device_result.get("active_device_id"),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        pairing.is_used = True
        pairing.save(update_fields=["is_used"])

        tokens = get_tokens_for_user(child)

        return Response(
            {
                "status": True,
                "detail": "Child muvaffaqiyatli ulandi.",
                "child": ChildSerializer(child).data,
                "device": DeviceTokenSerializer(device_result["device"]).data,
                "tokens": tokens,
            },
            status=status.HTTP_201_CREATED,
        )


class MyChildrenView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(tags=["info"])
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

    @swagger_auto_schema(tags=["location"])
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

    @swagger_auto_schema(request_body=SafeRouteSerializer, tags=["location"])
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

    def get_object(self, request, route_id):
        try:
            return SafeRoute.objects.get(
                id=route_id,
                parent=request.user
            )
        except SafeRoute.DoesNotExist:
            return None

    @swagger_auto_schema(tags=["location"])
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

    @swagger_auto_schema(request_body=SafeRouteSerializer, tags=["location"])
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

    @swagger_auto_schema(tags=["location"])
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

    @swagger_auto_schema(request_body=ChildRouteAssignmentSerializer, tags=["location"])
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

    @swagger_auto_schema(tags=["location"])
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

    @swagger_auto_schema(tags=["location"])
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

    @swagger_auto_schema(request_body=ChildLocationSerializer, tags=["location"])
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

    @swagger_auto_schema(tags=["location"])
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

    @swagger_auto_schema(tags=["location"])
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

    @swagger_auto_schema(tags=["location"])
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

    @swagger_auto_schema(request_body=DeviceTokenSerializer, tags=["device"])
    def post(self, request):
        serializer = DeviceTokenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        device_id = serializer.validated_data["device_id"]
        token = serializer.validated_data["token"]
        device_type = serializer.validated_data["device_type"]

        device_result = save_user_device(
            user=request.user,
            device_id=device_id,
            token=token,
            device_type=device_type,
        )

        if device_result.get("error"):
            return Response(
                {
                    "status": False,
                    "detail": device_result["detail"],
                    "active_device_id": device_result.get("active_device_id"),
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response(
            {
                "status": True,
                "detail": "Device token saqlandi.",
                "device": DeviceTokenSerializer(device_result["device"]).data,
            },
            status=(
                status.HTTP_201_CREATED
                if device_result["created"]
                else status.HTTP_200_OK
            )
        )


class DeviceLogoutView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(tags=["device"])
    def post(self, request):
        device_id = request.data.get("device_id")

        if not device_id:
            return Response(
                {
                    "status": False,
                    "detail": "device_id majburiy."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        updated_count = DeviceToken.objects.filter(
            user=request.user,
            device_id=device_id,
            is_active=True
        ).update(
            is_active=False
        )

        if updated_count == 0:
            return Response(
                {
                    "status": False,
                    "detail": "Aktiv device topilmadi."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        return Response(
            {
                "status": True,
                "detail": "Device logout qilindi."
            },
            status=status.HTTP_200_OK
        )