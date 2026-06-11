"""
Admin paneli CRUD API'lari — react admin (jojo_admin) shu yerga ulanadi.

Endpoint'lar `/api/admin/` ostida joylashgan. Auth: JWT + foydalanuvchi
`is_staff=True` bo'lishi shart.
"""

import os
import uuid
from rest_framework import serializers as drf_serializers
from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth import get_user_model
from django.core.files.storage import default_storage
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.permissions import IsAuthenticated, BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .models import (
    BlogCategory,
    BlogPost,
    CallCenterComment,
    CallCenterTicket,
    GameCategory,
    GameItem,
    NotificationRule,
    NotificationRuleLog,
    ParentStoreCategory,
    ParentStoreOrder,
    ParentStoreProduct,
    ParentStoreProductImage,
    ParentStorePromoBanner,
    ParentNotification,
    SOSAlert,
    SubscriptionPayment,
    SubscriptionPlan,
    SupportQuickReply,
)
from .realtime import broadcast_lead_changed, broadcast_lead_comment
from .serializers import (
    ParentNotificationSerializer,
    ParentStoreOrderSerializer,
    SubscriptionPaymentSerializer,
    SubscriptionPlanSerializer,
)
from .admin_serializers import (
    AdminBannerSerializer as ParentStorePromoBannerSerializer,
    AdminBlogCategorySerializer as BlogCategorySerializer,
    AdminBlogPostSerializer as BlogPostSerializer,
    AdminStoreCategorySerializer as ParentStoreCategorySerializer,
    AdminStoreProductSerializer as ParentStoreProductSerializer,
)

User = get_user_model()


class IsAdminUser(BasePermission):
    """Faqat `is_staff=True` foydalanuvchilarga ruxsat."""

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_staff)


# ============================================================================
# Auth
# ============================================================================


class AdminLoginView(APIView):
    """Phone + password bilan login. Foydalanuvchi `is_staff` bo'lishi kerak.
    Muvaffaqiyatli bo'lsa JWT (access + refresh) qaytaradi."""

    authentication_classes = []
    permission_classes = []

    def post(self, request):
        phone = (request.data.get("phone") or request.data.get("username") or "").strip()
        password = request.data.get("password") or ""
        if not phone or not password:
            return Response(
                {"detail": "phone va password majburiy"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user = None
        # Phone yoki username orqali qidiramiz.
        candidate = User.objects.filter(phone=phone).first() or \
            User.objects.filter(username=phone).first()
        if candidate and candidate.check_password(password):
            user = candidate
        if not user:
            return Response(
                {"detail": "Login yoki parol noto'g'ri"},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        if not user.is_staff:
            return Response(
                {"detail": "Ruxsat yo'q (admin emas)"},
                status=status.HTTP_403_FORBIDDEN,
            )
        refresh = RefreshToken.for_user(user)
        return Response({
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "user": {
                "id": user.id,
                "phone": getattr(user, "phone", None),
                "username": user.username,
                "full_name": user.first_name or "",
                "is_superuser": user.is_superuser,
            },
        })


class AdminMeView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        user = request.user
        return Response({
            "id": user.id,
            "phone": getattr(user, "phone", None),
            "username": user.username,
            "full_name": user.first_name or "",
            "is_superuser": user.is_superuser,
        })


# ============================================================================
# Promo Banners — list / create / update / delete
# ============================================================================


class AdminBannerListCreate(generics.ListCreateAPIView):
    queryset = ParentStorePromoBanner.objects.all().order_by("order", "id")
    serializer_class = ParentStorePromoBannerSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]


class AdminBannerDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = ParentStorePromoBanner.objects.all()
    serializer_class = ParentStorePromoBannerSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]


# ============================================================================
# Parent-store categories
# ============================================================================


class AdminStoreCategoryListCreate(generics.ListCreateAPIView):
    queryset = ParentStoreCategory.objects.all().order_by("order", "id")
    serializer_class = ParentStoreCategorySerializer
    permission_classes = [IsAuthenticated, IsAdminUser]


class AdminStoreCategoryDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = ParentStoreCategory.objects.all()
    serializer_class = ParentStoreCategorySerializer
    permission_classes = [IsAuthenticated, IsAdminUser]


# ============================================================================
# Parent-store products
# ============================================================================


class AdminStoreProductListCreate(generics.ListCreateAPIView):
    queryset = ParentStoreProduct.objects.all().order_by("-created_at")
    serializer_class = ParentStoreProductSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get_queryset(self):
        qs = super().get_queryset()
        cat = self.request.query_params.get("category_id")
        if cat:
            qs = qs.filter(category_id=cat)
        q = self.request.query_params.get("q")
        if q:
            qs = qs.filter(name__icontains=q)
        return qs


class AdminStoreProductDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = ParentStoreProduct.objects.all()
    serializer_class = ParentStoreProductSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]


# ============================================================================
# Blog (advice) categories
# ============================================================================


class AdminBlogCategoryListCreate(generics.ListCreateAPIView):
    queryset = BlogCategory.objects.all().order_by("order", "id")
    serializer_class = BlogCategorySerializer
    permission_classes = [IsAuthenticated, IsAdminUser]


class AdminBlogCategoryDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = BlogCategory.objects.all()
    serializer_class = BlogCategorySerializer
    permission_classes = [IsAuthenticated, IsAdminUser]


# ============================================================================
# Blog posts (Maslahatlar)
# ============================================================================


class AdminBlogPostListCreate(generics.ListCreateAPIView):
    queryset = BlogPost.objects.all().select_related("category").order_by("-created_at")
    serializer_class = BlogPostSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get_queryset(self):
        qs = super().get_queryset()
        cat = self.request.query_params.get("category_id")
        if cat:
            qs = qs.filter(category_id=cat)
        q = self.request.query_params.get("q")
        if q:
            qs = qs.filter(title__icontains=q)
        return qs


class AdminBlogPostDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = BlogPost.objects.all()
    serializer_class = BlogPostSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]


# ============================================================================
# Users management (list, suspend)
# ============================================================================


class AdminUserListView(generics.ListAPIView):
    serializer_class = drf_serializers.Serializer
    permission_classes = [IsAuthenticated, IsAdminUser]

    def list(self, request, *args, **kwargs):
        qs = User.objects.all().order_by("-date_joined")
        role = request.query_params.get("role")
        if role:
            qs = qs.filter(role=role)
        q = request.query_params.get("q")
        if q:
            qs = qs.filter(phone__icontains=q) | qs.filter(username__icontains=q) | qs.filter(first_name__icontains=q)
        is_active = request.query_params.get("is_active")
        if is_active in ("true", "false"):
            qs = qs.filter(is_active=(is_active == "true"))
        page_size = int(request.query_params.get("page_size", 30))
        offset = int(request.query_params.get("offset", 0))
        total = qs.count()
        # last_login va device count'ni ham qaytaramiz — UI'da "Oxirgi faollik"
        # va "Qurilma" ustunlari ko'rinishi uchun.
        from .models import DeviceToken
        from django.db.models import Count
        page = list(qs[offset:offset + page_size].values(
            "id", "phone", "username", "first_name", "last_name", "full_name",
            "role", "is_active", "is_staff", "date_joined", "last_login",
            "age", "gender", "language", "child_status", "is_premium",
        ))
        ids = [u["id"] for u in page]
        # 1 query'da hamma user uchun device sonini olamiz
        device_counts = dict(
            DeviceToken.objects.filter(user_id__in=ids, is_active=True)
            .values_list("user_id")
            .annotate(c=Count("id"))
            .values_list("user_id", "c")
        )
        last_devices = {}
        for d in DeviceToken.objects.filter(user_id__in=ids).order_by("-id"):
            last_devices.setdefault(d.user_id, {
                "type": getattr(d, "device_type", None) or "android",
                "id": getattr(d, "device_id", None) or "",
            })
        items = []
        for u in page:
            u["device_count"] = device_counts.get(u["id"], 0)
            u["last_device"] = last_devices.get(u["id"])
            items.append(u)
        return Response({"count": total, "results": items, "offset": offset, "page_size": page_size})


class AdminUserToggleActiveView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def post(self, request, user_id):
        user = User.objects.filter(id=user_id).first()
        if not user:
            return Response({"detail": "Topilmadi"}, status=404)
        user.is_active = not user.is_active
        user.save(update_fields=["is_active"])
        return Response({"id": user.id, "is_active": user.is_active})


# ============================================================================
# SOS alerts — read-only list
# ============================================================================


class AdminSOSAlertListView(generics.ListAPIView):
    serializer_class = drf_serializers.Serializer
    permission_classes = [IsAuthenticated, IsAdminUser]

    def list(self, request, *args, **kwargs):
        qs = SOSAlert.objects.all().select_related("child", "parent").order_by("-created_at")
        page_size = int(request.query_params.get("page_size", 30))
        offset = int(request.query_params.get("offset", 0))
        total = qs.count()
        items = []
        for s in qs[offset:offset + page_size]:
            items.append({
                "id": s.id,
                "child": {"id": s.child_id, "name": s.child.full_name or s.child.first_name or s.child.phone},
                "parent": {"id": s.parent_id, "name": s.parent.full_name or s.parent.first_name or s.parent.phone},
                "latitude": float(s.latitude) if s.latitude else None,
                "longitude": float(s.longitude) if s.longitude else None,
                "address": s.address,
                "status": s.status,
                "created_at": s.created_at.isoformat(),
            })
        return Response({"count": total, "results": items, "offset": offset, "page_size": page_size})


# ============================================================================
# Notifications broadcast — send to all parents
# ============================================================================


