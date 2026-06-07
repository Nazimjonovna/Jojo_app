from datetime import timedelta
from django.utils import timezone
from django.utils.dateparse import parse_date
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from django.db.models import Sum, Q, F
from .pagination import paginate_queryset
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from .permissions import IsParent, IsChild, IsParentOfChild
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
    SavedLocation,
    GameCategory,
    GameItem,
    ShopCategory,
    ShopItem,
    ChildWallet,
    ChildTransaction,
    ShopPurchase,
    SOSAlert,
    ChildInstalledApp,
    ChildAppUsage,
    ChildAppLimit,
    ChildBlockedApp,
    AppVersion,
    ChildDailyActivity,
    SavedLocationVisit,
    ChildSavedLocationEvent,
    SubscriptionPlan, 
    UserSubscription, 
    SubscriptionPayment,
    BlogCategory,
    BlogPost,
    BlogPostSave,
    BlogPostLike,
    ParentStoreCategory,
    ParentStoreProduct,
    ParentStorePromoBanner,
    ParentStoreSavedProduct,
    ParentStoreOrder,
    generate_parent_store_order_code,
    ChildFrequentPlace,
    ChildDestinationPrediction,
    ParentNotification,
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
    SavedLocationSerializer,
    GameCategorySerializer,
    GameItemSerializer,
    ShopCategorySerializer,
    ShopItemSerializer,
    ChildWalletSerializer,
    ChildTransactionSerializer,
    ShopPurchaseSerializer,
    ShopPurchaseCreateSerializer,
    SOSAlertSerializer,
    CreateSOSAlertSerializer,
    ChildInstalledAppSerializer,
    ChildAppSyncSerializer,
    ChildAppUsageSyncSerializer,
    ChildAppUsageSerializer,
    SetChildAppLimitSerializer,
    ChildAppLimitSerializer,
    BlockChildAppSerializer,
    ChildBlockedAppSerializer,
    ChildTrackPointSerializer,
    AppVersionCheckSerializer,
    ChildDailyActivitySerializer,
    ChildDailyActivitySyncSerializer,
    SavedLocationVisitSerializer,
    ChildSavedLocationEventSerializer,
    SubscriptionPlanSerializer,
    UserSubscriptionSerializer,
    SubscriptionPaymentSerializer,
    ActivateSubscriptionSerializer,
    AdminGiveSubscriptionSerializer,
    BlogCategorySerializer,
    BlogPostListSerializer,
    BlogPostDetailSerializer,
    ParentStoreCategorySerializer,
    ParentStoreProductListSerializer,
    ParentStoreProductDetailSerializer,
    ParentStorePromoBannerSerializer,
    ParentStoreSavedProductSerializer,
    ParentStoreOrderSerializer,
    ParentStoreOrderCreateSerializer,
    ParentNotificationSerializer,
)
from .services import (process_child_location, )
from .subscription import (
    give_free_trial_if_new_user,
    sync_user_premium_status,
    activate_paid_subscription,
    get_paid_plans,
)


def get_tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    return {"refresh": str(refresh), "access": str(refresh.access_token)}


def send_sms_code(phone, code):
    print(f"SMS CODE for {phone}: {code}")
    return True


def save_user_device(user, device_id, token, device_type="android"):
    if not device_id:
        return {"error": True, "detail": "device_id majburiy."}
    if not token:
        return {"error": True, "detail": "Firebase token majburiy."}
    if user.role == User.ROLE_CHILD:
        active_device = DeviceToken.objects.filter(user=user, is_active=True).exclude(device_id=device_id).first()
        if active_device:
            return {"error": True, "detail": "Bu child akkaunt boshqa qurilmada aktiv. Avval birinchi device_id dan logout qiling.", "active_device_id": active_device.device_id}
    device, created = DeviceToken.objects.update_or_create(user=user, device_id=device_id, defaults={"token": token, "device_type": device_type, "is_active": True, "last_login_at": timezone.now()})
    return {"error": False, "device": device, "created": created}


def parse_version(version):
    try:
        return tuple(int(part) for part in version.split("."))
    except Exception:
        return (0,)


def is_version_less(current, target):
    current_parts = parse_version(current)
    target_parts = parse_version(target)
    max_len = max(len(current_parts), len(target_parts))
    current_parts = current_parts + (0,) * (max_len - len(current_parts))
    target_parts = target_parts + (0,) * (max_len - len(target_parts))
    return current_parts < target_parts


def get_movement_status(speed):
    if speed is None:
        return {"status": "unknown", "label": "Noma’lum"}
    try:
        speed_kmh = float(speed) * 3.6
    except Exception:
        return {"status": "unknown", "label": "Noma’lum"}
    if speed_kmh < 1:
        return {"status": "idle", "label": "Joyida"}
    if speed_kmh < 7:
        return {"status": "walking", "label": "Yuryapti"}
    return {"status": "vehicle", "label": "Mashinada"}


def get_premium_payload(user):
    active_subscription = sync_user_premium_status(user)

    return {
        "is_premium": user.has_active_premium(),
        "premium_expires_at": user.premium_expires_at,
        "expired_time": user.premium_expires_at,
        "subscription": {
            "id": active_subscription.id,
            "status": active_subscription.status,
            "source": active_subscription.source,
            "started_at": active_subscription.started_at,
            "expires_at": active_subscription.expires_at,
            "days_left": active_subscription.days_left(),
            "plan": {
                "id": active_subscription.plan.id,
                "name": active_subscription.plan.name,
                "is_trial": active_subscription.plan.is_trial,
                "trial_days": active_subscription.plan.trial_days,
                "price": active_subscription.plan.price,
                "currency": active_subscription.plan.currency,
            } if active_subscription.plan else None,
        } if active_subscription else None,
    }


