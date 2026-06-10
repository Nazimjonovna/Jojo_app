from django.contrib import admin
from django.urls import path, include
from rest_framework import permissions
from django.conf import settings
from django.conf.urls.static import static
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

schema_view = get_schema_view(
    openapi.Info(
        title="Jojoapp API Documentation",
        default_version='v1',
        description="API documentation for JOJO app",
        contact=openapi.Contact(email="sturayeva000@gmail.com"),
        license=openapi.License(name="MIT License"),
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
    url="https://api.jojoapp.uz",
)


urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('parent.urls')),
    path("api/jojolingo/", include("jojolingo.urls")),
]

urlpatterns += [
    path('swagger<format>/', schema_view.without_ui(cache_timeout=0), name='schema-json'),
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)