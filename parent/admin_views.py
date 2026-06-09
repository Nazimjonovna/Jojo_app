"""
Admin paneli CRUD API'lari — react admin (jojo_admin) shu yerga ulanadi.

Endpoint'lar `/api/admin/` ostida joylashgan. Auth: JWT + foydalanuvchi
`is_staff=True` bo'lishi shart.
"""

import os
import uuid

from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth import get_user_model
from django.core.files.storage import default_storage
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.parsers import MultiPartParser, FormParser
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
    ParentStoreCategory,
    ParentStoreOrder,
    ParentStoreProduct,
    ParentStoreProductImage,
    ParentStorePromoBanner,
    ParentNotification,
    SOSAlert,
    SubscriptionPayment,
    SubscriptionPlan,
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
    """Hamma parentlarga umumiy bildirishnoma yuborish (announcement / elon)."""

    permission_classes = [IsAuthenticated, IsAdminUser]

    def post(self, request):
        title = (request.data.get("title") or "").strip()
        body = (request.data.get("body") or "").strip()
        category = request.data.get("category", "system")
        # Yangi opsiya — `send_sms=true` bo'lsa SMSFLY orqali SMS ham yuboriladi.
        send_sms = bool(request.data.get("send_sms"))
        if not title or not body:
            return Response({"detail": "title va body majburiy"}, status=400)
        # Broadcast: barcha parentlarga inbox yozuvi.
        from .services import record_parent_notification
        parents = User.objects.filter(role=User.ROLE_PARENT, is_active=True)
        created = 0
        phones = []
        for parent in parents:
            try:
                record_parent_notification(
                    parent=parent,
                    child=None,
                    category=category,
                    title=title,
                    body=body,
                    data={"announcement": True},
                )
                created += 1
                if send_sms and parent.phone:
                    phones.append(parent.phone)
            except Exception:
                continue

        sms_sent = 0
        if send_sms and phones:
            # SMS matni: title + body (160 belgi tavsiya). Bitta xabar limiti
            # tashqarisida bo'lsa, SMSFLY o'zi bo'lishadi.
            sms_text = f"{title}\n{body}"[:500]
            from .sms_service import sms_client
            ok = sms_client.send_bulk(phones, sms_text)
            sms_sent = len(phones) if ok else 0

        return Response({
            "status": True,
            "sent_to": created,
            "sms_sent": sms_sent,
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
        qs = ParentNotification.objects.values("title", "body", "category")
        if category:
            qs = qs.filter(category=category)
        rows = (
            qs.annotate(
                count=Count("id"),
                first_sent=Min("created_at"),
                last_sent=Max("created_at"),
            )
            .order_by("-last_sent")[:50]
        )
        return Response({"results": list(rows)})


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
    }


def _comment_to_dict(c):
    op = c.operator
    return {
        "id": c.id,
        "ticket_id": c.ticket_id,
        "text": c.comment,
        "old_status": c.old_status or "",
        "new_status": c.new_status or "",
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
        if "status" in request.data:
            s = request.data["status"]
            if s in dict(CallCenterTicket.STATUS_CHOICES):
                t.status = s
                update_fields.append("status")
                if s == CallCenterTicket.STATUS_CLOSED and not t.closed_at:
                    t.closed_at = timezone.now()
                    update_fields.append("closed_at")
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
    """Lead izohlari — operatorlar yozadigan history."""
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request, ticket_id):
        comments = CallCenterComment.objects.filter(
            ticket_id=ticket_id
        ).select_related("operator").order_by("-created_at")
        return Response({
            "results": [_comment_to_dict(c) for c in comments[:100]],
        })

    def post(self, request, ticket_id):
        ticket = CallCenterTicket.objects.filter(id=ticket_id).first()
        if not ticket:
            return Response({"detail": "Lead topilmadi"}, status=404)
        text = (request.data.get("text") or "").strip()
        if not text:
            return Response({"detail": "text majburiy"}, status=400)
        c = CallCenterComment.objects.create(
            ticket=ticket,
            operator=request.user,
            comment=text,
            old_status=ticket.status,
            new_status=ticket.status,
        )
        # last_contact_at'ni yangilaymiz
        ticket.last_contact_at = timezone.now()
        ticket.save(update_fields=["last_contact_at", "updated_at"])
        payload = _comment_to_dict(c)
        try:
            broadcast_lead_comment({
                "ticket_id": ticket.id,
                "comment": payload,
            })
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
        qs = User.objects.filter(is_staff=True, is_superuser=False).order_by("-date_joined")
        items = list(qs.values(
            "id", "phone", "username", "first_name", "last_name",
            "is_active", "date_joined",
        ))
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
        u = User(phone=phone, username=phone, first_name=full_name, is_staff=True, role=getattr(User, "ROLE_PARENT", "parent"))
        u.set_password(password)
        u.save()
        return Response({
            "id": u.id, "phone": u.phone, "username": u.username,
            "first_name": u.first_name, "is_active": u.is_active,
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
        qs = User.objects.filter(role=User.ROLE_CHILD).order_by("-date_joined")
        page_size = int(request.query_params.get("page_size", 50))
        offset = int(request.query_params.get("offset", 0))
        total = qs.count()
        items = list(qs[offset:offset + page_size].values(
            "id", "phone", "username", "first_name", "child_status",
            "age", "gender", "language", "is_active", "date_joined",
        ))
        return Response({"count": total, "results": items, "offset": offset, "page_size": page_size})


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
        from .sms_service import sms_client
        phone = (request.data.get("phone") or "").strip()
        message = (request.data.get("message") or "JoJo: test xabar").strip()
        if not phone:
            return Response({"detail": "phone majburiy"}, status=400)
        ok = sms_client.send(phone, message)
        return Response({"success": ok, "phone": phone})


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
