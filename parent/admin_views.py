"""
Admin paneli CRUD API'lari — react admin (jojo_admin) shu yerga ulanadi.

Endpoint'lar `/api/admin/` ostida joylashgan. Auth: JWT + foydalanuvchi
`is_staff=True` bo'lishi shart.
"""

from django.contrib.auth import authenticate
from django.contrib.auth import get_user_model
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated, BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .models import (
    BlogCategory,
    BlogPost,
    CallCenterTicket,
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
from .serializers import (
    BlogCategorySerializer,
    BlogPostDetailSerializer as BlogPostSerializer,
    ParentNotificationSerializer,
    ParentStoreCategorySerializer,
    ParentStoreOrderSerializer,
    ParentStoreProductDetailSerializer as ParentStoreProductSerializer,
    ParentStorePromoBannerSerializer,
    SubscriptionPaymentSerializer,
    SubscriptionPlanSerializer,
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
        items = list(qs[offset:offset + page_size].values(
            "id", "phone", "username", "first_name", "last_name",
            "role", "is_active", "is_staff", "date_joined", "age",
            "gender", "language", "child_status",
        ))
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
        if not title or not body:
            return Response({"detail": "title va body majburiy"}, status=400)
        # Broadcast: barcha parentlarga inbox yozuvi.
        from .services import record_parent_notification
        parents = User.objects.filter(role=User.ROLE_PARENT, is_active=True)
        created = 0
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
            except Exception:
                continue
        return Response({"status": True, "sent_to": created})


# ============================================================================
# Stats / Dashboard
# ============================================================================


class AdminDashboardStatsView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        from django.utils import timezone
        from datetime import timedelta
        total_users = User.objects.filter(role=User.ROLE_PARENT).count()
        total_children = User.objects.filter(role=User.ROLE_CHILD).count()
        active_24h = User.objects.filter(last_login__gte=timezone.now() - timedelta(days=1)).count()
        total_products = ParentStoreProduct.objects.filter(is_active=True).count()
        total_posts = BlogPost.objects.filter(is_active=True).count()
        total_banners = ParentStorePromoBanner.objects.filter(is_active=True).count()
        sos_count = SOSAlert.objects.count()
        return Response({
            "parents": total_users,
            "children": total_children,
            "active_24h": active_24h,
            "products": total_products,
            "blog_posts": total_posts,
            "banners": total_banners,
            "sos_alerts": sos_count,
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


# ============================================================================
# Operators / Support tickets (Call center)
# ============================================================================


class AdminTicketListView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        qs = CallCenterTicket.objects.all().select_related("user", "assignee").order_by("-created_at")
        s = request.query_params.get("status")
        if s:
            qs = qs.filter(status=s)
        page_size = int(request.query_params.get("page_size", 30))
        offset = int(request.query_params.get("offset", 0))
        items = []
        for t in qs[offset:offset + page_size]:
            items.append({
                "id": t.id,
                "subject": t.subject,
                "status": t.status,
                "priority": t.priority,
                "user": {
                    "id": t.user_id,
                    "name": (t.user.full_name or t.user.first_name or t.user.phone) if t.user else None,
                    "phone": t.user.phone if t.user else None,
                } if t.user_id else None,
                "assignee": {
                    "id": t.assignee_id,
                    "name": (t.assignee.full_name or t.assignee.first_name or t.assignee.phone) if t.assignee else None,
                } if t.assignee_id else None,
                "created_at": t.created_at.isoformat(),
                "updated_at": t.updated_at.isoformat() if hasattr(t, "updated_at") else None,
            })
        return Response({"count": qs.count(), "results": items, "offset": offset, "page_size": page_size})


class AdminTicketUpdateStatusView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def post(self, request, ticket_id):
        ticket = CallCenterTicket.objects.filter(id=ticket_id).first()
        if not ticket:
            return Response({"detail": "Topilmadi"}, status=404)
        new_status = request.data.get("status")
        if new_status:
            ticket.status = new_status
            ticket.save(update_fields=["status"])
        return Response({"id": ticket.id, "status": ticket.status})


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