class AdminBroadcastNotificationView(APIView):
    """Parentlarga bildirishnoma yuborish (audience bo'yicha filtrlash bilan).

    POST body:
      title, body            — uz (asosiy) matn — majburiy
      title_ru, body_ru      — ru tarjima (ixtiyoriy)
      title_en, body_en      — en tarjima (ixtiyoriy)
      category               — ParentNotification.category (default: "system")
      send_sms               — true bo'lsa SMSFLY orqali ham yuboriladi
      audience               — kimga jo'natilsin (default: "active"):
                                 "all"         — hamma parentlar (faol va nofaol)
                                 "active"      — faqat is_active=True
                                 "inactive"    — faqat is_active=False
                                 "premium"     — faol premium (muddati o'tmagan)
                                 "non_premium" — premium bo'lmagan faol parentlar
                                 "selected"    — `parent_ids` ro'yxatidagilar
      parent_ids             — int ro'yxati (audience="selected" uchun majburiy)
    """

    permission_classes = [IsAuthenticated, IsAdminUser]

    _AUDIENCE_CHOICES = {
        "all", "active", "inactive", "premium", "non_premium", "selected",
    }

    def post(self, request):
        from django.db.models import Q

        title = (request.data.get("title") or "").strip()
        body = (request.data.get("body") or "").strip()
        title_ru = (request.data.get("title_ru") or "").strip()
        title_en = (request.data.get("title_en") or "").strip()
        body_ru = (request.data.get("body_ru") or "").strip()
        body_en = (request.data.get("body_en") or "").strip()
        category = request.data.get("category", "system")
        send_sms = bool(request.data.get("send_sms"))
        raw_ids = request.data.get("parent_ids") or []
        if not isinstance(raw_ids, (list, tuple)):
            return Response({"detail": "parent_ids ro'yxat bo'lishi kerak"}, status=400)
        try:
            parent_ids = [int(x) for x in raw_ids if x is not None and str(x).strip() != ""]
        except (TypeError, ValueError):
            return Response({"detail": "parent_ids noto'g'ri formatda"}, status=400)

        # Audience tanlash. Backward-compat:
        #   - parent_ids berilgan bo'lsa va audience yo'q bo'lsa => "selected".
        #   - aks holda default "active" (eski "all" semantikasi shu edi).
        audience = request.data.get("audience")
        if not audience:
            audience = "selected" if parent_ids else "active"
        audience = str(audience).strip().lower()
        if audience not in self._AUDIENCE_CHOICES:
            return Response(
                {"detail": f"audience noto'g'ri: {audience}"}, status=400,
            )

        if not title or not body:
            return Response({"detail": "title va body majburiy"}, status=400)

        from .services import record_parent_notification, pick_for_lang

        title_translations = {"uz": title}
        if title_ru:
            title_translations["ru"] = title_ru
        if title_en:
            title_translations["en"] = title_en
        body_translations = {"uz": body}
        if body_ru:
            body_translations["ru"] = body_ru
        if body_en:
            body_translations["en"] = body_en

        parents_qs = User.objects.filter(role=User.ROLE_PARENT)

        # has_active_premium = is_premium=True AND (premium_expires_at IS NULL OR > now)
        now = timezone.now()
        active_premium_q = Q(is_premium=True) & (
            Q(premium_expires_at__isnull=True) | Q(premium_expires_at__gt=now)
        )

        if audience == "selected":
            if not parent_ids:
                return Response(
                    {"detail": "selected uchun parent_ids majburiy"}, status=400,
                )
            # Tanlangan ro'yxatda hatto bloklangan/nofaollar ham bo'lishi mumkin
            # — admin aniq tanlagan, hurmat qilamiz.
            parents_qs = parents_qs.filter(id__in=parent_ids)
        elif audience == "active":
            parents_qs = parents_qs.filter(is_active=True)
        elif audience == "inactive":
            parents_qs = parents_qs.filter(is_active=False)
        elif audience == "premium":
            parents_qs = parents_qs.filter(is_active=True).filter(active_premium_q)
        elif audience == "non_premium":
            parents_qs = parents_qs.filter(is_active=True).exclude(active_premium_q)
        # audience == "all" => filtr qo'shmaymiz (faol + nofaol hammasi)

        targeted = audience == "selected"
        announcement_data = {
            "announcement": True,
            "audience": audience,
        }
        # Tanlanganlar uchun aniq sonni ham yozamiz — history filtrida foydali.
        if targeted:
            announcement_data["audience_count"] = parents_qs.count()

        created = 0
        # Parent tili bo'yicha SMSlarni guruhlash — har bir tilga o'z matnida yuborish.
        sms_by_lang = {"uz": [], "ru": [], "en": []}
        for parent in parents_qs.iterator():
            try:
                record_parent_notification(
                    parent=parent,
                    child=None,
                    category=category,
                    title=title,
                    body=body,
                    data=announcement_data,
                    title_translations=title_translations,
                    body_translations=body_translations,
                )
                created += 1
                if send_sms and parent.phone:
                    plang = (getattr(parent, "language", "uz") or "uz").lower()
                    if plang.startswith("ru"):
                        bucket = "ru"
                    elif plang.startswith("en"):
                        bucket = "en"
                    else:
                        bucket = "uz"
                    sms_by_lang[bucket].append(parent.phone)
            except Exception:
                continue

        # SMS yuborish — per-phone, har biri alohida loglanadi va SESSION_NOT_BOUND
        # bo'lsa avto-retry qilinadi. Sekinroq, lekin per-raqam ko'rinish bor.
        sms_sent = 0
        sms_failed = []
        if send_sms:
            from .sms_service import sms_client
            for lang_code, phones in sms_by_lang.items():
                if not phones:
                    continue
                lang_title = pick_for_lang(title_translations, lang_code, fallback=title)
                lang_body = pick_for_lang(body_translations, lang_code, fallback=body)
                sms_text = f"{lang_title}\n{lang_body}"[:500]
                result = sms_client.send_bulk_per_phone(phones, sms_text, kind="broadcast")
                sms_sent += len(result["sent"])
                sms_failed.extend(result["failed"])

        return Response({
            "status": True,
            "sent_to": created,
            "sms_sent": sms_sent,
            "sms_failed_count": len(sms_failed),
            # Birinchi 50 ta failed ni qaytaramiz — admin UI ko'rsata oladi,
            # full ro'yxat /admin/sms-log/ orqali olinadi.
            "sms_failed": sms_failed[:50],
            "audience": audience,
        })


# ============================================================================
# Stats / Dashboard
# ============================================================================


class AdminDashboardStatsView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        from datetime import timedelta
        from django.db.models import Sum
        now = timezone.now()
        month_ago = now - timedelta(days=30)
        prev_month_start = now - timedelta(days=60)

        total_parents = User.objects.filter(role=User.ROLE_PARENT).count()
        prev_parents = User.objects.filter(
            role=User.ROLE_PARENT, date_joined__lt=month_ago
        ).count() or 1
        total_children = User.objects.filter(role=User.ROLE_CHILD).count()
        connected_children = User.objects.filter(
            role=User.ROLE_CHILD, child_status=User.CHILD_STATUS_ACTIVE
        ).count()
        active_24h = User.objects.filter(last_login__gte=now - timedelta(days=1)).count()
        premium_users = User.objects.filter(
            role=User.ROLE_PARENT, is_premium=True
        ).count()
        blocked_users = User.objects.filter(
            role=User.ROLE_PARENT, is_active=False
        ).count()
        premium_revenue = SubscriptionPayment.objects.filter(
            status="paid"
        ).aggregate(s=Sum("amount"))["s"] or 0

        # Last 30d for delta
        new_this_month = User.objects.filter(
            role=User.ROLE_PARENT, date_joined__gte=month_ago
        ).count()
        new_prev_month = User.objects.filter(
            role=User.ROLE_PARENT,
            date_joined__gte=prev_month_start,
            date_joined__lt=month_ago,
        ).count() or 1
        parent_delta = round(((new_this_month - new_prev_month) / max(new_prev_month, 1)) * 100, 1)

        total_products = ParentStoreProduct.objects.filter(is_active=True).count()
        total_posts = BlogPost.objects.filter(is_active=True).count()
        total_banners = ParentStorePromoBanner.objects.filter(is_active=True).count()
        sos_count = SOSAlert.objects.count()

        # 7 kunlik foydalanuvchi ro'yxatdan o'tish grafigi
        from django.db.models import Count
        from django.db.models.functions import TruncDate
        last7 = now - timedelta(days=7)
        signups_by_day = (
            User.objects.filter(role=User.ROLE_PARENT, date_joined__gte=last7)
            .annotate(d=TruncDate("date_joined"))
            .values("d")
            .annotate(c=Count("id"))
            .order_by("d")
        )
        signups_map = {row["d"].isoformat(): row["c"] for row in signups_by_day}
        signups_chart = []
        for i in range(7, -1, -1):
            day = (now - timedelta(days=i)).date()
            signups_chart.append({
                "date": day.isoformat(),
                "count": signups_map.get(day.isoformat(), 0),
            })

        # 7 kunlik daromad
        revenue_by_day = (
            SubscriptionPayment.objects.filter(
                status="paid", created_at__gte=last7
            )
            .annotate(d=TruncDate("created_at"))
            .values("d")
            .annotate(s=Sum("amount"))
            .order_by("d")
        )
        revenue_map = {row["d"].isoformat(): int(row["s"] or 0) for row in revenue_by_day}
        revenue_chart = []
        for i in range(7, -1, -1):
            day = (now - timedelta(days=i)).date()
            revenue_chart.append({
                "date": day.isoformat(),
                "amount": revenue_map.get(day.isoformat(), 0),
            })

        return Response({
            "parents": total_parents,
            "parents_delta_pct": parent_delta,
            "children": total_children,
            "children_connected": connected_children,
            "active_24h": active_24h,
            "premium_users": premium_users,
            "premium_revenue": int(premium_revenue),
            "blocked_users": blocked_users,
            "products": total_products,
            "blog_posts": total_posts,
            "banners": total_banners,
            "sos_alerts": sos_count,
            "signups_7d": signups_chart,
            "revenue_7d": revenue_chart,
        })