class SendOTPView(APIView):
    permission_classes = [AllowAny]
    @swagger_auto_schema(request_body=SendOTPSerializer, tags=["register"])
    def post(self, request):
        serializer = SendOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone = serializer.validated_data["phone"]
        last_otp = OTPCode.objects.filter(phone=phone).order_by("-created_at").first()
        if last_otp and last_otp.is_blocked():
            time_left = last_otp.block_time_left_seconds()
            return Response({"status": False, "detail": "Juda ko‘p noto‘g‘ri urinish. Keyinroq qayta urinib ko‘ring.", "blocked": True, "time_left_seconds": time_left, "time_left_minutes": round(time_left / 60, 1)}, status=status.HTTP_429_TOO_MANY_REQUESTS)
        if last_otp:
            seconds = (timezone.now() - last_otp.created_at).total_seconds()
            if seconds < 60:
                time_left = int(60 - seconds)
                return Response({"status": False, "detail": f"SMS kodni qayta yuborish uchun {time_left} sekund kuting.", "time_left": time_left}, status=status.HTTP_429_TOO_MANY_REQUESTS)
        code = generate_numeric_code(6)
        OTPCode.objects.create(phone=phone, code=code, expires_at=timezone.now() + timedelta(minutes=5))
        send_sms_code(phone, code)
        return Response({"status": True, "detail": "SMS kod yuborildi.", "code": code, "lifetime": "5 minutes"}, status=status.HTTP_200_OK)


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
            is_used=False
        ).order_by("-created_at").first()

        if not otp:
            return Response(
                {
                    "status": False,
                    "detail": "Aktiv SMS kod topilmadi. Yangi kod oling."
                },
                status=status.HTTP_400_BAD_REQUEST
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
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )

        if otp.is_expired():
            return Response(
                {
                    "status": False,
                    "detail": "SMS kod muddati tugagan."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        now = timezone.now()

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
                        "time_left_seconds": 1800,
                        "time_left_minutes": 30,
                    },
                    status=status.HTTP_429_TOO_MANY_REQUESTS
                )

            otp.save(update_fields=["attempt_count", "first_attempt_at"])

            return Response(
                {
                    "status": False,
                    "detail": "SMS kod noto‘g‘ri.",
                    "attempts_left": attempts_left,
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        otp.is_used = True
        otp.save(update_fields=["is_used"])

        user = User.objects.filter(
            phone=phone,
            role=User.ROLE_PARENT
        ).first()

        if user:
            tokens = get_tokens_for_user(user)
            premium = get_premium_payload(user)

            return Response(
                {
                    "status": True,
                    "is_registered": True,
                    "detail": "SMS kod tasdiqlandi. User avval ro‘yxatdan o‘tgan. Token qaytarildi.",
                    "user": UserSerializer(user).data,
                    "premium": premium,
                    "is_premium": premium["is_premium"],
                    "premium_expires_at": premium["premium_expires_at"],
                    "expired_time": premium["expired_time"],
                    "tokens": tokens,
                },
                status=status.HTTP_200_OK
            )

        return Response(
            {
                "status": True,
                "is_registered": False,
                "detail": "SMS kod tasdiqlandi. User hali ro‘yxatdan o‘tmagan. Parent/register endpointini chaqiring.",
                "is_premium": False,
                "premium_expires_at": None,
                "expired_time": None,
                "premium": None,
            },
            status=status.HTTP_201_CREATED
        )


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

        existing_user = User.objects.filter(
            phone=phone,
            role=User.ROLE_PARENT
        ).first()

        if existing_user:
            device_result = save_user_device(
                existing_user,
                device_id,
                token,
                device_type
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

            premium = get_premium_payload(existing_user)

            return Response(
                {
                    "status": True,
                    "is_registered": True,
                    "detail": "User avval ro‘yxatdan o‘tgan. Token qaytarildi.",
                    "user": UserSerializer(existing_user).data,
                    "device": DeviceTokenSerializer(device_result["device"]).data,
                    "premium": premium,
                    "is_premium": premium["is_premium"],
                    "premium_expires_at": premium["premium_expires_at"],
                    "expired_time": premium["expired_time"],
                    "tokens": get_tokens_for_user(existing_user),
                },
                status=status.HTTP_200_OK
            )

        user = serializer.save()

        give_free_trial_if_new_user(user)

        device_result = save_user_device(
            user,
            device_id,
            token,
            device_type
        )

        if device_result.get("error"):
            user.delete()

            return Response(
                {
                    "status": False,
                    "detail": device_result["detail"],
                    "active_device_id": device_result.get("active_device_id"),
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        premium = get_premium_payload(user)

        return Response(
            {
                "status": True,
                "is_registered": False,
                "detail": "Parent muvaffaqiyatli ro‘yxatdan o‘tdi.",
                "user": UserSerializer(user).data,
                "device": DeviceTokenSerializer(device_result["device"]).data,
                "premium": premium,
                "is_premium": premium["is_premium"],
                "premium_expires_at": premium["premium_expires_at"],
                "expired_time": premium["expired_time"],
                "tokens": get_tokens_for_user(user),
            },
            status=status.HTTP_201_CREATED
        )
        

class MeView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(tags=["info"])
    def get(self, request):
        premium = get_premium_payload(request.user)

        return Response(
            {
                "status": True,
                "user": UserSerializer(request.user).data,
                "premium": premium,
                "is_premium": premium["is_premium"],
                "premium_expires_at": premium["premium_expires_at"],
                "expired_time": premium["expired_time"],
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
        return Response({"status": True, "detail": "Til muvaffaqiyatli o‘zgartirildi.", "user": UserSerializer(request.user).data}, status=status.HTTP_200_OK)


class CreatePairingCodeView(APIView):
    permission_classes = [IsParent]
    @swagger_auto_schema(request_body=CreateChildPairingSerializer, tags=["child"])
    def post(self, request):
        child_id = request.data.get("child_id")
        if child_id:
            if not ParentChild.objects.filter(parent=request.user, child_id=child_id).exists():
                return Response({"status": False, "detail": "Bu child sizga tegishli emas."}, status=status.HTTP_403_FORBIDDEN)
            child = User.objects.filter(id=child_id, role=User.ROLE_CHILD).first()
            if not child:
                return Response({"status": False, "detail": "Child topilmadi."}, status=status.HTTP_404_NOT_FOUND)
            if child.child_status == User.CHILD_STATUS_ACTIVE:
                return Response({"status": False, "detail": "Bu child allaqachon active. Pairing code kerak emas."}, status=status.HTTP_400_BAD_REQUEST)
            existing_pairing = PairingCode.objects.filter(parent=request.user, child=child, is_used=False).order_by("-created_at").first()
            if existing_pairing:
                return Response({"status": True, "already_exists": True, "detail": f"Bu pairing code {child.full_name or child.first_name} uchun avval olingan.", "child": ChildSerializer(child).data, "pairing": PairingCodeSerializer(existing_pairing).data, "qr_payload": {"type": "jojo_child_pairing", "code": existing_pairing.code, "child_id": child.id}}, status=status.HTTP_200_OK)
            code = generate_numeric_code(6)
            while PairingCode.objects.filter(code=code, is_used=False).exists():
                code = generate_numeric_code(6)
            pairing = PairingCode.objects.create(parent=request.user, child=child, code=code, expires_at=timezone.now() + timedelta(days=3), child_name=child.full_name or child.first_name, child_gender=child.gender, child_age=child.age, child_avatar=child.avatar)
            return Response({"status": True, "already_exists": False, "detail": f"{child.full_name or child.first_name} uchun pairing code yaratildi.", "child": ChildSerializer(child).data, "pairing": PairingCodeSerializer(pairing).data, "qr_payload": {"type": "jojo_child_pairing", "code": pairing.code, "child_id": child.id}}, status=status.HTTP_201_CREATED)
        serializer = CreateChildPairingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        child = User.objects.create_user(phone=f"+998CHILD{generate_numeric_code(8)}", username=f"child_{generate_numeric_code(10)}", full_name=serializer.validated_data["child_name"], first_name=serializer.validated_data["child_name"], role=User.ROLE_CHILD, gender=serializer.validated_data["child_gender"], age=serializer.validated_data["child_age"], language=request.user.language, avatar=serializer.validated_data.get("child_avatar"), child_status=User.CHILD_STATUS_NON_ACTIVE, pending_delete_at=timezone.now() + timedelta(days=3))
        ParentChild.objects.create(parent=request.user, child=child)
        code = generate_numeric_code(6)
        while PairingCode.objects.filter(code=code, is_used=False).exists():
            code = generate_numeric_code(6)
        pairing = PairingCode.objects.create(parent=request.user, child=child, code=code, expires_at=timezone.now() + timedelta(days=3), child_name=child.full_name, child_gender=child.gender, child_age=child.age, child_avatar=child.avatar)
        return Response({"status": True, "already_exists": False, "detail": "Bola non-active holatda yaratildi. Pairing code 3 kun ichida ishlatilishi kerak.", "child": ChildSerializer(child).data, "pairing": PairingCodeSerializer(pairing).data, "qr_payload": {"type": "jojo_child_pairing", "code": pairing.code, "child_id": child.id}}, status=status.HTTP_201_CREATED)


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
        pairing = PairingCode.objects.filter(code=code, is_used=False).select_related("child", "parent").first()
        if not pairing:
            return Response({"status": False, "detail": "Pairing code noto‘g‘ri yoki ishlatilgan."}, status=status.HTTP_400_BAD_REQUEST)
        if pairing.is_expired():
            return Response({"status": False, "detail": "Pairing code muddati tugagan. Parent qaytadan bola qo‘shishi kerak."}, status=status.HTTP_400_BAD_REQUEST)
        child = pairing.child
        if not child:
            return Response({"status": False, "detail": "Bu pairing code uchun child topilmadi."}, status=status.HTTP_400_BAD_REQUEST)
        if child.child_status == User.CHILD_STATUS_ACTIVE:
            return Response({"status": False, "detail": "Bu child allaqachon active holatda."}, status=status.HTTP_400_BAD_REQUEST)
        if child.is_child_pending_expired():
            child.delete()
            return Response({"status": False, "detail": "Pairing muddati tugagan. Bola DB’dan o‘chirildi. Parent qaytadan qo‘shishi kerak."}, status=status.HTTP_410_GONE)
        device_result = save_user_device(child, device_id, token, device_type)
        if device_result.get("error"):
            return Response({"status": False, "detail": device_result["detail"], "active_device_id": device_result.get("active_device_id")}, status=status.HTTP_400_BAD_REQUEST)
        child.child_status = User.CHILD_STATUS_ACTIVE
        child.pending_delete_at = None
        child.save(update_fields=["child_status", "pending_delete_at"])
        pairing.is_used = True
        pairing.save(update_fields=["is_used"])
        return Response({"status": True, "detail": "Child muvaffaqiyatli active qilindi.", "child": ChildSerializer(child).data, "device": DeviceTokenSerializer(device_result["device"]).data, "tokens": get_tokens_for_user(child)}, status=status.HTTP_200_OK)


class MyChildrenView(APIView):
    permission_classes = [IsParent]
    @swagger_auto_schema(tags=["info"])
    def get(self, request):
        expired_children = User.objects.filter(parent_links__parent=request.user, role=User.ROLE_CHILD, child_status=User.CHILD_STATUS_NON_ACTIVE, pending_delete_at__isnull=False, pending_delete_at__lte=timezone.now())
        expired_count = expired_children.count()
        expired_children.delete()
        links = ParentChild.objects.filter(parent=request.user).select_related("child")
        children = [link.child for link in links]
        active_children = [child for child in children if child.child_status == User.CHILD_STATUS_ACTIVE]
        non_active_children = [child for child in children if child.child_status == User.CHILD_STATUS_NON_ACTIVE]
        return Response({"status": True, "deleted_expired_children_count": expired_count, "active_children": ChildSerializer(active_children, many=True).data, "non_active_children": ChildSerializer(non_active_children, many=True).data}, status=status.HTTP_200_OK)


class ParentChildLogoutView(APIView):
    permission_classes = [IsParentOfChild]
    @swagger_auto_schema(tags=["child"])
    def post(self, request, child_id):
        child = User.objects.filter(id=child_id, role=User.ROLE_CHILD).first()
        if not child:
            return Response({"status": False, "detail": "Child topilmadi."}, status=status.HTTP_404_NOT_FOUND)
        DeviceToken.objects.filter(user=child, is_active=True).update(is_active=False)
        child.child_status = User.CHILD_STATUS_NON_ACTIVE
        child.pending_delete_at = timezone.now() + timedelta(days=3)
        child.save(update_fields=["child_status", "pending_delete_at"])
        existing_pairing = PairingCode.objects.filter(parent=request.user, child=child, is_used=False).order_by("-created_at").first()
        if not existing_pairing:
            code = generate_numeric_code(6)
            while PairingCode.objects.filter(code=code, is_used=False).exists():
                code = generate_numeric_code(6)
            existing_pairing = PairingCode.objects.create(parent=request.user, child=child, code=code, expires_at=timezone.now() + timedelta(days=3), child_name=child.full_name or child.first_name, child_gender=child.gender, child_age=child.age, child_avatar=child.avatar)
        else:
            existing_pairing.expires_at = timezone.now() + timedelta(days=3)
            existing_pairing.save(update_fields=["expires_at"])
        return Response({"status": True, "detail": f"{child.full_name or child.first_name} logout qilindi va non-active holatga o‘tkazildi.", "child": ChildSerializer(child).data, "pairing": PairingCodeSerializer(existing_pairing).data}, status=status.HTTP_200_OK)


class ParentRouteListCreateView(APIView):
    permission_classes = [IsParent]
    @swagger_auto_schema(tags=["location"])
    def get(self, request):
        routes = SafeRoute.objects.filter(parent=request.user).prefetch_related("points").order_by("-created_at")
        return Response({"status": True, "routes": SafeRouteSerializer(routes, many=True).data}, status=status.HTTP_200_OK)
    @swagger_auto_schema(request_body=SafeRouteSerializer, tags=["location"])
    def post(self, request):
        serializer = SafeRouteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        route = serializer.save(parent=request.user)
        return Response({"status": True, "detail": "Marshrut yaratildi.", "route": SafeRouteSerializer(route).data}, status=status.HTTP_201_CREATED)


class ParentRouteDetailView(APIView):
    permission_classes = [IsParent]
    def get_object(self, request, route_id):
        try:
            return SafeRoute.objects.get(id=route_id, parent=request.user)
        except SafeRoute.DoesNotExist:
            return None
    @swagger_auto_schema(tags=["location"])
    def get(self, request, route_id):
        route = self.get_object(request, route_id)
        if not route:
            return Response({"status": False, "detail": "Route topilmadi."}, status=status.HTTP_404_NOT_FOUND)
        return Response({"status": True, "route": SafeRouteSerializer(route).data}, status=status.HTTP_200_OK)
    @swagger_auto_schema(request_body=SafeRouteSerializer, tags=["location"])
    def patch(self, request, route_id):
        route = self.get_object(request, route_id)
        if not route:
            return Response({"status": False, "detail": "Route topilmadi."}, status=status.HTTP_404_NOT_FOUND)
        serializer = SafeRouteSerializer(route, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        route = serializer.save()
        return Response({"status": True, "detail": "Route yangilandi.", "route": SafeRouteSerializer(route).data}, status=status.HTTP_200_OK)
    @swagger_auto_schema(tags=["location"])
    def delete(self, request, route_id):
        route = self.get_object(request, route_id)
        if not route:
            return Response({"status": False, "detail": "Route topilmadi."}, status=status.HTTP_404_NOT_FOUND)
        route.delete()
        return Response({"status": True, "detail": "Route o‘chirildi."}, status=status.HTTP_200_OK)


class AssignRouteToChildView(APIView):
    permission_classes = [IsParent]
    @swagger_auto_schema(request_body=ChildRouteAssignmentSerializer, tags=["location"])
    def post(self, request):
        serializer = ChildRouteAssignmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        child = serializer.validated_data["child"]
        route = serializer.validated_data["route"]
        if not ParentChild.objects.filter(parent=request.user, child=child).exists():
            return Response({"status": False, "detail": "Bu child sizga tegishli emas."}, status=status.HTTP_403_FORBIDDEN)
        if route.parent_id != request.user.id:
            return Response({"status": False, "detail": "Bu route sizga tegishli emas."}, status=status.HTTP_403_FORBIDDEN)
        assignment = serializer.save(parent=request.user)
        return Response({"status": True, "detail": "Route childga biriktirildi.", "assignment": ChildRouteAssignmentSerializer(assignment).data}, status=status.HTTP_201_CREATED)


class ParentChildAssignmentsView(APIView):
    permission_classes = [IsParentOfChild]
    @swagger_auto_schema(tags=["location"])
    def get(self, request, child_id):
        assignments = ChildRouteAssignment.objects.filter(parent=request.user, child_id=child_id).select_related("route").order_by("-created_at")
        return Response({"status": True, "assignments": ChildRouteAssignmentSerializer(assignments, many=True).data}, status=status.HTTP_200_OK)


class ChildActiveRoutesView(APIView):
    permission_classes = [IsChild]
    @swagger_auto_schema(tags=["location"])
    def get(self, request):
        assignments = ChildRouteAssignment.objects.filter(child=request.user, status=ChildRouteAssignment.STATUS_ACTIVE, route__is_active=True).select_related("route").prefetch_related("route__points")
        return Response({"status": True, "assignments": ChildRouteAssignmentSerializer(assignments, many=True).data}, status=status.HTTP_200_OK)


class SendChildLocationView(APIView):
    permission_classes = [IsChild]
    @swagger_auto_schema(request_body=ChildLocationSerializer, tags=["location"])
    def post(self, request):
        serializer = ChildLocationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        location, realtime_payload = process_child_location(child=request.user, latitude=serializer.validated_data["latitude"], longitude=serializer.validated_data["longitude"], accuracy=serializer.validated_data.get("accuracy"), battery_level=serializer.validated_data.get("battery_level"), speed=serializer.validated_data.get("speed"), heading=serializer.validated_data.get("heading"), source=ChildLocation.SOURCE_REST)
        return Response({"status": True, "detail": "Location saqlandi va real-time yuborildi.", "location": ChildLocationSerializer(location).data, "realtime_payload": realtime_payload}, status=status.HTTP_201_CREATED)


class ChildLastLocationView(APIView):
    permission_classes = [IsParentOfChild]
    @swagger_auto_schema(tags=["location"])
    def get(self, request, child_id):
        try:
            location = ChildLastLocation.objects.get(child_id=child_id)
        except ChildLastLocation.DoesNotExist:
            return Response({"status": False, "detail": "Location hali yuborilmagan."}, status=status.HTTP_404_NOT_FOUND)
        return Response({"status": True, "location": ChildLastLocationSerializer(location).data}, status=status.HTTP_200_OK)

class ChildLocationHistoryView(APIView):
    permission_classes = [IsParentOfChild]

    @swagger_auto_schema(tags=["location"])
    def get(self, request, child_id):
        date = request.query_params.get("date")
        date_from = request.query_params.get("date_from")
        date_to = request.query_params.get("date_to")
        locations = ChildLocation.objects.filter(
            child_id=child_id
        )
        if date:
            parsed_date = parse_date(date)
            if parsed_date:
                locations = locations.filter(created_at__date=parsed_date)
        if date_from:
            parsed_from = parse_date(date_from)
            if parsed_from:
                locations = locations.filter(created_at__date__gte=parsed_from)
        if date_to:
            parsed_to = parse_date(date_to)
            if parsed_to:
                locations = locations.filter(created_at__date__lte=parsed_to)
        locations = locations.order_by("created_at")
        response = paginate_queryset(
            request=request,
            queryset=locations,
            serializer_class=ChildTrackPointSerializer,
            page_size=100,
        )
        response.data["child_id"] = child_id
        return response

class RouteAlertListView(APIView):
    permission_classes = [IsParent]

    @swagger_auto_schema(tags=["location"])
    def get(self, request):
        alerts = RouteAlert.objects.filter(
            assignment__parent=request.user
        ).select_related(
            "child",
            "assignment",
            "assignment__route",
        ).order_by("-created_at")
        return paginate_queryset(
            request=request,
            queryset=alerts,
            serializer_class=RouteAlertSerializer,
            page_size=20,
        )


class DeviceTokenView(APIView):
    permission_classes = [IsAuthenticated]
    @swagger_auto_schema(request_body=DeviceTokenSerializer, tags=["device"])
    def post(self, request):
        serializer = DeviceTokenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        device_result = save_user_device(user=request.user, device_id=serializer.validated_data["device_id"], token=serializer.validated_data["token"], device_type=serializer.validated_data["device_type"])
        if device_result.get("error"):
            return Response({"status": False, "detail": device_result["detail"], "active_device_id": device_result.get("active_device_id")}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"status": True, "detail": "Device token saqlandi.", "device": DeviceTokenSerializer(device_result["device"]).data}, status=status.HTTP_201_CREATED if device_result["created"] else status.HTTP_200_OK)


class DeviceLogoutView(APIView):
    permission_classes = [IsAuthenticated]
    @swagger_auto_schema(tags=["device"])
    def post(self, request):
        device_id = request.data.get("device_id")
        if not device_id:
            return Response({"status": False, "detail": "device_id majburiy."}, status=status.HTTP_400_BAD_REQUEST)
        updated_count = DeviceToken.objects.filter(user=request.user, device_id=device_id, is_active=True).update(is_active=False)
        if updated_count == 0:
            return Response({"status": False, "detail": "Aktiv device topilmadi."}, status=status.HTTP_404_NOT_FOUND)
        return Response({"status": True, "detail": "Device logout qilindi."}, status=status.HTTP_200_OK)


class SavedLocationListCreateView(APIView):
    permission_classes = [IsParent]
    @swagger_auto_schema(tags=["saved-location"])
    def get(self, request):
        locations = SavedLocation.objects.filter(
            parent=request.user
        ).order_by("-created_at")
        return paginate_queryset(
            request=request,
            queryset=locations,
            serializer_class=SavedLocationSerializer,
            page_size=20,
        )
    @swagger_auto_schema(request_body=SavedLocationSerializer, tags=["saved-location"])
    def post(self, request):
        serializer = SavedLocationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        saved_location = serializer.save(parent=request.user)
        return Response({"status": True, "detail": "Saved location yaratildi.", "saved_location": SavedLocationSerializer(saved_location).data}, status=status.HTTP_201_CREATED)


class SavedLocationDetailView(APIView):
    permission_classes = [IsParent]
    def get_object(self, request, location_id):
        try:
            return SavedLocation.objects.get(id=location_id, parent=request.user)
        except SavedLocation.DoesNotExist:
            return None
    @swagger_auto_schema(tags=["saved-location"])
    def get(self, request, location_id):
        saved_location = self.get_object(request, location_id)
        if not saved_location:
            return Response({"status": False, "detail": "Saved location topilmadi."}, status=status.HTTP_404_NOT_FOUND)
        child_id = request.query_params.get("child_id")
        return Response({"status": True, "saved_location": SavedLocationSerializer(saved_location, context={"child_id": child_id}).data}, status=status.HTTP_200_OK)
    @swagger_auto_schema(request_body=SavedLocationSerializer, tags=["saved-location"])
    def patch(self, request, location_id):
        saved_location = self.get_object(request, location_id)
        if not saved_location:
            return Response({"status": False, "detail": "Saved location topilmadi."}, status=status.HTTP_404_NOT_FOUND)
        serializer = SavedLocationSerializer(saved_location, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        saved_location = serializer.save()
        return Response({"status": True, "detail": "Saved location yangilandi.", "saved_location": SavedLocationSerializer(saved_location).data}, status=status.HTTP_200_OK)
    @swagger_auto_schema(tags=["saved-location"])
    def delete(self, request, location_id):
        saved_location = self.get_object(request, location_id)
        if not saved_location:
            return Response({"status": False, "detail": "Saved location topilmadi."}, status=status.HTTP_404_NOT_FOUND)
        saved_location.delete()
        return Response({"status": True, "detail": "Saved location o‘chirildi."}, status=status.HTTP_200_OK)


class KidsGameCategoryListView(APIView):
    permission_classes = [IsChild]

    def get(self, request):
        categories = GameCategory.objects.filter(
            is_active=True
        ).order_by("order", "id")
        return paginate_queryset(
            request=request,
            queryset=categories,
            serializer_class=GameCategorySerializer,
            page_size=20,
        )


class KidsGameListView(APIView):
    permission_classes = [IsChild]

    def get(self, request):
        category_id = request.query_params.get("category_id")
        featured = request.query_params.get("featured")
        child_age = request.user.age or 18
        games = GameItem.objects.filter(
            is_active=True,
            age_min__lte=child_age,
            age_max__gte=child_age,
        ).select_related("category")
        if category_id:
            games = games.filter(category_id=category_id)
        if featured == "true":
            games = games.filter(is_featured=True)
        games = games.order_by("order", "-created_at")
        return paginate_queryset(
            request=request,
            queryset=games,
            serializer_class=GameItemSerializer,
            page_size=20,
        )


class KidsGameDetailView(APIView):
    permission_classes = [IsChild]
    def get(self, request, game_id):
        game = GameItem.objects.select_related("category").filter(id=game_id, is_active=True).first()
        if not game:
            return Response({"status": False, "detail": "Game topilmadi."}, status=status.HTTP_404_NOT_FOUND)
        return Response({"status": True, "game": GameItemSerializer(game).data}, status=status.HTTP_200_OK)


class KidsShopCategoryListView(APIView):
    permission_classes = [IsChild]

    def get(self, request):
        categories = ShopCategory.objects.filter(
            is_active=True
        ).order_by("order", "id")
        return paginate_queryset(
            request=request,
            queryset=categories,
            serializer_class=ShopCategorySerializer,
            page_size=20,
        )


class KidsShopItemListView(APIView):
    permission_classes = [IsChild]

    def get(self, request):
        category_id = request.query_params.get("category_id")
        featured = request.query_params.get("featured")
        child_age = request.user.age or 18
        items = ShopItem.objects.filter(
            is_active=True,
            age_min__lte=child_age,
            age_max__gte=child_age,
        ).select_related("category")
        if category_id:
            items = items.filter(category_id=category_id)
        if featured == "true":
            items = items.filter(is_featured=True)
        items = items.order_by("order", "-created_at")
        return paginate_queryset(
            request=request,
            queryset=items,
            serializer_class=ShopItemSerializer,
            page_size=20,
        )


class KidsShopItemDetailView(APIView):
    permission_classes = [IsChild]
    def get(self, request, item_id):
        item = ShopItem.objects.select_related("category").filter(id=item_id, is_active=True).first()
        if not item:
            return Response({"status": False, "detail": "Shop item topilmadi."}, status=status.HTTP_404_NOT_FOUND)
        return Response({"status": True, "item": ShopItemSerializer(item).data}, status=status.HTTP_200_OK)


class KidsWalletView(APIView):
    permission_classes = [IsChild]
    def get(self, request):
        wallet, _ = ChildWallet.objects.get_or_create(child=request.user)
        return Response({"status": True, "wallet": ChildWalletSerializer(wallet).data}, status=status.HTTP_200_OK)


class KidsTransactionListView(APIView):
    permission_classes = [IsChild]

    def get(self, request):
        transactions = ChildTransaction.objects.filter(
            child=request.user
        ).order_by("-created_at")
        return paginate_queryset(
            request=request,
            queryset=transactions,
            serializer_class=ChildTransactionSerializer,
            page_size=20,
        )


class KidsShopPurchaseView(APIView):
    permission_classes = [IsChild]
    def post(self, request):
        serializer = ShopPurchaseCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        item = ShopItem.objects.filter(id=serializer.validated_data["item_id"], is_active=True).first()
        if not item:
            return Response({"status": False, "detail": "Shop item topilmadi."}, status=status.HTTP_404_NOT_FOUND)
        wallet, _ = ChildWallet.objects.get_or_create(child=request.user)
        if wallet.balance < item.price_points:
            return Response({"status": False, "detail": "Balans yetarli emas.", "balance": wallet.balance, "price_points": item.price_points}, status=status.HTTP_400_BAD_REQUEST)
        wallet.balance -= item.price_points
        wallet.save(update_fields=["balance"])
        purchase = ShopPurchase.objects.create(child=request.user, item=item, price_points=item.price_points, status=ShopPurchase.STATUS_PENDING)
        ChildTransaction.objects.create(child=request.user, amount=-item.price_points, transaction_type=ChildTransaction.TYPE_SPEND, source="shop_purchase", description=f"Purchased {item.title}")
        return Response({"status": True, "detail": "Shop item sotib olindi. Parent/admin tasdiqlashi mumkin.", "wallet": ChildWalletSerializer(wallet).data, "purchase": ShopPurchaseSerializer(purchase).data}, status=status.HTTP_201_CREATED)


class KidsSOSCreateView(APIView):
    permission_classes = [IsChild]
    def post(self, request):
        serializer = CreateSOSAlertSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        parent_link = ParentChild.objects.filter(child=request.user).select_related("parent").first()
        if not parent_link:
            return Response({"status": False, "detail": "Bu child uchun parent topilmadi."}, status=status.HTTP_404_NOT_FOUND)
        parent = parent_link.parent
        latitude = serializer.validated_data.get("latitude")
        longitude = serializer.validated_data.get("longitude")
        if latitude is None or longitude is None:
            try:
                last_location = request.user.last_location
                latitude = last_location.latitude
                longitude = last_location.longitude
            except ChildLastLocation.DoesNotExist:
                pass
        sos = SOSAlert.objects.create(child=request.user, parent=parent, latitude=latitude, longitude=longitude, address=serializer.validated_data.get("address"), note=serializer.validated_data.get("note"))
        return Response({"status": True, "detail": "SOS yuborildi.", "sos": SOSAlertSerializer(sos).data, "parent_phone": parent.phone}, status=status.HTTP_201_CREATED)


class ParentSOSAlertListView(APIView):
    permission_classes = [IsParent]

    def get(self, request):
        alerts = SOSAlert.objects.filter(
            parent=request.user
        ).select_related(
            "child",
            "parent",
        ).order_by("-created_at")
        return paginate_queryset(
            request=request,
            queryset=alerts,
            serializer_class=SOSAlertSerializer,
            page_size=20,
        )


class ParentSOSAlertResolveView(APIView):
    permission_classes = [IsParent]
    def post(self, request, sos_id):
        sos = SOSAlert.objects.filter(id=sos_id, parent=request.user).first()
        if not sos:
            return Response({"status": False, "detail": "SOS alert topilmadi."}, status=status.HTTP_404_NOT_FOUND)
        sos.status = SOSAlert.STATUS_RESOLVED
        sos.save(update_fields=["status", "updated_at"])
        return Response({"status": True, "detail": "SOS alert resolved qilindi.", "sos": SOSAlertSerializer(sos).data}, status=status.HTTP_200_OK)


class ChildAppSyncView(APIView):
    permission_classes = [IsChild]
    @swagger_auto_schema(request_body=ChildAppSyncSerializer, tags=["app-control"])
    def post(self, request):
        serializer = ChildAppSyncSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        incoming_packages = []
        for item in serializer.validated_data["apps"]:
            package_name = item["package_name"]
            incoming_packages.append(package_name)
            ChildInstalledApp.objects.update_or_create(child=request.user, package_name=package_name, defaults={"app_name": item["app_name"], "category": item.get("category"), "is_system_app": item.get("is_system_app", False), "is_active": True})
        ChildInstalledApp.objects.filter(child=request.user).exclude(package_name__in=incoming_packages).update(is_active=False)
        apps = ChildInstalledApp.objects.filter(child=request.user, is_active=True).order_by("app_name")
        return Response({"status": True, "detail": "Installed apps synced.", "apps": ChildInstalledAppSerializer(apps, many=True).data}, status=status.HTTP_200_OK)


class ChildAppUsageSyncView(APIView):
    permission_classes = [IsChild]
    @swagger_auto_schema(request_body=ChildAppUsageSyncSerializer, tags=["app-control"])
    def post(self, request):
        serializer = ChildAppUsageSyncSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        saved_items = []
        for item in serializer.validated_data["usages"]:
            app = ChildInstalledApp.objects.filter(child=request.user, package_name=item["package_name"]).first()
            if not app:
                app = ChildInstalledApp.objects.create(child=request.user, package_name=item["package_name"], app_name=item["package_name"], is_active=True)
            usage, _ = ChildAppUsage.objects.update_or_create(child=request.user, app=app, usage_date=item["usage_date"], defaults={"total_usage_seconds": item["total_usage_seconds"], "open_count": item.get("open_count", 0), "first_opened_at": item.get("first_opened_at"), "last_opened_at": item.get("last_opened_at")})
            saved_items.append(usage)
        return Response({"status": True, "detail": "App usage synced.", "usages": ChildAppUsageSerializer(saved_items, many=True).data}, status=status.HTTP_200_OK)


class ChildAppPolicyView(APIView):
    permission_classes = [IsChild]
    def get(self, request):
        today = timezone.localdate()
        apps = ChildInstalledApp.objects.filter(child=request.user, is_active=True).order_by("app_name")
        policies = []
        for app in apps:
            try:
                is_blocked = app.block.is_blocked
            except ChildBlockedApp.DoesNotExist:
                is_blocked = False
            try:
                limit = app.limit
                daily_limit_seconds = limit.daily_limit_seconds
                is_limit_enabled = limit.is_enabled
            except ChildAppLimit.DoesNotExist:
                daily_limit_seconds = None
                is_limit_enabled = False
            usage = ChildAppUsage.objects.filter(child=request.user, app=app, usage_date=today).first()
            policies.append({"app_id": app.id, "package_name": app.package_name, "app_name": app.app_name, "is_blocked": is_blocked, "daily_limit_seconds": daily_limit_seconds, "is_limit_enabled": is_limit_enabled, "today_usage_seconds": usage.total_usage_seconds if usage else 0})
        return Response({"status": True, "policies": policies}, status=status.HTTP_200_OK)


class ParentChildAppListView(APIView):
    permission_classes = [IsParentOfChild]

    def get(self, request, child_id):
        tab = request.query_params.get("tab", "all")
        usage_date = request.query_params.get("date")
        parsed_date = parse_date(usage_date) if usage_date else timezone.localdate()
        apps = ChildInstalledApp.objects.filter(
            child_id=child_id,
            is_active=True
        )
        if tab == "blocked":
            apps = apps.filter(block__is_blocked=True)
        if tab == "limits":
            apps = apps.filter(limit__is_enabled=True)
        apps = apps.order_by("app_name")
        response = paginate_queryset(
            request=request,
            queryset=apps,
            serializer_class=ChildInstalledAppSerializer,
            context={
                "request": request,
                "usage_date": parsed_date,
            },
            page_size=30,
        )
        response.data["tab"] = tab
        response.data["date"] = str(parsed_date)
        response.data["child_id"] = child_id
        return response


def _build_and_push_child_policies(child_id):
    """Bola uchun joriy policy ro'yxatini yig'ib WS push qiladi.
    Block + limit ikkalasini ham birgalikda yuboradi — kids tomondagi
    `JojoAccessibilityService` shu format'da kutadi.
    """
    from .realtime import broadcast_child_app_policy

    apps = (
        ChildInstalledApp.objects
        .filter(child_id=child_id, is_active=True)
        .select_related("limit", "block")
    )
    policies = []
    for app in apps:
        limit = getattr(app, "limit", None)
        block = getattr(app, "block", None)
        is_blocked = bool(block and block.is_blocked)
        if not is_blocked and (not limit or not limit.is_enabled):
            continue
        policies.append({
            "package_name": app.package_name,
            "is_blocked": is_blocked,
            "daily_limit_seconds":
                limit.daily_limit_seconds if (limit and limit.is_enabled) else None,
        })
    try:
        broadcast_child_app_policy(child_id=child_id, policies=policies)
    except Exception:
        pass


class ParentSetChildAppLimitView(APIView):
    permission_classes = [IsParentOfChild]
    @swagger_auto_schema(request_body=SetChildAppLimitSerializer, tags=["app-control"])
    def post(self, request, child_id, app_id):
        app = ChildInstalledApp.objects.filter(id=app_id, child_id=child_id).first()
        if not app:
            return Response({"status": False, "detail": "App topilmadi."}, status=status.HTTP_404_NOT_FOUND)
        serializer = SetChildAppLimitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        limit, _ = ChildAppLimit.objects.update_or_create(child_id=child_id, app=app, defaults={"daily_limit_seconds": serializer.validated_data["daily_limit_seconds"], "is_enabled": serializer.validated_data.get("is_enabled", True), "created_by": request.user})
        _build_and_push_child_policies(child_id)
        return Response({"status": True, "detail": "App limit saqlandi.", "limit": ChildAppLimitSerializer(limit).data}, status=status.HTTP_200_OK)
    def delete(self, request, child_id, app_id):
        app = ChildInstalledApp.objects.filter(id=app_id, child_id=child_id).first()
        if not app:
            return Response({"status": False, "detail": "App topilmadi."}, status=status.HTTP_404_NOT_FOUND)
        ChildAppLimit.objects.filter(child_id=child_id, app=app).delete()
        _build_and_push_child_policies(child_id)
        return Response({"status": True, "detail": "App limit o‘chirildi."}, status=status.HTTP_200_OK)


class ParentBlockChildAppView(APIView):
    permission_classes = [IsParentOfChild]
    @swagger_auto_schema(request_body=BlockChildAppSerializer, tags=["app-control"])
    def post(self, request, child_id, app_id):
        app = ChildInstalledApp.objects.filter(id=app_id, child_id=child_id).first()
        if not app:
            return Response({"status": False, "detail": "App topilmadi."}, status=status.HTTP_404_NOT_FOUND)
        serializer = BlockChildAppSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        blocked_app, _ = ChildBlockedApp.objects.update_or_create(child_id=child_id, app=app, defaults={"is_blocked": serializer.validated_data.get("is_blocked", True), "reason": serializer.validated_data.get("reason"), "created_by": request.user})
        _build_and_push_child_policies(child_id)
        return Response({"status": True, "detail": "App block holati yangilandi.", "blocked_app": ChildBlockedAppSerializer(blocked_app).data}, status=status.HTTP_200_OK)


class ParentChildAppUsageStatsView(APIView):
    permission_classes = [IsParentOfChild]

    def get(self, request, child_id):
        date_from = parse_date(request.query_params.get("date_from")) if request.query_params.get("date_from") else None
        date_to = parse_date(request.query_params.get("date_to")) if request.query_params.get("date_to") else None
        usages = ChildAppUsage.objects.filter(
            child_id=child_id
        ).select_related("app")
        if date_from:
            usages = usages.filter(usage_date__gte=date_from)
        if date_to:
            usages = usages.filter(usage_date__lte=date_to)
        usages = usages.order_by("-usage_date", "-total_usage_seconds")
        total_seconds = sum(
            usages.values_list("total_usage_seconds", flat=True)
        )
        response = paginate_queryset(
            request=request,
            queryset=usages,
            serializer_class=ChildAppUsageSerializer,
            page_size=20,
        )
        response.data["total_usage_seconds"] = total_seconds
        response.data["child_id"] = child_id
        return response


class AppVersionCheckView(APIView):
    permission_classes = [AllowAny]
    @swagger_auto_schema(request_body=AppVersionCheckSerializer, tags=["version"])
    def post(self, request):
        serializer = AppVersionCheckSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        platform = serializer.validated_data["platform"]
        current_version = serializer.validated_data["current_version"]
        app_version = AppVersion.objects.filter(platform=platform, is_active=True).order_by("-created_at").first()
        if not app_version:
            return Response({"status": True, "update_required": False, "force_update": False, "detail": "Version config topilmadi."}, status=status.HTTP_200_OK)
        update_required = is_version_less(current=current_version, target=app_version.latest_version)
        force_update = is_version_less(current=current_version, target=app_version.min_supported_version) or app_version.force_update
        return Response({"status": True, "platform": platform, "current_version": current_version, "latest_version": app_version.latest_version, "min_supported_version": app_version.min_supported_version, "update_required": update_required, "force_update": force_update, "update_url": app_version.update_url, "title": app_version.title, "message": app_version.message}, status=status.HTTP_200_OK)


class ParentHomeSummaryView(APIView):
    permission_classes = [IsParent]
    def get(self, request):
        today = timezone.localdate()
        links = ParentChild.objects.filter(parent=request.user).select_related("child")
        children_data = []
        for link in links:
            child = link.child
            try:
                last_location = child.last_location
                movement = get_movement_status(last_location.speed)
                location_data = ChildLastLocationSerializer(last_location).data
            except ChildLastLocation.DoesNotExist:
                movement = {"status": "unknown", "label": "Noma’lum"}
                location_data = None
            activity = ChildDailyActivity.objects.filter(child=child, activity_date=today).first()
            children_data.append({"child": ChildSerializer(child).data, "movement": movement, "last_location": location_data, "today_activity": ChildDailyActivitySerializer(activity).data if activity else None})
        return Response({"status": True, "date": str(today), "children": children_data}, status=status.HTTP_200_OK)


class ChildDailyActivitySyncView(APIView):
    permission_classes = [IsChild]
    @swagger_auto_schema(request_body=ChildDailyActivitySyncSerializer, tags=["activity"])
    def post(self, request):
        serializer = ChildDailyActivitySyncSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        activity, _ = ChildDailyActivity.objects.update_or_create(child=request.user, activity_date=serializer.validated_data["activity_date"], defaults={"distance_meters": serializer.validated_data.get("distance_meters", 0), "steps_count": serializer.validated_data.get("steps_count", 0), "active_seconds": serializer.validated_data.get("active_seconds", 0)})
        return Response({"status": True, "detail": "Daily activity saqlandi.", "activity": ChildDailyActivitySerializer(activity).data}, status=status.HTTP_200_OK)


class ChildSavedLocationVisitSyncView(APIView):
    permission_classes = [IsChild]
    def post(self, request):
        saved_location_id = request.data.get("saved_location_id")
        if not saved_location_id:
            return Response({"status": False, "detail": "saved_location_id majburiy."}, status=status.HTTP_400_BAD_REQUEST)
        parent_link = ParentChild.objects.filter(child=request.user).select_related("parent").first()
        if not parent_link:
            return Response({"status": False, "detail": "Parent topilmadi."}, status=status.HTTP_404_NOT_FOUND)
        saved_location = SavedLocation.objects.filter(id=saved_location_id, parent=parent_link.parent).first()
        if not saved_location:
            return Response({"status": False, "detail": "Saved location topilmadi."}, status=status.HTTP_404_NOT_FOUND)
        visit, _ = SavedLocationVisit.objects.get_or_create(saved_location=saved_location, child=request.user)
        visit.visit_count += 1
        visit.last_visited_at = timezone.now()
        visit.save(update_fields=["visit_count", "last_visited_at", "updated_at"])
        return Response({"status": True, "detail": "Saved location visit saqlandi.", "visit": SavedLocationVisitSerializer(visit).data}, status=status.HTTP_200_OK)


class ParentSavedLocationEventListView(APIView):
    permission_classes = [IsParent]

    def get(self, request):
        child_id = request.query_params.get("child_id")
        event_type = request.query_params.get("event_type")
        date = request.query_params.get("date")

        events = ChildSavedLocationEvent.objects.filter(
            parent=request.user
        ).select_related(
            "child",
            "saved_location",
        ).order_by("-created_at")

        if child_id:
            events = events.filter(child_id=child_id)

        if event_type:
            events = events.filter(event_type=event_type)

        if date:
            parsed_date = parse_date(date)
            if parsed_date:
                events = events.filter(created_at__date=parsed_date)

        return paginate_queryset(
            request=request,
            queryset=events,
            serializer_class=ChildSavedLocationEventSerializer,
            page_size=20,
        )
        
        
class ParentChildAppAnalyticsView(APIView):
    permission_classes = [IsParentOfChild]

    @swagger_auto_schema(tags=["app-control"])
    def get(self, request, child_id):
        period = request.query_params.get("period", "week")
        date_from = request.query_params.get("date_from")
        date_to = request.query_params.get("date_to")

        today = timezone.localdate()

        if date_from:
            parsed_from = parse_date(date_from)
        else:
            parsed_from = today - timedelta(days=6)

        if date_to:
            parsed_to = parse_date(date_to)
        else:
            parsed_to = today

        if not parsed_from or not parsed_to:
            return Response(
                {
                    "status": False,
                    "detail": "date_from yoki date_to noto‘g‘ri formatda. Format: YYYY-MM-DD"
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        max_days = 90
        if (parsed_to - parsed_from).days > max_days:
            return Response(
                {
                    "status": False,
                    "detail": f"Maksimal oraliq {max_days} kun bo‘lishi mumkin."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        usages = ChildAppUsage.objects.filter(
            child_id=child_id,
            usage_date__gte=parsed_from,
            usage_date__lte=parsed_to,
        ).select_related("app")

        total_usage_seconds = usages.aggregate(
            total=Sum("total_usage_seconds")
        )["total"] or 0

        daily_rows = usages.values(
            "usage_date"
        ).annotate(
            total_usage_seconds=Sum("total_usage_seconds"),
            total_open_count=Sum("open_count"),
        ).order_by("usage_date")

        daily_stats = []

        current_date = parsed_from
        daily_map = {
            row["usage_date"]: row
            for row in daily_rows
        }

        while current_date <= parsed_to:
            row = daily_map.get(current_date)

            total_seconds = row["total_usage_seconds"] if row else 0
            open_count = row["total_open_count"] if row else 0

            daily_stats.append(
                {
                    "date": str(current_date),
                    "total_usage_seconds": total_seconds,
                    "total_usage_minutes": round(total_seconds / 60, 1),
                    "total_usage_hours": round(total_seconds / 3600, 2),
                    "open_count": open_count,
                }
            )

            current_date += timedelta(days=1)

        app_rows = usages.values(
            "app_id",
            "app__app_name",
            "app__package_name",
            "app__category",
        ).annotate(
            total_usage_seconds=Sum("total_usage_seconds"),
            total_open_count=Sum("open_count"),
        ).order_by("-total_usage_seconds")

        apps_stats = []

        for row in app_rows:
            app_total = row["total_usage_seconds"] or 0

            apps_stats.append(
                {
                    "app_id": row["app_id"],
                    "app_name": row["app__app_name"],
                    "package_name": row["app__package_name"],
                    "category": row["app__category"],
                    "total_usage_seconds": app_total,
                    "total_usage_minutes": round(app_total / 60, 1),
                    "total_usage_hours": round(app_total / 3600, 2),
                    "open_count": row["total_open_count"] or 0,
                    "percent": round((app_total / total_usage_seconds) * 100, 1) if total_usage_seconds else 0,
                }
            )

        most_used_app = apps_stats[0] if apps_stats else None

        return Response(
            {
                "status": True,
                "child_id": child_id,
                "period": period,
                "date_from": str(parsed_from),
                "date_to": str(parsed_to),
                "summary": {
                    "total_usage_seconds": total_usage_seconds,
                    "total_usage_minutes": round(total_usage_seconds / 60, 1),
                    "total_usage_hours": round(total_usage_seconds / 3600, 2),
                    "most_used_app": most_used_app,
                },
                "daily_stats": daily_stats,
                "apps_stats": apps_stats,
            },
            status=status.HTTP_200_OK
        )
        
        
class SubscriptionPlanListView(APIView):
    permission_classes = [AllowAny]

    @swagger_auto_schema(tags=["subscription"])
    def get(self, request):
        plans = get_paid_plans()

        return Response(
            {
                "status": True,
                "plans": SubscriptionPlanSerializer(plans, many=True).data,
            },
            status=status.HTTP_200_OK
        )


class MySubscriptionView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(tags=["subscription"])
    def get(self, request):
        active_subscription = sync_user_premium_status(request.user)
        paid_plans = get_paid_plans()

        should_choose_paid_plan = not request.user.has_active_premium()

        return Response(
            {
                "status": True,
                "is_premium": request.user.has_active_premium(),
                "premium_expires_at": request.user.premium_expires_at,
                "active_subscription": UserSubscriptionSerializer(active_subscription).data if active_subscription else None,
                "should_choose_paid_plan": should_choose_paid_plan,
                "message": "Free trial tugagan. Pullik tarifni tanlang." if should_choose_paid_plan else None,
                "tariffs": SubscriptionPlanSerializer(paid_plans, many=True).data if should_choose_paid_plan else [],
            },
            status=status.HTTP_200_OK
        )


class ActivateSubscriptionView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(request_body=ActivateSubscriptionSerializer, tags=["subscription"])
    def post(self, request):
        serializer = ActivateSubscriptionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        plan = SubscriptionPlan.objects.filter(
            id=serializer.validated_data["plan_id"],
            is_active=True,
            is_trial=False,
        ).first()

        if not plan:
            return Response(
                {
                    "status": False,
                    "detail": "Pullik tarif topilmadi."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        subscription = activate_paid_subscription(
            user=request.user,
            plan=plan,
            source=UserSubscription.SOURCE_PAYMENT,
        )

        payment = SubscriptionPayment.objects.create(
            user=request.user,
            plan=plan,
            subscription=subscription,
            amount=plan.price,
            currency=plan.currency,
            provider="manual_test",
            status=SubscriptionPayment.STATUS_PAID,
            paid_at=timezone.now(),
            raw_payload={
                "source": "manual_test_activate_endpoint"
            },
        )

        return Response(
            {
                "status": True,
                "detail": "Subscription aktiv qilindi.",
                "subscription": UserSubscriptionSerializer(subscription).data,
                "payment": SubscriptionPaymentSerializer(payment).data,
                "user": UserSerializer(request.user).data,
            },
            status=status.HTTP_201_CREATED
        )


class AdminGiveSubscriptionView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(request_body=AdminGiveSubscriptionSerializer, tags=["subscription"])
    def post(self, request):
        if not request.user.is_superuser:
            return Response(
                {
                    "status": False,
                    "detail": "Faqat superuser subscription bera oladi."
                },
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = AdminGiveSubscriptionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user_id = serializer.validated_data.get("user_id")
        phone = serializer.validated_data.get("phone")
        days = serializer.validated_data["days"]

        target_user = None

        if user_id:
            target_user = User.objects.filter(id=user_id).first()

        if not target_user and phone:
            target_user = User.objects.filter(phone=phone).first()

        if not target_user:
            return Response(
                {
                    "status": False,
                    "detail": "User topilmadi."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        now = timezone.now()
        active_subscription = sync_user_premium_status(target_user)
        start_date = active_subscription.expires_at if active_subscription else now
        expires_at = start_date + timedelta(days=days)

        subscription = UserSubscription.objects.create(
            user=target_user,
            plan=None,
            status=UserSubscription.STATUS_ACTIVE,
            source=UserSubscription.SOURCE_ADMIN,
            started_at=start_date,
            expires_at=expires_at,
            created_by=request.user,
        )

        target_user.is_premium = True
        target_user.premium_expires_at = expires_at
        target_user.save(update_fields=["is_premium", "premium_expires_at"])

        return Response(
            {
                "status": True,
                "detail": f"{days} kunlik premium berildi.",
                "subscription": UserSubscriptionSerializer(subscription).data,
                "user": UserSerializer(target_user).data,
            },
            status=status.HTTP_201_CREATED
        )


class CancelSubscriptionView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(tags=["subscription"])
    def post(self, request):
        subscription = UserSubscription.objects.filter(
            user=request.user,
            status__in=[
                UserSubscription.STATUS_TRIAL,
                UserSubscription.STATUS_ACTIVE,
            ],
            expires_at__gt=timezone.now(),
        ).order_by("-expires_at").first()

        if not subscription:
            return Response(
                {
                    "status": False,
                    "detail": "Aktiv subscription topilmadi."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        subscription.status = UserSubscription.STATUS_CANCELLED
        subscription.cancelled_at = timezone.now()
        subscription.save(update_fields=["status", "cancelled_at", "updated_at"])

        active_subscription = sync_user_premium_status(request.user)
        paid_plans = get_paid_plans()

        return Response(
            {
                "status": True,
                "detail": "Subscription bekor qilindi.",
                "is_premium": request.user.has_active_premium(),
                "active_subscription": UserSubscriptionSerializer(active_subscription).data if active_subscription else None,
                "should_choose_paid_plan": not request.user.has_active_premium(),
                "tariffs": SubscriptionPlanSerializer(paid_plans, many=True).data if not request.user.has_active_premium() else [],
                "user": UserSerializer(request.user).data,
            },
            status=status.HTTP_200_OK
        )


class BlogCategoryListView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(tags=["blog-video"])
    def get(self, request):
        categories = BlogCategory.objects.filter(
            is_active=True
        ).order_by("order", "id")

        return paginate_queryset(
            request=request,
            queryset=categories,
            serializer_class=BlogCategorySerializer,
            page_size=20,
        )


class BlogPostListView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(tags=["blog-video"])
    def get(self, request):
        post_type = request.query_params.get("type")
        category_id = request.query_params.get("category_id")
        saved = request.query_params.get("saved")
        featured = request.query_params.get("featured")
        search = request.query_params.get("q")

        posts = BlogPost.objects.filter(
            is_active=True
        ).select_related("category")

        if post_type in [BlogPost.TYPE_BLOG, BlogPost.TYPE_VIDEO]:
            posts = posts.filter(post_type=post_type)

        if category_id:
            posts = posts.filter(category_id=category_id)

        if featured == "true":
            posts = posts.filter(is_featured=True)

        if search:
            posts = posts.filter(
                Q(title__icontains=search)
                | Q(short_description__icontains=search)
                | Q(content__icontains=search)
            )

        if saved == "true":
            posts = posts.filter(saved_by_users__user=request.user)

        posts = posts.order_by("order", "-published_at", "-created_at")

        return paginate_queryset(
            request=request,
            queryset=posts,
            serializer_class=BlogPostListSerializer,
            context={"request": request},
            page_size=20,
        )


class BlogPostDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(tags=["blog-video"])
    def get(self, request, post_id):
        post = BlogPost.objects.filter(
            id=post_id,
            is_active=True,
        ).select_related("category").first()

        if not post:
            return Response(
                {
                    "status": False,
                    "detail": "Blog/video topilmadi."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        BlogPost.objects.filter(id=post.id).update(
            views_count=F("views_count") + 1
        )

        post.refresh_from_db()

        return Response(
            {
                "status": True,
                "post": BlogPostDetailSerializer(
                    post,
                    context={"request": request},
                ).data,
            },
            status=status.HTTP_200_OK
        )


class BlogPostSaveToggleView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(tags=["blog-video"])
    def post(self, request, post_id):
        post = BlogPost.objects.filter(
            id=post_id,
            is_active=True,
        ).first()

        if not post:
            return Response(
                {
                    "status": False,
                    "detail": "Blog/video topilmadi."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        saved = BlogPostSave.objects.filter(
            user=request.user,
            post=post,
        ).first()

        if saved:
            saved.delete()
            is_saved = False
            detail = "Saqlanganlardan olib tashlandi."
        else:
            BlogPostSave.objects.create(
                user=request.user,
                post=post,
            )
            is_saved = True
            detail = "Saqlanganlarga qo‘shildi."

        return Response(
            {
                "status": True,
                "detail": detail,
                "is_saved": is_saved,
            },
            status=status.HTTP_200_OK
        )


class BlogPostLikeToggleView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(tags=["blog-video"])
    def post(self, request, post_id):
        post = BlogPost.objects.filter(
            id=post_id,
            is_active=True,
        ).first()

        if not post:
            return Response(
                {
                    "status": False,
                    "detail": "Blog/video topilmadi."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        liked = BlogPostLike.objects.filter(
            user=request.user,
            post=post,
        ).first()

        if liked:
            liked.delete()
            BlogPost.objects.filter(id=post.id, likes_count__gt=0).update(
                likes_count=F("likes_count") - 1
            )
            is_liked = False
            detail = "Foydali belgisi olib tashlandi."
        else:
            BlogPostLike.objects.create(
                user=request.user,
                post=post,
            )
            BlogPost.objects.filter(id=post.id).update(
                likes_count=F("likes_count") + 1
            )
            is_liked = True
            detail = "Foydali deb belgilandi."

        post.refresh_from_db()

        return Response(
            {
                "status": True,
                "detail": detail,
                "is_liked": is_liked,
                "likes_count": post.likes_count,
            },
            status=status.HTTP_200_OK
        )

# ============================================================================
# Parent Store (Do‘kon) views
# ============================================================================


class ParentStoreCategoryListView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(tags=["parent-store"])
    def get(self, request):
        categories = ParentStoreCategory.objects.filter(
            is_active=True
        ).order_by("order", "id")

        return paginate_queryset(
            request=request,
            queryset=categories,
            serializer_class=ParentStoreCategorySerializer,
            page_size=50,
        )


class ParentStorePromoBannerListView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(tags=["parent-store"])
    def get(self, request):
        banners = ParentStorePromoBanner.objects.filter(
            is_active=True
        ).select_related("link_product").order_by("order", "id")

        return paginate_queryset(
            request=request,
            queryset=banners,
            serializer_class=ParentStorePromoBannerSerializer,
            page_size=20,
        )


class ParentStoreProductListView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(tags=["parent-store"])
    def get(self, request):
        product_type = request.query_params.get("type")
        category_id = request.query_params.get("category_id")
        featured = request.query_params.get("featured")
        deal = request.query_params.get("deal")
        search = request.query_params.get("q")

        products = ParentStoreProduct.objects.filter(
            is_active=True
        ).select_related("category").prefetch_related("images")

        if product_type:
            products = products.filter(category__product_type=product_type)

        if category_id:
            products = products.filter(category_id=category_id)

        if featured == "true":
            products = products.filter(is_featured=True)

        if deal == "true":
            products = products.filter(
                old_price__isnull=False,
                old_price__gt=F("price"),
            )

        if search:
            products = products.filter(
                Q(name__icontains=search)
                | Q(category_label__icontains=search)
                | Q(short_description__icontains=search)
            )

        products = products.order_by("order", "-created_at")

        return paginate_queryset(
            request=request,
            queryset=products,
            serializer_class=ParentStoreProductListSerializer,
            context={"request": request},
            page_size=30,
        )


class ParentStoreProductDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(tags=["parent-store"])
    def get(self, request, product_id):
        product = (
            ParentStoreProduct.objects
            .filter(id=product_id, is_active=True)
            .select_related("category")
            .prefetch_related("images")
            .first()
        )

        if not product:
            return Response(
                {"status": False, "detail": "Mahsulot topilmadi."},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(
            {
                "status": True,
                "product": ParentStoreProductDetailSerializer(
                    product, context={"request": request}
                ).data,
            },
            status=status.HTTP_200_OK,
        )


class ParentStoreSavedProductListView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(tags=["parent-store"])
    def get(self, request):
        saved = (
            ParentStoreSavedProduct.objects
            .filter(user=request.user, product__is_active=True)
            .select_related("product", "product__category")
            .prefetch_related("product__images")
        )

        return paginate_queryset(
            request=request,
            queryset=saved,
            serializer_class=ParentStoreSavedProductSerializer,
            context={"request": request},
            page_size=50,
        )


class ParentStoreSavedProductToggleView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(tags=["parent-store"])
    def post(self, request, product_id):
        product = ParentStoreProduct.objects.filter(
            id=product_id, is_active=True
        ).first()
        if not product:
            return Response(
                {"status": False, "detail": "Mahsulot topilmadi."},
                status=status.HTTP_404_NOT_FOUND,
            )

        existing = ParentStoreSavedProduct.objects.filter(
            user=request.user, product=product
        ).first()

        if existing:
            existing.delete()
            return Response(
                {
                    "status": True,
                    "is_saved": False,
                    "detail": "Saqlanganlardan olib tashlandi.",
                },
                status=status.HTTP_200_OK,
            )

        ParentStoreSavedProduct.objects.create(user=request.user, product=product)
        return Response(
            {
                "status": True,
                "is_saved": True,
                "detail": "Saqlanganlarga qo‘shildi.",
            },
            status=status.HTTP_200_OK,
        )


class ParentStoreOrderListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(tags=["parent-store"])
    def get(self, request):
        orders = (
            ParentStoreOrder.objects
            .filter(user=request.user)
            .select_related("product")
            .order_by("-created_at")
        )

        only = request.query_params.get("only")
        if only == "active":
            orders = orders.filter(status__in=ParentStoreOrder.ACTIVE_STATUSES)

        return paginate_queryset(
            request=request,
            queryset=orders,
            serializer_class=ParentStoreOrderSerializer,
            page_size=30,
        )

    @swagger_auto_schema(
        tags=["parent-store"],
        request_body=ParentStoreOrderCreateSerializer,
    )
    def post(self, request):
        serializer = ParentStoreOrderCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        product = ParentStoreProduct.objects.filter(
            id=serializer.validated_data["product_id"],
            is_active=True,
        ).first()

        if not product:
            return Response(
                {"status": False, "detail": "Mahsulot topilmadi."},
                status=status.HTTP_404_NOT_FOUND,
            )

        quantity = serializer.validated_data.get("quantity", 1)
        now = timezone.now()

        order = ParentStoreOrder(
            code=generate_parent_store_order_code(),
            user=request.user,
            product=product,
            quantity=quantity,
            unit_price=product.price,
            total_price=product.price * quantity,
            status=ParentStoreOrder.STATUS_SENT,
            sent_at=now,
            contact_phone=serializer.validated_data.get("contact_phone", ""),
            contact_name=serializer.validated_data.get("contact_name", ""),
            address=serializer.validated_data.get("address", ""),
            note=serializer.validated_data.get("note", ""),
        )
        order.save()

        return Response(
            {
                "status": True,
                "detail": "Buyurtma yuborildi.",
                "order": ParentStoreOrderSerializer(order).data,
            },
            status=status.HTTP_201_CREATED,
        )


class ParentStoreOrderDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(tags=["parent-store"])
    def get(self, request, order_id):
        order = (
            ParentStoreOrder.objects
            .filter(id=order_id, user=request.user)
            .select_related("product")
            .first()
        )
        if not order:
            return Response(
                {"status": False, "detail": "Buyurtma topilmadi."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(
            {"status": True, "order": ParentStoreOrderSerializer(order).data},
            status=status.HTTP_200_OK,
        )


class ParentStoreOrderCancelView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(tags=["parent-store"])
    def post(self, request, order_id):
        order = ParentStoreOrder.objects.filter(
            id=order_id, user=request.user
        ).first()

        if not order:
            return Response(
                {"status": False, "detail": "Buyurtma topilmadi."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if order.status in (
            ParentStoreOrder.STATUS_DELIVERED,
            ParentStoreOrder.STATUS_CANCELLED,
        ):
            return Response(
                {
                    "status": False,
                    "detail": "Bu buyurtmani bekor qilib bo‘lmaydi.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        order.stamp_status(ParentStoreOrder.STATUS_CANCELLED)
        order.save()

        return Response(
            {
                "status": True,
                "detail": "Buyurtma bekor qilindi.",
                "order": ParentStoreOrderSerializer(order).data,
            },
            status=status.HTTP_200_OK,
        )


# ============================================================================
# Tracking: Trajectory + Frequent place recommendations
# ============================================================================


class ChildDailyTrajectoryView(APIView):
    """Bola kun davomidagi marshruti — polyline + nuqtalar ro'yxati.

    Query params:
      - date (YYYY-MM-DD, default: bugun)
      - decimate: int (har N-nuqtani qoldirish, default: 1 — to'liq)

    Bola id orqali izlanadi, faqat o'sha bolaning ota-onasi ko'ra oladi.
    """

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(tags=["tracking"])
    def get(self, request, child_id):
        if request.user.role != User.ROLE_PARENT:
            return Response(
                {"status": False, "detail": "Faqat ota-onalar uchun."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if not ParentChild.objects.filter(
            parent=request.user, child_id=child_id
        ).exists():
            return Response(
                {"status": False, "detail": "Sizning farzandingiz emas."},
                status=status.HTTP_403_FORBIDDEN,
            )

        date_str = request.query_params.get("date")
        if date_str:
            day = parse_date(date_str)
            if not day:
                return Response(
                    {"status": False, "detail": "date YYYY-MM-DD formatida bo‘lsin."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            day = timezone.now().date()

        start = timezone.make_aware(
            timezone.datetime.combine(day, timezone.datetime.min.time())
        ) if timezone.is_naive(timezone.datetime.combine(day, timezone.datetime.min.time())) else timezone.datetime.combine(day, timezone.datetime.min.time())

        # Simpler: bound by created_at__date
        locations = (
            ChildLocation.objects
            .filter(child_id=child_id, created_at__date=day)
            .order_by("created_at")
            .values(
                "id", "latitude", "longitude", "accuracy",
                "speed", "heading", "battery_level", "signal_strength",
                "activity_type", "created_at", "captured_at",
            )
        )

        try:
            decimate = max(1, int(request.query_params.get("decimate") or 1))
        except ValueError:
            decimate = 1

        points = []
        for i, loc in enumerate(locations):
            if i % decimate != 0:
                continue
            points.append({
                "id": loc["id"],
                "lat": float(loc["latitude"]),
                "lng": float(loc["longitude"]),
                "acc": loc["accuracy"],
                "spd": loc["speed"],
                "hdg": loc["heading"],
                "bat": loc["battery_level"],
                "sig": loc["signal_strength"],
                "act": loc["activity_type"],
                "ts": (loc["captured_at"] or loc["created_at"]).isoformat(),
            })

        # Trajectory tafsiloti
        distance_meters = 0.0
        if len(points) >= 2:
            from .services import calculate_distance_meters
            for i in range(1, len(points)):
                a = points[i - 1]
                b = points[i]
                distance_meters += calculate_distance_meters(
                    a["lat"], a["lng"], b["lat"], b["lng"],
                )

        return Response(
            {
                "status": True,
                "date": day.isoformat(),
                "child_id": child_id,
                "points_count": len(points),
                "distance_meters": round(distance_meters, 2),
                "points": points,
            },
            status=status.HTTP_200_OK,
        )


class ChildFrequentPlacesView(APIView):
    """Bola uchun aniqlangan ko'p tashrif buyuradigan joylar (tavsiyalar)."""

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(tags=["tracking"])
    def get(self, request, child_id):
        if request.user.role != User.ROLE_PARENT:
            return Response(
                {"status": False, "detail": "Faqat ota-onalar uchun."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if not ParentChild.objects.filter(
            parent=request.user, child_id=child_id
        ).exists():
            return Response(
                {"status": False, "detail": "Sizning farzandingiz emas."},
                status=status.HTTP_403_FORBIDDEN,
            )

        only_recommendable = request.query_params.get("recommendable") == "true"
        min_visits = int(request.query_params.get("min_visits") or 0)

        places = ChildFrequentPlace.objects.filter(child_id=child_id)
        if only_recommendable:
            places = places.filter(
                is_recommendation_dismissed=False,
                saved_location__isnull=True,
                visit_count__gte=max(min_visits, 3),
            )
        elif min_visits:
            places = places.filter(visit_count__gte=min_visits)

        results = [
            {
                "id": p.id,
                "lat": float(p.latitude),
                "lng": float(p.longitude),
                "radius_meters": p.radius_meters,
                "visit_count": p.visit_count,
                "total_dwell_seconds": p.total_dwell_seconds,
                "label": p.label,
                "saved_location_id": p.saved_location_id,
                "is_recommendation_dismissed": p.is_recommendation_dismissed,
                "first_seen_at": p.first_seen_at.isoformat(),
                "last_seen_at": p.last_seen_at.isoformat(),
            }
            for p in places.order_by("-visit_count", "-last_seen_at")[:50]
        ]

        return Response(
            {"status": True, "results": results},
            status=status.HTTP_200_OK,
        )


class ChildFrequentPlaceSaveView(APIView):
    """Frequent place'ni SavedLocation'ga aylantirish."""

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(tags=["tracking"])
    def post(self, request, child_id, place_id):
        if request.user.role != User.ROLE_PARENT:
            return Response(
                {"status": False, "detail": "Faqat ota-onalar uchun."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if not ParentChild.objects.filter(
            parent=request.user, child_id=child_id
        ).exists():
            return Response(
                {"status": False, "detail": "Sizning farzandingiz emas."},
                status=status.HTTP_403_FORBIDDEN,
            )

        place = ChildFrequentPlace.objects.filter(
            id=place_id, child_id=child_id,
        ).first()
        if not place:
            return Response(
                {"status": False, "detail": "Joy topilmadi."},
                status=status.HTTP_404_NOT_FOUND,
            )

        name = request.data.get("name") or "Yangi joy"
        location_type = request.data.get("location_type") or SavedLocation.LOCATION_OTHER
        radius_meters = int(
            request.data.get("radius_meters") or place.radius_meters or 120
        )

        saved = SavedLocation.objects.create(
            parent=request.user,
            name=name[:150],
            location_type=location_type,
            latitude=place.latitude,
            longitude=place.longitude,
            radius_meters=radius_meters,
            is_active=True,
        )

        place.saved_location = saved
        place.save(update_fields=["saved_location"])

        return Response(
            {
                "status": True,
                "saved_location_id": saved.id,
                "detail": "Joy saqlanganlarga qo‘shildi.",
            },
            status=status.HTTP_201_CREATED,
        )


class ChildFrequentPlaceDismissView(APIView):
    """Tavsiyani rad etish — qayta ko'rsatilmaydi."""

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(tags=["tracking"])
    def post(self, request, child_id, place_id):
        if not ParentChild.objects.filter(
            parent=request.user, child_id=child_id
        ).exists():
            return Response(
                {"status": False, "detail": "Sizning farzandingiz emas."},
                status=status.HTTP_403_FORBIDDEN,
            )

        place = ChildFrequentPlace.objects.filter(
            id=place_id, child_id=child_id,
        ).first()
        if not place:
            return Response(
                {"status": False, "detail": "Joy topilmadi."},
                status=status.HTTP_404_NOT_FOUND,
            )

        place.is_recommendation_dismissed = True
        place.save(update_fields=["is_recommendation_dismissed"])

        return Response(
            {"status": True, "detail": "Tavsiya rad etildi."},
            status=status.HTTP_200_OK,
        )


class ChildDestinationPredictionListView(APIView):
    """Oxirgi destination prediction-larni qaytaradi (debug/audit uchun)."""

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(tags=["tracking"])
    def get(self, request, child_id):
        if not ParentChild.objects.filter(
            parent=request.user, child_id=child_id
        ).exists():
            return Response(
                {"status": False, "detail": "Sizning farzandingiz emas."},
                status=status.HTTP_403_FORBIDDEN,
            )

        preds = ChildDestinationPrediction.objects.filter(
            child_id=child_id,
        ).select_related("saved_location").order_by("-created_at")[:50]

        results = [
            {
                "id": p.id,
                "saved_location_id": p.saved_location_id,
                "saved_location_name": p.saved_location.name if p.saved_location else "",
                "event_type": p.event_type,
                "distance_meters": p.distance_meters,
                "speed_kmh": p.speed_kmh,
                "eta_seconds": p.eta_seconds,
                "title": p.title,
                "body": p.body,
                "created_at": p.created_at.isoformat(),
            }
            for p in preds
        ]
        return Response(
            {"status": True, "results": results},
            status=status.HTTP_200_OK,
        )


# ============================================================================
# Parent notification inbox endpoints
# ============================================================================


class ParentNotificationListView(APIView):
    """GET /parent/notifications/

    Filtrlar:
      - category=...        — bitta yoki vergul bilan ajratilgan ro'yxat
      - only=unread         — faqat o'qilmaganlarni
      - since=<iso>         — vaqtdan keyin yaratilganlar
    """

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(tags=["parent-notifications"])
    def get(self, request):
        qs = ParentNotification.objects.filter(parent=request.user)

        categories = request.query_params.get("category")
        if categories:
            qs = qs.filter(category__in=[c.strip() for c in categories.split(",") if c.strip()])

        if request.query_params.get("only") == "unread":
            qs = qs.filter(is_read=False)

        since = request.query_params.get("since")
        if since:
            from django.utils.dateparse import parse_datetime as _pd
            parsed = _pd(since)
            if parsed:
                qs = qs.filter(created_at__gt=parsed)

        qs = qs.order_by("-created_at")

        return paginate_queryset(
            request=request,
            queryset=qs,
            serializer_class=ParentNotificationSerializer,
            page_size=50,
        )


class ParentNotificationUnreadCountView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(tags=["parent-notifications"])
    def get(self, request):
        count = ParentNotification.objects.filter(
            parent=request.user, is_read=False
        ).count()
        return Response({"status": True, "unread_count": count}, status=status.HTTP_200_OK)


class ParentNotificationMarkReadView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(tags=["parent-notifications"])
    def post(self, request, notification_id):
        notification = ParentNotification.objects.filter(
            id=notification_id, parent=request.user
        ).first()
        if not notification:
            return Response(
                {"status": False, "detail": "Topilmadi."},
                status=status.HTTP_404_NOT_FOUND,
            )
        notification.mark_read()
        return Response(
            {
                "status": True,
                "notification": ParentNotificationSerializer(notification).data,
            },
            status=status.HTTP_200_OK,
        )


class ParentNotificationMarkAllReadView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(tags=["parent-notifications"])
    def post(self, request):
        now = timezone.now()
        updated = ParentNotification.objects.filter(
            parent=request.user, is_read=False
        ).update(is_read=True, read_at=now)
        return Response(
            {"status": True, "updated": updated},
            status=status.HTTP_200_OK,
        )


class ChildJourneyView(APIView):
    """Bola kun davomidagi yo'l xulosasi — Findmykids uslubidagi timeline."""

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(tags=["tracking"])
    def get(self, request, child_id):
        if request.user.role != User.ROLE_PARENT:
            return Response(
                {"status": False, "detail": "Faqat ota-onalar uchun."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if not ParentChild.objects.filter(
            parent=request.user, child_id=child_id
        ).exists():
            return Response(
                {"status": False, "detail": "Sizning farzandingiz emas."},
                status=status.HTTP_403_FORBIDDEN,
            )

        child = User.objects.filter(id=child_id).first()
        if not child:
            return Response(
                {"status": False, "detail": "Bola topilmadi."},
                status=status.HTTP_404_NOT_FOUND,
            )

        date_str = request.query_params.get("date")
        if date_str:
            target = parse_date(date_str)
            if not target:
                return Response(
                    {"status": False, "detail": "date YYYY-MM-DD bo‘lsin."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            target = timezone.localdate()

        from .services import compute_child_journey
        journey = compute_child_journey(child=child, target_date=target)

        # Bugungi step count'ni qo'shamiz — ChildDailyActivity'dan
        activity = ChildDailyActivity.objects.filter(
            child=child, activity_date=target,
        ).first()
        journey["summary"]["steps_count"] = (
            activity.steps_count if activity else 0
        )

        return Response(
            {"status": True, **journey},
            status=status.HTTP_200_OK,
        )
