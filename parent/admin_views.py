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
    ParentStoreCategory,
    ParentStoreProduct,
    ParentStoreProductImage,
    ParentStorePromoBanner,
    SOSAlert,
    ParentNotification,
)
from .serializers import (
    BlogCategorySerializer,
    BlogPostDetailSerializer as BlogPostSerializer,
    ParentStoreCategorySerializer,
    ParentStoreProductDetailSerializer as ParentStoreProductSerializer,
    ParentStorePromoBannerSerializer,
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