# ============================================================================
# Orders (parent_store)
# ============================================================================


class AdminOrderListView(generics.ListAPIView):
    queryset = ParentStoreOrder.objects.select_related("product", "parent").order_by("-created_at")
    serializer_class = ParentStoreOrderSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get_queryset(self):
        qs = super().get_queryset()
        status_filter = self.request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs


class AdminOrderDetailView(generics.RetrieveUpdateAPIView):
    queryset = ParentStoreOrder.objects.all()
    serializer_class = ParentStoreOrderSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]


# ============================================================================
# Subscription plans (Premium)
# ============================================================================


class AdminSubscriptionPlanListCreate(generics.ListCreateAPIView):
    queryset = SubscriptionPlan.objects.all().order_by("order", "id")
    serializer_class = SubscriptionPlanSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]


class AdminSubscriptionPlanDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = SubscriptionPlan.objects.all()
    serializer_class = SubscriptionPlanSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]


# ============================================================================
# Subscription payments (Payments page)
# ============================================================================


class AdminSubscriptionPaymentListView(generics.ListAPIView):
    queryset = SubscriptionPayment.objects.select_related("user", "plan").order_by("-created_at")
    serializer_class = SubscriptionPaymentSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get_queryset(self):
        qs = super().get_queryset()
        s = self.request.query_params.get("status")
        if s:
            qs = qs.filter(status=s)
        return qs


# ============================================================================
# Notifications history (inbox)
# ============================================================================


class AdminNotificationListView(generics.ListAPIView):
    queryset = ParentNotification.objects.select_related("parent", "child").order_by("-created_at")
    serializer_class = ParentNotificationSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get_queryset(self):
        qs = super().get_queryset()
        cat = self.request.query_params.get("category")
        if cat:
            qs = qs.filter(category=cat)
        return qs


class AdminNotificationDetailView(APIView):
    """Bildirishnomani tahrirlash yoki o'chirish.

    PATCH /api/admin/notifications/<id>/ — title, body, category
    DELETE /api/admin/notifications/<id>/ — yozuvni butunlay o'chiradi.
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    def patch(self, request, notif_id):
        notif = ParentNotification.objects.filter(id=notif_id).first()
        if not notif:
            return Response({"detail": "Topilmadi"}, status=404)
        update_fields = []
        for f in ("title", "body", "category"):
            if f in request.data:
                setattr(notif, f, request.data.get(f) or "")
                update_fields.append(f)
        if update_fields:
            notif.save(update_fields=update_fields)
        return Response({
            "id": notif.id,
            "title": notif.title,
            "body": notif.body,
            "category": notif.category,
        })

    def delete(self, request, notif_id):
        notif = ParentNotification.objects.filter(id=notif_id).first()
        if not notif:
            return Response({"detail": "Topilmadi"}, status=404)
        notif.delete()
        return Response(status=204)


class AdminBroadcastHistoryView(APIView):
    """`AdminBroadcastNotificationView` har yuborganda hamma parentga bitta
    ParentNotification yozuvi yaratadi. Bir xil title+body+category+yaqin
    vaqtdagi yozuvlarni guruhlab "broadcast" tarixi sifatida qaytaramiz."""
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        from django.db.models import Count, Min, Max
        category = request.query_params.get("category")
        qs = ParentNotification.objects.all()
        if category:
            qs = qs.filter(category=category)
        rows = (
            qs.values("title", "body", "title_ru", "title_en", "body_ru", "body_en", "category")
            .annotate(
                count=Count("id"),
                first_sent=Min("created_at"),
                last_sent=Max("created_at"),
            )
            .order_by("-last_sent")[:100]
        )
        results = []
        for row in rows:
            # Audience metadatasini eng oxirgi yozuvdan o'qiymiz.
            last = (
                ParentNotification.objects.filter(
                    title=row["title"], body=row["body"], category=row["category"]
                )
                .order_by("-created_at")
                .values("data")
                .first()
            )
            data = (last or {}).get("data") or {}
            row["audience"] = data.get("audience") or "all"
            results.append(row)
        return Response({"results": results})


# ============================================================================
# Operators / Support tickets (Call center)
# ============================================================================


def _parent_brief(p, *, request=None):
    """Lead kartochkasi uchun parent ma'lumotlari."""
    if not p:
        return None
    avatar_url = None
    if p.avatar and hasattr(p.avatar, "url") and p.avatar.name:
        avatar_url = p.avatar.url
        if request and not avatar_url.startswith("http"):
            avatar_url = request.build_absolute_uri(avatar_url)

    # Bola ulanganmi — kamida bitta aktiv farzandi bormi
    from .models import ParentChild
    child_count = ParentChild.objects.filter(parent=p).count()
    child_connected = ParentChild.objects.filter(
        parent=p, child__child_status=User.CHILD_STATUS_ACTIVE
    ).exists()

    # Premium status
    premium_active = bool(p.is_premium and (
        p.premium_expires_at is None or p.premium_expires_at > timezone.now()
    ))
    premium_days_left = None
    if premium_active and p.premium_expires_at:
        delta = p.premium_expires_at - timezone.now()
        premium_days_left = max(0, delta.days)

    return {
        "id": p.id,
        "name": p.full_name or p.first_name or p.phone or "—",
        "phone": p.phone,
        "email": p.email or "",
        "gender": p.gender or "",
        "avatar": avatar_url,
        "child_count": child_count,
        "child_connected": child_connected,
        "premium_active": premium_active,
        "premium_expires_at": p.premium_expires_at.isoformat() if p.premium_expires_at else None,
        "premium_days_left": premium_days_left,
        "is_active": p.is_active,
        "registered_at": p.date_joined.isoformat() if p.date_joined else None,
        "last_activity": p.last_login.isoformat() if p.last_login else None,
        "language": p.language or "",
    }


def _lead_to_dict(t, *, request=None):
    op = t.operator

    # Suhbatdagi eng oxirgi va eng oxirgi USER xabarini bir ORM aylantirishda
    # olamiz — ticket kartochkasidagi "Hali xabar yo'q" matnini almashtirish
    # va "yangi javob keldi" jihatini tezkor aniqlash uchun.
    last_msg = t.comments.order_by("-created_at").first()
    last_user_msg = (
        t.comments.filter(direction=getattr(CallCenterComment, "DIRECTION_IN", "in"))
        .order_by("-created_at")
        .first()
        if hasattr(t, "comments") else None
    )

    return {
        "id": t.id,
        "title": t.title,
        "description": t.description or "",
        "status": t.status,
        "priority": t.priority,
        "parent": _parent_brief(t.parent, request=request),
        "operator": {
            "id": op.id,
            "name": op.full_name or op.first_name or op.phone or "—",
        } if op else None,
        "last_contact_at": t.last_contact_at.isoformat() if t.last_contact_at else None,
        "closed_at": t.closed_at.isoformat() if t.closed_at else None,
        "created_at": t.created_at.isoformat(),
        "updated_at": t.updated_at.isoformat(),
        "comments_count": t.comments.count(),
        "source": getattr(t, "source", "app"),
        "telegram": {
            "chat_id": t.telegram_chat_id,
            "username": t.telegram_username,
            "name": t.telegram_name,
        } if getattr(t, "telegram_chat_id", None) else None,
        # Bot bilan ishlovchi tikket holatlari — chat panel + kartochka uchun
        "language": getattr(t, "language", "") or "",
        "bot_state": getattr(t, "bot_state", "") or "",
        # Foydalanuvchining oxirgi baholash natijasi (resolved bo'lsa)
        "rating": getattr(t, "rating", None),
        "rating_comment": getattr(t, "rating_comment", "") or "",
        "rated_at": t.rated_at.isoformat() if getattr(t, "rated_at", None) else None,
        # Kartochka ko'rinishi uchun: oxirgi xabar matni va sanasi.
        # Frontend TS interface kalit nomi `at` (created_at o'rniga).
        "last_message": {
            "text": (last_msg.comment or "")[:200],
            "direction": getattr(last_msg, "direction", "out"),
            "is_operator": bool(last_msg.operator_id),
            "at": last_msg.created_at.isoformat(),
        } if last_msg else None,
        "last_user_message_at": last_user_msg.created_at.isoformat()
            if last_user_msg else None,
    }


def _comment_to_dict(c, *, request=None):
    op = c.operator
    attachment_url = None
    att = getattr(c, "attachment", None)
    if att and getattr(att, "name", ""):
        try:
            url = att.url
            attachment_url = (
                request.build_absolute_uri(url)
                if request and not url.startswith("http")
                else url
            )
        except Exception:
            attachment_url = None
    return {
        "id": c.id,
        "ticket_id": c.ticket_id,
        "text": c.comment,
        "direction": getattr(c, "direction", "out"),
        "is_operator": bool(op),
        "old_status": c.old_status or "",
        "new_status": c.new_status or "",
        "attachment_url": attachment_url,
        "attachment_kind": getattr(c, "attachment_kind", "") or "",
        "attachment_name": getattr(c, "attachment_name", "") or "",
        "operator": {
            "id": op.id,
            "name": op.full_name or op.first_name or op.phone or "—",
        } if op else None,
        "created_at": c.created_at.isoformat(),
    }


class AdminTicketListView(APIView):
    """Eski endpoint — paginated flat list (Requests sahifasi ishlatadi)."""
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        qs = CallCenterTicket.objects.all().select_related(
            "parent", "operator"
        ).prefetch_related("comments").order_by("-updated_at")
        s = request.query_params.get("status")
        if s:
            qs = qs.filter(status=s)
        q = request.query_params.get("q")
        if q:
            from django.db.models import Q
            qs = qs.filter(
                Q(title__icontains=q)
                | Q(description__icontains=q)
                | Q(parent__phone__icontains=q)
                | Q(parent__first_name__icontains=q)
                | Q(parent__full_name__icontains=q)
            )
        page_size = int(request.query_params.get("page_size", 30))
        offset = int(request.query_params.get("offset", 0))
        items = [_lead_to_dict(t, request=request) for t in qs[offset:offset + page_size]]
        return Response({
            "count": qs.count(),
            "results": items,
            "offset": offset,
            "page_size": page_size,
        })


class AdminTicketUpdateStatusView(APIView):
    """Faqat statusni yangilaydi (Requests sahifasi tezda status o'zgartirish uchun)."""
    permission_classes = [IsAuthenticated, IsAdminUser]

    def post(self, request, ticket_id):
        ticket = CallCenterTicket.objects.filter(id=ticket_id).select_related("parent", "operator").first()
        if not ticket:
            return Response({"detail": "Topilmadi"}, status=404)
        new_status = request.data.get("status")
        if new_status and new_status in dict(CallCenterTicket.STATUS_CHOICES):
            old = ticket.status
            ticket.status = new_status
            ticket.save(update_fields=["status", "updated_at"])
            try:
                broadcast_lead_changed({
                    "type": "status_changed",
                    "id": ticket.id,
                    "from": old,
                    "to": new_status,
                    "lead": _lead_to_dict(ticket),
                })
            except Exception:
                pass
        return Response({"id": ticket.id, "status": ticket.status})


# ============================================================================
# Leads (kanban board) — call-center operatorlari uchun real-time CRM
# ============================================================================


class AdminLeadBoardView(APIView):
    """Lead'larni status bo'yicha guruhlangan tarzda qaytaradi.
    Frontend kanban kolonkalari uchun ideal shakl."""
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        statuses = [s[0] for s in CallCenterTicket.STATUS_CHOICES]
        qs = CallCenterTicket.objects.all().select_related(
            "parent", "operator"
        ).prefetch_related("comments").order_by("-updated_at")

        # Lead-CRM va Sorovlar (telegram support) ikki alohida ish oqimi.
        # `?source=telegram` → Sorovlar (bot orqali); `?source=app,manual`
        # yoki shunga o'xshash CSV → faqat parent app-dan / qo'lda
        # kiritilgan murojaatlar. Aniq berilmasa hammasi qaytariladi
        # (eski API mosligi uchun).
        source = request.query_params.get("source")
        if source:
            wanted = [s.strip() for s in source.split(",") if s.strip()]
            if wanted:
                qs = qs.filter(source__in=wanted)

        q = request.query_params.get("q")
        if q:
            from django.db.models import Q
            qs = qs.filter(
                Q(title__icontains=q)
                | Q(description__icontains=q)
                | Q(parent__phone__icontains=q)
                | Q(parent__first_name__icontains=q)
                | Q(parent__full_name__icontains=q)
                | Q(telegram_username__icontains=q)
                | Q(telegram_name__icontains=q)
            )

        # Operator filtersi — faqat shu operatorga biriktirilganlar
        op_id = request.query_params.get("operator_id")
        if op_id:
            qs = qs.filter(operator_id=op_id)

        # Har kolonkada qancha ko'rsatish — default 50.
        per_column = int(request.query_params.get("per_column", 50))

        columns = {}
        counts = {}
        for st in statuses:
            sub = qs.filter(status=st)
            counts[st] = sub.count()
            columns[st] = [_lead_to_dict(t, request=request) for t in sub[:per_column]]

        return Response({
            "statuses": statuses,
            "counts": counts,
            "columns": columns,
        })


class AdminLeadListCreate(APIView):
    """Yangi lead yaratish — qo'lda kiritilgan murojaatlar uchun."""
    permission_classes = [IsAuthenticated, IsAdminUser]

    def post(self, request):
        parent_id = request.data.get("parent_id")
        title = (request.data.get("title") or "").strip() or "Foydalanuvchi murojaati"
        description = request.data.get("description") or ""
        priority = request.data.get("priority") or "normal"
        status_val = request.data.get("status") or CallCenterTicket.STATUS_NEW
        if status_val not in dict(CallCenterTicket.STATUS_CHOICES):
            status_val = CallCenterTicket.STATUS_NEW
        if not parent_id:
            return Response({"detail": "parent_id majburiy"}, status=status.HTTP_400_BAD_REQUEST)
        parent_user = User.objects.filter(id=parent_id, role="parent").first()
        if not parent_user:
            return Response({"detail": "Foydalanuvchi topilmadi"}, status=status.HTTP_404_NOT_FOUND)
        ticket = CallCenterTicket.objects.create(
            parent=parent_user,
            operator=request.user if request.user.is_staff else None,
            title=title,
            description=description,
            priority=priority,
            status=status_val,
        )
        data = _lead_to_dict(ticket, request=request)
        try:
            broadcast_lead_changed({"type": "created", "id": ticket.id, "lead": data})
        except Exception:
            pass
        return Response(data, status=status.HTTP_201_CREATED)


class AdminLeadDetailView(APIView):
    """Bitta lead'ni o'qish, yangilash yoki o'chirish."""
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request, ticket_id):
        t = CallCenterTicket.objects.filter(id=ticket_id).select_related("parent", "operator").first()
        if not t:
            return Response({"detail": "Topilmadi"}, status=404)
        return Response(_lead_to_dict(t, request=request))

    def patch(self, request, ticket_id):
        t = CallCenterTicket.objects.filter(id=ticket_id).select_related("parent", "operator").first()
        if not t:
            return Response({"detail": "Topilmadi"}, status=404)
        old_status = t.status
        update_fields = []
        for f in ("title", "description", "priority"):
            if f in request.data:
                setattr(t, f, request.data.get(f) or "")
                update_fields.append(f)
        rating_requested = False
        if "status" in request.data:
            s = request.data["status"]
            if s in dict(CallCenterTicket.STATUS_CHOICES):
                t.status = s
                update_fields.append("status")
                if s == CallCenterTicket.STATUS_CLOSED and not t.closed_at:
                    t.closed_at = timezone.now()
                    update_fields.append("closed_at")
                # Telegram orqali kelgan murojaat operator tomonidan
                # `resolved` deb belgilanganda bot foydalanuvchidan
                # baho so'raydi. Status `closed` qachon `awaiting_rating`
                # tugagandan keyin qo'yiladi (callback handler).
                if (
                    s == CallCenterTicket.STATUS_RESOLVED
                    and old_status != CallCenterTicket.STATUS_RESOLVED
                    and getattr(t, "source", "") == CallCenterTicket.SOURCE_TELEGRAM
                    and t.telegram_chat_id
                ):
                    if t.resolved_at is None:
                        t.resolved_at = timezone.now()
                        update_fields.append("resolved_at")
                    rating_requested = True
        if "operator_id" in request.data:
            op_id = request.data["operator_id"]
            if op_id:
                op = User.objects.filter(id=op_id, is_staff=True).first()
                t.operator = op
            else:
                t.operator = None
            update_fields.append("operator")
        if update_fields:
            update_fields.append("updated_at")
            t.save(update_fields=update_fields)
        if rating_requested:
            try:
                from .telegram_bot import request_rating
                request_rating(t)
            except Exception:
                import logging
                logging.getLogger(__name__).exception("request_rating failed")
        data = _lead_to_dict(t, request=request)
        try:
            broadcast_lead_changed({
                "type": "updated",
                "id": t.id,
                "from": old_status,
                "to": t.status,
                "lead": data,
            })
        except Exception:
            pass
        return Response(data)

    def delete(self, request, ticket_id):
        t = CallCenterTicket.objects.filter(id=ticket_id).first()
        if not t:
            return Response({"detail": "Topilmadi"}, status=404)
        tid = t.id
        t.delete()
        try:
            broadcast_lead_changed({"type": "deleted", "id": tid})
        except Exception:
            pass
        return Response(status=204)


class AdminLeadFullView(APIView):
    """Lead + parent + children + payments + activity — detail panel uchun."""
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request, ticket_id):
        from .models import ParentChild
        t = CallCenterTicket.objects.filter(id=ticket_id).select_related("parent", "operator").first()
        if not t:
            return Response({"detail": "Topilmadi"}, status=404)
        lead = _lead_to_dict(t, request=request)
        parent = t.parent

        # Bolalar
        children = []
        if parent:
            links = ParentChild.objects.filter(parent=parent).select_related("child")
            for link in links:
                c = link.child
                if not c:
                    continue
                avatar = None
                if c.avatar and hasattr(c.avatar, "url") and c.avatar.name:
                    avatar = c.avatar.url
                    if not avatar.startswith("http"):
                        avatar = request.build_absolute_uri(avatar)
                children.append({
                    "id": c.id,
                    "name": c.full_name or c.first_name or "—",
                    "age": c.age,
                    "gender": c.gender,
                    "status": c.child_status,
                    "avatar": avatar,
                    "phone": c.phone,
                    "linked_at": link.created_at.isoformat() if link.created_at else None,
                })

        # To'lovlar
        payments = []
        if parent:
            for p in SubscriptionPayment.objects.filter(
                user=parent
            ).select_related("plan").order_by("-created_at")[:50]:
                payments.append({
                    "id": p.id,
                    "amount": int(getattr(p, "amount", 0) or 0),
                    "currency": getattr(p, "currency", "UZS") or "UZS",
                    "status": getattr(p, "status", "") or "",
                    "plan_name": getattr(p.plan, "name", None) if getattr(p, "plan_id", None) else None,
                    "created_at": p.created_at.isoformat(),
                })

        # Faollik (so'nggi loginlar + lead status o'zgarishlari + SOS)
        activity = []
        if parent and parent.last_login:
            activity.append({
                "type": "login",
                "label": "Tizimga kirdi",
                "at": parent.last_login.isoformat(),
            })
        if parent:
            for s in SOSAlert.objects.filter(parent=parent).order_by("-created_at")[:10]:
                activity.append({
                    "type": "sos",
                    "label": "SOS bildirishnoma",
                    "at": s.created_at.isoformat() if hasattr(s, "created_at") else None,
                })
        # Lead status o'zgarishlari (CallCenterComment'dan)
        for c in CallCenterComment.objects.filter(ticket=t).order_by("-created_at")[:20]:
            if c.old_status and c.new_status and c.old_status != c.new_status:
                activity.append({
                    "type": "status",
                    "label": f"Status o'zgartirildi: {c.old_status} → {c.new_status}",
                    "at": c.created_at.isoformat(),
                })
        activity.sort(key=lambda x: x.get("at") or "", reverse=True)

        return Response({
            "lead": lead,
            "children": children,
            "payments": payments,
            "activity": activity[:30],
        })


class AdminLeadCommentsView(APIView):
    """Lead izohlari — operatorlar yozadigan history.

    POST endpoint multipart/form-data ham qabul qiladi: `text` matn va
    ixtiyoriy `attachment` fayl (rasm yoki hujjat). Telegram orqali
    kelgan tikket bo'lsa, javob mos ravishda `tg_send_message` yoki
    `tg_send_photo`/`tg_send_document` bilan foydalanuvchiga yetkaziladi.
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get(self, request, ticket_id):
        comments = CallCenterComment.objects.filter(
            ticket_id=ticket_id
        ).select_related("operator").order_by("-created_at")
        return Response({
            "results": [
                _comment_to_dict(c, request=request) for c in comments[:100]
            ],
        })

    def post(self, request, ticket_id):
        ticket = CallCenterTicket.objects.filter(id=ticket_id).first()
        if not ticket:
            return Response({"detail": "Lead topilmadi"}, status=404)
        text = (request.data.get("text") or "").strip()
        upload = request.FILES.get("attachment")
        if not text and not upload:
            return Response(
                {"detail": "text yoki attachment majburiy"},
                status=400,
            )

        attachment_kind = ""
        attachment_name = ""
        if upload:
            attachment_name = upload.name[:255]
            ctype = (upload.content_type or "").lower()
            if ctype.startswith("image/") or attachment_name.lower().endswith(
                (".jpg", ".jpeg", ".png", ".gif", ".webp")
            ):
                attachment_kind = CallCenterComment.ATTACHMENT_PHOTO
            else:
                attachment_kind = CallCenterComment.ATTACHMENT_DOCUMENT

        c = CallCenterComment.objects.create(
            ticket=ticket,
            operator=request.user,
            comment=text,
            direction=CallCenterComment.DIRECTION_OUT,
            old_status=ticket.status,
            new_status=ticket.status,
            attachment=upload if upload else None,
            attachment_kind=attachment_kind,
            attachment_name=attachment_name,
        )
        ticket.last_contact_at = timezone.now()
        ticket.save(update_fields=["last_contact_at", "updated_at"])

        # Telegramdan kelgan murojaat bo'lsa, javobni botga yuboramiz.
        # Fayl bo'lsa — tegishli sendPhoto/sendDocument; matn bo'lsa
        # oddiy sendMessage. Caption bilan rasm yuborilsa ikkalasi
        # ham bir xil postda yetkaziladi.
        if ticket.telegram_chat_id:
            from .telegram_bot import (
                tg_send_message,
                tg_send_photo,
                tg_send_document,
            )
            mid = None
            if attachment_kind == CallCenterComment.ATTACHMENT_PHOTO and c.attachment:
                mid = tg_send_photo(
                    ticket.telegram_chat_id,
                    c.attachment.path,
                    caption=text or None,
                )
            elif attachment_kind == CallCenterComment.ATTACHMENT_DOCUMENT and c.attachment:
                mid = tg_send_document(
                    ticket.telegram_chat_id,
                    c.attachment.path,
                    caption=text or None,
                    filename=attachment_name,
                )
            elif text:
                mid = tg_send_message(ticket.telegram_chat_id, text)
            if mid:
                c.telegram_message_id = str(mid)
                c.save(update_fields=["telegram_message_id"])

        payload = _comment_to_dict(c, request=request)
        try:
            broadcast_lead_comment({"ticket_id": ticket.id, "comment": payload})
        except Exception:
            pass
        return Response(payload, status=201)


# ============================================================================
# Operators (call-center staff) management
# ============================================================================


class AdminOperatorListView(APIView):
    """Call operator rolidagi foydalanuvchilar.
    Loyihada alohida "operator" rol bo'lmasa, `is_staff=True` ammo
    superuser bo'lmagan foydalanuvchilarni qaytaramiz."""

    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        qs = User.objects.filter(is_staff=True, is_superuser=False).select_related("admin_role").order_by("-date_joined")
        items = []
        for u in qs:
            items.append({
                "id": u.id,
                "phone": u.phone,
                "username": u.username,
                "first_name": u.first_name,
                "last_name": u.last_name,
                "is_active": u.is_active,
                "date_joined": u.date_joined,
                "role_id": u.admin_role_id,
                "role_name": u.admin_role.name if u.admin_role else None,
            })
        return Response({"count": qs.count(), "results": items})


class AdminOperatorCreateView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def post(self, request):
        phone = (request.data.get("phone") or "").strip()
        password = request.data.get("password") or ""
        full_name = (request.data.get("full_name") or "").strip()
        if not phone or not password:
            return Response({"detail": "phone va password majburiy"}, status=400)
        if User.objects.filter(phone=phone).exists():
            return Response({"detail": "Bunday telefon bilan foydalanuvchi mavjud"}, status=400)
        role_id = request.data.get("role_id")
        role = None
        if role_id:
            from .models import AdminRole
            role = AdminRole.objects.filter(id=role_id).first()
            if not role:
                return Response({"detail": "Rol topilmadi."}, status=400)
        u = User(phone=phone, username=phone, first_name=full_name, is_staff=True, role=getattr(User, "ROLE_PARENT", "parent"))
        u.admin_role = role
        u.set_password(password)
        u.save()
        return Response({
            "id": u.id, "phone": u.phone, "username": u.username,
            "first_name": u.first_name, "is_active": u.is_active,
            "role_id": u.admin_role_id,
            "role_name": u.admin_role.name if u.admin_role else None,
        }, status=201)


class AdminOperatorDetailView(APIView):
    """Xodimni tahrirlash / o'chirish / parolini reset qilish."""
    permission_classes = [IsAuthenticated, IsAdminUser]

    def _ensure_staff(self, user):
        return user and user.is_staff and not user.is_superuser

    def patch(self, request, user_id):
        u = User.objects.filter(id=user_id).first()
        if not self._ensure_staff(u):
            return Response({"detail": "Xodim topilmadi"}, status=404)
        update_fields = []
        full_name = request.data.get("full_name")
        if full_name is not None:
            u.first_name = full_name.strip()
            u.full_name = full_name.strip()
            update_fields += ["first_name", "full_name"]
        phone = request.data.get("phone")
        if phone is not None:
            phone = phone.strip()
            if phone != u.phone:
                if User.objects.filter(phone=phone).exclude(id=u.id).exists():
                    return Response({"detail": "Bu telefon allaqachon ishlatilgan"}, status=400)
                u.phone = phone
                update_fields.append("phone")
        is_active = request.data.get("is_active")
        if is_active is not None:
            u.is_active = bool(is_active)
            update_fields.append("is_active")
        if "role_id" in request.data:
            role_id = request.data.get("role_id")
            if role_id is None or role_id == "":
                u.admin_role = None
            else:
                from .models import AdminRole
                role = AdminRole.objects.filter(id=role_id).first()
                if not role:
                    return Response({"detail": "Rol topilmadi."}, status=400)
                u.admin_role = role
            update_fields.append("admin_role")
        new_password = request.data.get("new_password")
        if new_password:
            if len(new_password) < 4:
                return Response({"detail": "Parol kamida 4 belgidan iborat"}, status=400)
            u.set_password(new_password)
            update_fields.append("password")
        if update_fields:
            u.save(update_fields=update_fields)
        return Response({
            "id": u.id, "phone": u.phone, "username": u.username,
            "first_name": u.first_name, "is_active": u.is_active,
            "role_id": u.admin_role_id,
            "role_name": u.admin_role.name if u.admin_role else None,
        })

    def delete(self, request, user_id):
        u = User.objects.filter(id=user_id).first()
        if not self._ensure_staff(u):
            return Response({"detail": "Xodim topilmadi"}, status=404)
        if u.id == request.user.id:
            return Response({"detail": "O'zingizni o'chirib bo'lmaydi"}, status=400)
        u.delete()
        return Response(status=204)


# ============================================================================
# Settings — admin profilini o'zgartirish (parolni almashtirish)
# ============================================================================


class AdminChangePasswordView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def post(self, request):
        old = request.data.get("old_password") or ""
        new = request.data.get("new_password") or ""
        if not new or len(new) < 4:
            return Response({"detail": "Yangi parol 4+ belgidan iborat bo'lishi kerak"}, status=400)
        user = request.user
        if not user.check_password(old):
            return Response({"detail": "Joriy parol noto'g'ri"}, status=400)
        user.set_password(new)
        user.save(update_fields=["password"])
        return Response({"status": True})


# ============================================================================
# Children — read-only list for "Children" tab
# ============================================================================


class AdminChildrenListView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        from .models import ParentChild
        qs = User.objects.filter(role=User.ROLE_CHILD).order_by("-date_joined")
        page_size = int(request.query_params.get("page_size", 50))
        offset = int(request.query_params.get("offset", 0))
        total = qs.count()
        page = list(qs[offset:offset + page_size])

        # Bir requestda barcha ParentChild bog'lanishlarini olib kelamiz —
        # har bir bolaga N+1 query ishlamasin.
        child_ids = [c.id for c in page]
        links = ParentChild.objects.filter(
            child_id__in=child_ids
        ).select_related("parent")
        parent_map = {}
        for link in links:
            p = link.parent
            parent_map[link.child_id] = {
                "id": p.id,
                "phone": p.phone or "",
                "first_name": p.first_name or "",
                "last_name": p.last_name or "",
                "full_name": (p.full_name or "").strip()
                    or " ".join([p.first_name or "", p.last_name or ""]).strip(),
            }

        items = []
        for c in page:
            items.append({
                "id": c.id,
                "phone": c.phone,
                "username": c.username,
                "first_name": c.first_name,
                "child_status": c.child_status,
                "age": c.age,
                "gender": c.gender,
                "language": c.language,
                "is_active": c.is_active,
                "date_joined": c.date_joined,
                "parent": parent_map.get(c.id),
            })
        return Response({
            "count": total,
            "results": items,
            "offset": offset,
            "page_size": page_size,
        })


# ============================================================================
# Media upload — admin file picker uchun. Faylni saqlab, public URL qaytaradi.
# ============================================================================


_ALLOWED_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg"}
_ALLOWED_FOLDERS = {
    "products",
    "categories",
    "banners",
    "blog",
    "blog/thumbnails",
    "blog/banners",
    "avatars",
    "children",
    "uploads",
}
_MAX_BYTES = 10 * 1024 * 1024  # 10 MB


class AdminMediaUploadView(APIView):
    """Multipart file upload. JSON qaytaradi: {url, path, name, size}.

    Mijoz tarafda foydalanish:
      const fd = new FormData(); fd.append("file", f); fd.append("folder", "products");
      fetch("/api/admin/upload/", {method:"POST", body:fd, headers:{Authorization:"Bearer ..."}})
    """

    permission_classes = [IsAuthenticated, IsAdminUser]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        f = request.FILES.get("file")
        if not f:
            return Response(
                {"detail": "file majburiy"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if f.size > _MAX_BYTES:
            return Response(
                {"detail": f"Maksimal {_MAX_BYTES // 1024 // 1024} MB"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        folder = (request.data.get("folder") or "uploads").strip("/ ").lower()
        if folder not in _ALLOWED_FOLDERS:
            folder = "uploads"

        ext = os.path.splitext(f.name)[1].lower()
        if ext not in _ALLOWED_IMAGE_EXTS and not (request.data.get("any") == "1"):
            return Response(
                {"detail": f"Faqat rasm: {sorted(_ALLOWED_IMAGE_EXTS)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        rel_path = f"admin_uploads/{folder}/{uuid.uuid4().hex}{ext}"
        saved = default_storage.save(rel_path, f)
        # default_storage may return a different path than requested if conflict.
        url = default_storage.url(saved)
        # Absolute URL (so client can use it directly even from another origin).
        if not url.startswith("http"):
            url = request.build_absolute_uri(url)

        return Response({
            "url": url,
            "path": saved,
            "name": f.name,
            "size": f.size,
        }, status=status.HTTP_201_CREATED)


# ============================================================================
# SMS test va status — SMSFLY integratsiyasini tekshirish
# ============================================================================


class AdminSmsLogView(APIView):
    """SMS yuborish jurnali — har bir urinish, success/fail, sabab bilan.

    Query parametrlari:
      kind      — otp / broadcast / rule / test / other
      success   — true / false (string)
      phone     — substring qidirish (normalized telefon bo'yicha)
      page_size — default 50
      offset    — pagination
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        from .models import SmsSendLog
        qs = SmsSendLog.objects.all()
        kind = request.query_params.get("kind")
        if kind:
            qs = qs.filter(kind=kind)
        success = request.query_params.get("success")
        if success in ("true", "1"):
            qs = qs.filter(success=True)
        elif success in ("false", "0"):
            qs = qs.filter(success=False)
        phone = (request.query_params.get("phone") or "").strip()
        if phone:
            digits = "".join(c for c in phone if c.isdigit())
            qs = qs.filter(phone_normalized__icontains=digits or phone)
        try:
            page_size = max(1, min(int(request.query_params.get("page_size", 50)), 200))
        except ValueError:
            page_size = 50
        try:
            offset = max(0, int(request.query_params.get("offset", 0)))
        except ValueError:
            offset = 0
        total = qs.count()
        items = []
        for r in qs[offset:offset + page_size]:
            items.append({
                "id": r.id,
                "phone": r.phone,
                "phone_normalized": r.phone_normalized,
                "kind": r.kind,
                "message": r.message,
                "success": r.success,
                "result_code": r.result_code,
                "reason": r.reason,
                "retry_count": r.retry_count,
                "related_user_id": r.related_user_id,
                "created_at": r.created_at.isoformat(),
            })

        # Statistik xulosa — admin UI da chiroyli ko'rsatish uchun
        from django.db.models import Count, Q
        stats_qs = SmsSendLog.objects.all()
        if kind:
            stats_qs = stats_qs.filter(kind=kind)
        stats = stats_qs.aggregate(
            total_all=Count("id"),
            sent_all=Count("id", filter=Q(success=True)),
            failed_all=Count("id", filter=Q(success=False)),
        )
        # Eng tez-tez uchraydigan xato sabablarini ham ko'rsatamiz
        top_reasons = list(
            stats_qs.filter(success=False)
            .values("reason")
            .annotate(c=Count("id"))
            .order_by("-c")[:10]
        )

        return Response({
            "count": total,
            "offset": offset,
            "page_size": page_size,
            "results": items,
            "stats": {
                "total": stats["total_all"] or 0,
                "sent": stats["sent_all"] or 0,
                "failed": stats["failed_all"] or 0,
                "top_failure_reasons": top_reasons,
            },
        })


class AdminSmsTestView(APIView):
    """Adminga SMSFLY kalitining ishlashini va test SMS yuborishni tekshirib
    ko'rish imkonini beradi.

    GET  — SMSFLY check-key chaqirib `enabled` qaytaradi.
    POST — body {"phone": "+998...", "message": "..."} bilan bitta SMS.
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        from .sms_service import sms_client
        return Response({
            "enabled": sms_client.enabled,
            "key_valid": sms_client.check_key() if sms_client.enabled else False,
        })

    def post(self, request):
        from .sms_service import sms_client, normalize_phone, is_valid_uz_phone
        from .models import SmsSendLog
        phone = (request.data.get("phone") or "").strip()
        message = (request.data.get("message") or "JoJo: test xabar").strip()
        if not phone:
            return Response({"detail": "phone majburiy"}, status=400)
        ok = sms_client.send(phone, message, kind=SmsSendLog.KIND_TEST)
        # Tegishli oxirgi log yozuvini ham qaytaramiz — UI da reason ko'rsatadi
        normalized = normalize_phone(phone)
        last = SmsSendLog.objects.filter(
            phone_normalized=normalized,
        ).order_by("-created_at").first()
        return Response({
            "success": ok,
            "phone": phone,
            "normalized": normalized,
            "valid": is_valid_uz_phone(normalized),
            "reason": last.reason if last else "",
            "result_code": last.result_code if last else -1,
            "retry_count": last.retry_count if last else 0,
        })


# ============================================================================
# Kids kontent — o'yinlar (GameCategory + GameItem) admin CRUD
# ============================================================================


def _game_category_to_dict(c, request=None):
    icon = None
    if c.icon and hasattr(c.icon, "url") and c.icon.name:
        url = c.icon.url
        icon = request.build_absolute_uri(url) if request and not url.startswith("http") else url
    return {
        "id": c.id,
        "name": c.name,
        "icon": icon,
        "is_active": c.is_active,
        "order": c.order,
        "games_count": c.games.count(),
    }


def _game_to_dict(g, request=None):
    def _img(f):
        if not f or not hasattr(f, "url") or not f.name:
            return None
        url = f.url
        return request.build_absolute_uri(url) if request and not url.startswith("http") else url
    return {
        "id": g.id,
        "category": g.category_id,
        "category_name": g.category.name if g.category else None,
        "title": g.title,
        "description": g.description or "",
        "thumbnail": _img(g.thumbnail),
        "banner": _img(g.banner),
        "game_url": g.game_url or "",
        "screen_key": g.screen_key or "",
        "age_min": g.age_min,
        "age_max": g.age_max,
        "reward_points": g.reward_points,
        "is_active": g.is_active,
        "is_featured": g.is_featured,
        "order": g.order,
    }


def _resolve_image_path(value):
    """`https://api.jojoapp.uz/media/foo.jpg` -> `foo.jpg`; relativlarni o'tkazib yuboramiz."""
    if not value or not isinstance(value, str):
        return None
    v = value.strip()
    if not v:
        return None
    if v.startswith("http"):
        from urllib.parse import urlparse
        from django.conf import settings
        path = urlparse(v).path
        prefix = (settings.MEDIA_URL or "/media/").rstrip("/") + "/"
        idx = path.find(prefix)
        if idx == -1:
            return None
        return path[idx + len(prefix):]
    return v[1:] if v.startswith("/") else v


class AdminGameCategoryListCreate(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        qs = GameCategory.objects.all().order_by("order", "id")
        return Response({"results": [_game_category_to_dict(c, request) for c in qs]})

    def post(self, request):
        name = (request.data.get("name") or "").strip()
        if not name:
            return Response({"detail": "Nom majburiy"}, status=400)
        c = GameCategory.objects.create(
            name=name,
            is_active=bool(request.data.get("is_active", True)),
            order=int(request.data.get("order") or 0),
        )
        icon = _resolve_image_path(request.data.get("icon"))
        if icon:
            c.icon.name = icon
            c.save(update_fields=["icon"])
        return Response(_game_category_to_dict(c, request), status=201)


class AdminGameCategoryDetail(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def patch(self, request, cat_id):
        c = GameCategory.objects.filter(id=cat_id).first()
        if not c:
            return Response({"detail": "Topilmadi"}, status=404)
        for f in ("name", "is_active", "order"):
            if f in request.data:
                setattr(c, f, request.data[f])
        icon = _resolve_image_path(request.data.get("icon"))
        if icon:
            c.icon.name = icon
        c.save()
        return Response(_game_category_to_dict(c, request))

    def delete(self, request, cat_id):
        c = GameCategory.objects.filter(id=cat_id).first()
        if not c:
            return Response({"detail": "Topilmadi"}, status=404)
        c.delete()
        return Response(status=204)


class AdminGameListCreate(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        qs = GameItem.objects.all().select_related("category").order_by("order", "-created_at")
        cat = request.query_params.get("category_id")
        if cat:
            qs = qs.filter(category_id=cat)
        q = request.query_params.get("q")
        if q:
            qs = qs.filter(title__icontains=q)
        return Response({"results": [_game_to_dict(g, request) for g in qs[:200]]})

    def post(self, request):
        title = (request.data.get("title") or "").strip()
        if not title:
            return Response({"detail": "Sarlavha majburiy"}, status=400)
        category_id = request.data.get("category")
        category = GameCategory.objects.filter(id=category_id).first() if category_id else None
        if not category:
            return Response({"detail": "Kategoriya tanlang"}, status=400)
        g = GameItem.objects.create(
            category=category,
            title=title,
            description=request.data.get("description") or "",
            game_url=request.data.get("game_url") or "",
            screen_key=request.data.get("screen_key") or "",
            age_min=int(request.data.get("age_min") or 1),
            age_max=int(request.data.get("age_max") or 18),
            reward_points=int(request.data.get("reward_points") or 0),
            is_active=bool(request.data.get("is_active", True)),
            is_featured=bool(request.data.get("is_featured", False)),
            order=int(request.data.get("order") or 0),
        )
        for attr in ("thumbnail", "banner"):
            p = _resolve_image_path(request.data.get(attr))
            if p:
                getattr(g, attr).name = p
        g.save()
        return Response(_game_to_dict(g, request), status=201)


class AdminGameDetail(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def patch(self, request, game_id):
        g = GameItem.objects.filter(id=game_id).first()
        if not g:
            return Response({"detail": "Topilmadi"}, status=404)
        for f in (
            "title", "description", "game_url", "screen_key",
            "age_min", "age_max", "reward_points",
            "is_active", "is_featured", "order",
        ):
            if f in request.data:
                setattr(g, f, request.data[f])
        cat = request.data.get("category")
        if cat:
            cat_obj = GameCategory.objects.filter(id=cat).first()
            if cat_obj:
                g.category = cat_obj
        for attr in ("thumbnail", "banner"):
            p = _resolve_image_path(request.data.get(attr))
            if p:
                getattr(g, attr).name = p
        g.save()
        return Response(_game_to_dict(g, request))

    def delete(self, request, game_id):
        g = GameItem.objects.filter(id=game_id).first()
        if not g:
            return Response({"detail": "Topilmadi"}, status=404)
        g.delete()
        return Response(status=204)


# ============================================================================
# Kids video kontent — KidsVideoCategory + KidsVideo admin CRUD
# Play tab (kids ilovasi 2-navbar) uchun YouTube video kontenti.
# ============================================================================


def _kids_video_category_to_dict(c, request=None):
    icon = None
    if c.icon and hasattr(c.icon, "url") and c.icon.name:
        url = c.icon.url
        icon = request.build_absolute_uri(url) if request and not url.startswith("http") else url
    return {
        "id": c.id,
        "name": c.name,
        "name_ru": c.name_ru,
        "name_en": c.name_en,
        "name_uz_cyrl": getattr(c, "name_uz_cyrl", "") or "",
        "icon": icon,
        "is_active": c.is_active,
        "order": c.order,
        "videos_count": c.videos.count(),
    }


def _kids_video_to_dict(v, request=None):
    def _img(f):
        if not f or not hasattr(f, "url") or not f.name:
            return None
        url = f.url
        return request.build_absolute_uri(url) if request and not url.startswith("http") else url

    thumb = _img(v.thumbnail)
    if not thumb and v.youtube_id:
        thumb = f"https://img.youtube.com/vi/{v.youtube_id}/hqdefault.jpg"

    return {
        "id": v.id,
        "category": v.category_id,
        "category_name": v.category.name if v.category else None,
        "title": v.title,
        "title_ru": v.title_ru,
        "title_en": v.title_en,
        "description": v.description or "",
        "description_ru": v.description_ru,
        "description_en": v.description_en,
        "youtube_url": v.youtube_url,
        "youtube_id": v.youtube_id,
        "thumbnail": _img(v.thumbnail),
        "thumbnail_url": thumb,
        "duration_label": v.duration_label,
        "age_min": v.age_min,
        "age_max": v.age_max,
        "views_count": v.views_count,
        "is_active": v.is_active,
        "is_featured": v.is_featured,
        "order": v.order,
    }


class AdminKidsVideoCategoryListCreate(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        qs = KidsVideoCategory.objects.all().order_by("order", "id")
        return Response({"results": [_kids_video_category_to_dict(c, request) for c in qs]})

    def post(self, request):
        name = (request.data.get("name") or "").strip()
        if not name:
            return Response({"detail": "Nom majburiy"}, status=400)
        c = KidsVideoCategory.objects.create(
            name=name,
            name_ru=(request.data.get("name_ru") or "").strip(),
            name_en=(request.data.get("name_en") or "").strip(),
            is_active=bool(request.data.get("is_active", True)),
            order=int(request.data.get("order") or 0),
        )
        icon = _resolve_image_path(request.data.get("icon"))
        if icon:
            c.icon.name = icon
            c.save(update_fields=["icon"])
        return Response(_kids_video_category_to_dict(c, request), status=201)


class AdminKidsVideoCategoryDetail(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def patch(self, request, cat_id):
        c = KidsVideoCategory.objects.filter(id=cat_id).first()
        if not c:
            return Response({"detail": "Topilmadi"}, status=404)
        for f in ("name", "name_ru", "name_en", "is_active", "order"):
            if f in request.data:
                setattr(c, f, request.data[f])
        icon = _resolve_image_path(request.data.get("icon"))
        if icon:
            c.icon.name = icon
        c.save()
        return Response(_kids_video_category_to_dict(c, request))

    def delete(self, request, cat_id):
        c = KidsVideoCategory.objects.filter(id=cat_id).first()
        if not c:
            return Response({"detail": "Topilmadi"}, status=404)
        c.delete()
        return Response(status=204)


class AdminKidsVideoListCreate(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        qs = (
            KidsVideo.objects.all()
            .select_related("category")
            .order_by("order", "-created_at")
        )
        cat = request.query_params.get("category_id")
        if cat:
            qs = qs.filter(category_id=cat)
        q = request.query_params.get("q")
        if q:
            qs = qs.filter(title__icontains=q)
        return Response({"results": [_kids_video_to_dict(v, request) for v in qs[:200]]})

    def post(self, request):
        title = (request.data.get("title") or "").strip()
        if not title:
            return Response({"detail": "Sarlavha majburiy"}, status=400)
        youtube_url = (request.data.get("youtube_url") or "").strip()
        if not youtube_url:
            return Response({"detail": "YouTube havola majburiy"}, status=400)
        category_id = request.data.get("category")
        category = KidsVideoCategory.objects.filter(id=category_id).first() if category_id else None
        if not category:
            return Response({"detail": "Kategoriya tanlang"}, status=400)
        v = KidsVideo.objects.create(
            category=category,
            title=title,
            title_ru=(request.data.get("title_ru") or "").strip(),
            title_en=(request.data.get("title_en") or "").strip(),
            description=request.data.get("description") or "",
            description_ru=request.data.get("description_ru") or "",
            description_en=request.data.get("description_en") or "",
            youtube_url=youtube_url,
            duration_label=(request.data.get("duration_label") or "").strip(),
            age_min=int(request.data.get("age_min") or 3),
            age_max=int(request.data.get("age_max") or 12),
            is_active=bool(request.data.get("is_active", True)),
            is_featured=bool(request.data.get("is_featured", False)),
            order=int(request.data.get("order") or 0),
        )
        thumb = _resolve_image_path(request.data.get("thumbnail"))
        if thumb:
            v.thumbnail.name = thumb
            v.save(update_fields=["thumbnail"])
        return Response(_kids_video_to_dict(v, request), status=201)


class AdminKidsVideoDetail(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def patch(self, request, video_id):
        v = KidsVideo.objects.filter(id=video_id).first()
        if not v:
            return Response({"detail": "Topilmadi"}, status=404)
        text_fields = (
            "title", "title_ru", "title_en",
            "description", "description_ru", "description_en",
            "youtube_url", "duration_label",
        )
        for f in text_fields:
            if f in request.data:
                setattr(v, f, request.data[f] or "")
        int_fields = ("age_min", "age_max", "order")
        for f in int_fields:
            if f in request.data:
                setattr(v, f, int(request.data[f] or 0))
        for f in ("is_active", "is_featured"):
            if f in request.data:
                setattr(v, f, bool(request.data[f]))
        cat = request.data.get("category")
        if cat:
            cat_obj = KidsVideoCategory.objects.filter(id=cat).first()
            if cat_obj:
                v.category = cat_obj
        thumb = _resolve_image_path(request.data.get("thumbnail"))
        if thumb:
            v.thumbnail.name = thumb
        v.save()
        return Response(_kids_video_to_dict(v, request))

    def delete(self, request, video_id):
        v = KidsVideo.objects.filter(id=video_id).first()
        if not v:
            return Response({"detail": "Topilmadi"}, status=404)
        v.delete()
        return Response(status=204)


class TelegramWebhookView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        expected = getattr(settings, "TELEGRAM_WEBHOOK_SECRET", "")
        header_secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if expected and header_secret != expected:
            return Response({"detail": "forbidden"}, status=403)
        from .telegram_bot import handle_telegram_update
        try:
            handle_telegram_update(request.data)
        except Exception:
            import logging
            logging.getLogger(__name__).exception("Telegram update handling failed")
        return Response({"ok": True})

# ============================================================================
# NotificationRule — avtomatik rejaviy bildirishnomalar
# ============================================================================


def _rule_to_dict(r):
    return {
        "id": r.id,
        "name": r.name,
        "trigger_type": r.trigger_type,
        "trigger_params": r.trigger_params or {},
        "audience": r.audience,
        "audience_params": r.audience_params or {},
        "title": r.title,
        "title_ru": r.title_ru,
        "title_en": r.title_en,
        "body": r.body,
        "body_ru": r.body_ru,
        "body_en": r.body_en,
        "category": r.category,
        "send_push": r.send_push,
        "send_sms": r.send_sms,
        "is_active": r.is_active,
        "last_run_at": r.last_run_at.isoformat() if r.last_run_at else None,
        "next_run_at": r.next_run_at.isoformat() if r.next_run_at else None,
        "created_at": r.created_at.isoformat(),
    }


def _rule_apply_payload(rule, data):
    for f in ("name", "trigger_type", "audience", "title", "title_ru", "title_en",
              "body", "body_ru", "body_en", "category"):
        if f in data:
            setattr(rule, f, data[f] or "")
    if "trigger_params" in data:
        rule.trigger_params = data["trigger_params"] or {}
    if "audience_params" in data:
        rule.audience_params = data["audience_params"] or {}
    if "send_push" in data:
        rule.send_push = bool(data["send_push"])
    if "send_sms" in data:
        rule.send_sms = bool(data["send_sms"])
    if "is_active" in data:
        rule.is_active = bool(data["is_active"])


class AdminNotificationRuleListCreate(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        qs = NotificationRule.objects.all().order_by("-updated_at")
        return Response({"results": [_rule_to_dict(r) for r in qs[:200]]})

    def post(self, request):
        from .notification_scheduler import compute_next_run
        data = request.data or {}
        rule = NotificationRule()
        _rule_apply_payload(rule, data)
        if not rule.name or not rule.title or not rule.body:
            return Response({"detail": "name, title, body majburiy"}, status=400)
        rule.save()
        rule.next_run_at = compute_next_run(rule)
        rule.save(update_fields=["next_run_at"])
        return Response(_rule_to_dict(rule), status=201)


class AdminNotificationRuleDetail(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request, rule_id):
        r = NotificationRule.objects.filter(id=rule_id).first()
        if not r:
            return Response({"detail": "Topilmadi"}, status=404)
        return Response(_rule_to_dict(r))

    def patch(self, request, rule_id):
        from .notification_scheduler import compute_next_run
        r = NotificationRule.objects.filter(id=rule_id).first()
        if not r:
            return Response({"detail": "Topilmadi"}, status=404)
        _rule_apply_payload(r, request.data or {})
        r.save()
        r.next_run_at = compute_next_run(r)
        r.save(update_fields=["next_run_at"])
        return Response(_rule_to_dict(r))

    def delete(self, request, rule_id):
        r = NotificationRule.objects.filter(id=rule_id).first()
        if not r:
            return Response({"detail": "Topilmadi"}, status=404)
        r.delete()
        return Response(status=204)


class AdminNotificationRuleRunNow(APIView):
    """Rule'ni darrov sinash uchun manual ishga tushirish."""
    permission_classes = [IsAuthenticated, IsAdminUser]

    def post(self, request, rule_id):
        from .notification_scheduler import fire_rule
        r = NotificationRule.objects.filter(id=rule_id).first()
        if not r:
            return Response({"detail": "Topilmadi"}, status=404)
        log = fire_rule(r)
        return Response({
            "id": log.id,
            "recipients_count": log.recipients_count,
            "push_sent": log.push_sent,
            "sms_sent": log.sms_sent,
            "success": log.success,
            "detail": log.detail,
        })


class AdminNotificationRuleLogs(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request, rule_id):
        logs = NotificationRuleLog.objects.filter(rule_id=rule_id).order_by("-fired_at")[:50]
        return Response({
            "results": [{
                "id": l.id,
                "fired_at": l.fired_at.isoformat(),
                "recipients_count": l.recipients_count,
                "push_sent": l.push_sent,
                "sms_sent": l.sms_sent,
                "success": l.success,
                "detail": l.detail,
            } for l in logs]
        })


# ============================================================================
# Admin Roles (xodimga rol berish)
# ============================================================================

from .models import AdminRole as _AdminRole

# Sidebar permission kalitlari — frontend bilan bir xil bo'lishi kerak.
ADMIN_PERMISSION_KEYS = [
    "dashboard", "leads", "users", "children", "premium", "payments",
    "requests", "notifications", "notification_rules", "sms", "ads",
    "settings", "operators", "roles", "blocked",
    "products", "categories", "banners", "orders",
    "advice", "kids_content",
]


def _role_to_dict(r):
    return {
        "id": r.id,
        "name": r.name,
        "description": r.description,
        "permissions": list(r.permissions or []),
        "is_system": r.is_system,
        "users_count": r.users.count(),
        "created_at": r.created_at,
        "updated_at": r.updated_at,
    }


class AdminRoleListCreateView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        qs = _AdminRole.objects.all().order_by("name")
        return Response({
            "count": qs.count(),
            "results": [_role_to_dict(r) for r in qs],
            "available_permissions": ADMIN_PERMISSION_KEYS,
        })

    def post(self, request):
        name = (request.data.get("name") or "").strip()
        if not name:
            return Response({"detail": "Rol nomi majburiy."}, status=400)
        if _AdminRole.objects.filter(name=name).exists():
            return Response({"detail": "Bu nomli rol allaqachon mavjud."}, status=400)
        perms = request.data.get("permissions") or []
        if not isinstance(perms, list):
            return Response({"detail": "permissions ro'yxat (list) bo'lishi kerak."}, status=400)
        # Faqat ma'lum kalitlarni qabul qilamiz — adash qilingan kalitlarni tashlab yuboramiz.
        perms = [p for p in perms if p in ADMIN_PERMISSION_KEYS]
        r = _AdminRole.objects.create(
            name=name,
            description=request.data.get("description") or "",
            permissions=perms,
        )
        return Response(_role_to_dict(r), status=201)


class AdminRoleDetailView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def _get(self, role_id):
        return _AdminRole.objects.filter(id=role_id).first()

    def get(self, request, role_id):
        r = self._get(role_id)
        if not r:
            return Response({"detail": "Rol topilmadi."}, status=404)
        return Response(_role_to_dict(r))

    def patch(self, request, role_id):
        r = self._get(role_id)
        if not r:
            return Response({"detail": "Rol topilmadi."}, status=404)
        if r.is_system:
            return Response({"detail": "Tizim rolini o'zgartirib bo'lmaydi."}, status=403)
        name = request.data.get("name")
        if name is not None:
            name = name.strip()
            if not name:
                return Response({"detail": "Nom bo'sh bo'lishi mumkin emas."}, status=400)
            if _AdminRole.objects.filter(name=name).exclude(id=r.id).exists():
                return Response({"detail": "Bu nomli rol allaqachon mavjud."}, status=400)
            r.name = name
        if "description" in request.data:
            r.description = request.data.get("description") or ""
        if "permissions" in request.data:
            perms = request.data.get("permissions") or []
            if not isinstance(perms, list):
                return Response({"detail": "permissions ro'yxat bo'lishi kerak."}, status=400)
            r.permissions = [p for p in perms if p in ADMIN_PERMISSION_KEYS]
        r.save()
        return Response(_role_to_dict(r))

    def delete(self, request, role_id):
        r = self._get(role_id)
        if not r:
            return Response({"detail": "Rol topilmadi."}, status=404)
        if r.is_system:
            return Response({"detail": "Tizim rolini o'chirib bo'lmaydi."}, status=403)
        r.delete()
        return Response(status=204)


# ============================================================================
# Auto-translate (Admin paneldagi "Auto" tugmasi uchun)
# ============================================================================

from .translation import (
    translate as _do_translate,
    translate_to_all as _do_translate_all,
)


class AdminAutoTranslateView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def post(self, request):
        text = (request.data.get("text") or "").strip()
        source = request.data.get("source") or "uz"
        target = request.data.get("target")
        # `target` bo'lsa — bittasiga, bo'lmasa — uchchalasiga.
        if not text:
            return Response({"detail": "text bo'sh bo'lishi mumkin emas."}, status=400)
        if target:
            result = _do_translate(text, source, target)
            return Response({"text": result, "source": source, "target": target})
        return Response({"translations": _do_translate_all(text, source), "source": source})


# ============================================================================
# Support quick-replies (operator shortcut shablonlari)
#
# Eslatma: bu view'lar `parent/urls.py` ichida 2026-06 da yangi qo'shilgan
# `admin/support/quick-replies/` yo'llari uchun zarur. Boshqa agent commitida
# urls qo'shilgan, lekin views unutilgan — bu erda minimal CRUD beriladi.
# ============================================================================


class _SupportQuickReplySerializer(drf_serializers.ModelSerializer):
    class Meta:
        model = SupportQuickReply
        fields = [
            "id",
            "owner",
            "scope",
            "code",
            "title",
            "text_uz_latn",
            "text_uz_cyrl",
            "text_ru",
            "text_en",
            "order",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class AdminQuickReplyListCreateView(generics.ListCreateAPIView):
    serializer_class = _SupportQuickReplySerializer
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get_queryset(self):
        qs = SupportQuickReply.objects.all()
        scope = self.request.query_params.get("scope")
        if scope:
            qs = qs.filter(scope=scope)
        active = self.request.query_params.get("is_active")
        if active is not None:
            qs = qs.filter(is_active=str(active).lower() in ("1", "true", "yes"))
        return qs


class AdminQuickReplyDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = _SupportQuickReplySerializer
    permission_classes = [IsAuthenticated, IsAdminUser]
    queryset = SupportQuickReply.objects.all()
    lookup_url_kwarg = "qr_id"
