import os
from pathlib import Path
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv("SECRET_KEY", "django-insecure-change-me")
DEBUG = os.getenv("DEBUG", "True") == "True"
ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "*").split(",")

# nginx orqasida ishlaganda DRF pagination uchun to'g'ri host va scheme
# olishi shart, aks holda `next` URL ichki Docker manziliga tushib qoladi
# va parent dasturi keyingi sahifani yuklamaydi.
USE_X_FORWARDED_HOST = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")


# Application definition

INSTALLED_APPS = [
    "jazzmin",
    "daphne",
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    "channels",
    'corsheaders',
    'parent',
    'rest_framework',
    'drf_yasg',
]

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated', 
    ),
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=2),
    # Tracking uchun refresh tokens har bir refresh'da yangilanadi va
    # 90 kunga uzaytiriladi — kids dasturi yana 90 kun davomida hech
    # qachon expire bo'lmasligi uchun. Foydalanuvchi har necha soatda
    # access yangilab tursa, refresh ham yangilanib turadi va abadiy
    # ishlaydi.
    "REFRESH_TOKEN_LIFETIME": timedelta(days=90),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": False,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

SWAGGER_SETTINGS = {
    "USE_SESSION_AUTH": False,
    "DEFAULT_API_URL": "https://api.jojoapp.uz",
    'SECURITY_DEFINITIONS': {
        'Bearer': {
            'type': 'apiKey',
            'name': 'Authorization',
            'in': 'header',
            'description': (
                'Bearer <token> formatida kiriting. '
                'Masalan: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...'
            ),
        }
    },

    'USE_SESSION_AUTH': False,
}

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    "whitenoise.middleware.WhiteNoiseMiddleware",
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    "django.middleware.locale.LocaleMiddleware",
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'core.wsgi.application'
ASGI_APPLICATION = "core.asgi.application"
AUTH_USER_MODEL = "parent.User"

# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases

DATABASES = {
    'default': {
        "ENGINE": os.getenv("DB_ENGINE", "django.db.backends.sqlite3"),
        "NAME": os.getenv("DB_NAME", BASE_DIR / "db.sqlite3"),
        "USER": os.getenv("DB_USER", ""),
        "PASSWORD": os.getenv("DB_PASSWORD", ""),
        "HOST": os.getenv("DB_HOST", ""),
        "PORT": os.getenv("DB_PORT", ""),
        # CONN_MAX_AGE: har bir request uchun yangi DB connection ochish o'rniga
        # workerda 60 soniya ushlab turamiz. 100k+ user bilan bu juda muhim —
        # Postgres connection ochish ~5-10ms ketadi, har request'da 5-7 query
        # bo'lsa, bu sezilarli sekinlik.
        "CONN_MAX_AGE": 60,
        # Sog'lom ulanishlarni qayta tekshirish — Postgres restart bo'lsa ham
        # eski stale connection ishlatib ketmaslik uchun.
        "CONN_HEALTH_CHECKS": True,
    }
}


REDIS_HOST = os.getenv("REDIS_HOST", "127.0.0.1")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [(REDIS_HOST, REDIS_PORT)],
            # 100k+ socket uchun: har group'da 10k pending xabar yetadi,
            # expiry pastroq — eski xabarlarni darrov tozalab Redis
            # memoryni tejaymiz.
            "capacity": 10000,
            "expiry": 10,
        },
    },
}

# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGES = [
    ("uz-latn", "O‘zbekcha"),
    ("uz-cyrl", "Ўзбекча"),
    ("ru", "Русский"),
    ("en", "English"),
    ("kaa", "Qaraqalpaqsha"),
]

LANGUAGE_CODE = "uz-latn"
USE_I18N = True
TIME_ZONE = 'UTC'
USE_TZ = True


# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://5.189.151.237",
    "http://5.189.151.237:8000",
    "http://jojoapp.uz",
    "https://jojoapp.uz",
    "http://www.jojoapp.uz",
    "https://www.jojoapp.uz",
    "http://api.jojoapp.uz",
    "https://api.jojoapp.uz",
]

CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^https://[a-z0-9-]+\.vercel\.app$",
    r"^https://jojo-admin(-[a-z0-9-]+)?\.vercel\.app$",
]

CORS_ALLOW_CREDENTIALS = True

CORS_ALLOW_METHODS = [
    "DELETE",
    "GET",
    "OPTIONS",
    "PATCH",
    "POST",
    "PUT",
]

CORS_ALLOW_HEADERS = [
    "accept",
    "accept-encoding",
    "authorization",
    "content-type",
    "dnt",
    "origin",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
]

CSRF_TRUSTED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:8000",
    "http://127.0.0.1:8000",

    "http://5.189.151.237",
    "http://5.189.151.237:8000",

    "http://jojoapp.uz",
    "https://jojoapp.uz",
    "http://www.jojoapp.uz",
    "https://www.jojoapp.uz",
    
    "http://api.jojoapp.uz",
    "https://api.jojoapp.uz",
]
# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

FIREBASE_CREDENTIALS = os.getenv(
    "FIREBASE_CREDENTIALS",
    BASE_DIR / "firebase-service-account.json"
)


JAZZMIN_SETTINGS = {
    "site_title": "Call Center Admin",
    "site_header": "CALL CENTER",
    "site_brand": "CALL CENTER",
    "welcome_sign": "Call Center Admin Panel",
    "copyright": "Jojo App",

    "show_sidebar": True,
    "navigation_expanded": True,

    "order_with_respect_to": [
        "parent.User",
        "parent.ParentChild",
        "parent.SOSAlert",
        "parent.DeviceToken",
        "parent.SavedLocation",
        "parent.RouteAlert",
        "parent.UserSubscription",
        "parent.SubscriptionPayment",
    ],

    "icons": {
        "parent.User": "fas fa-users",
        "parent.ParentChild": "fas fa-child",
        "parent.SOSAlert": "fas fa-bell",
        "parent.DeviceToken": "fas fa-mobile-alt",
        "parent.SavedLocation": "fas fa-map-pin",
        "parent.RouteAlert": "fas fa-exclamation-triangle",
        "parent.UserSubscription": "fas fa-crown",
        "parent.SubscriptionPayment": "fas fa-credit-card",
        "auth.Group": "fas fa-user-shield",
    },
    "topmenu_links": [
        {"name": "Call Center", "url": "/admin/call-center/", "new_window": False},
        {"name": "Swagger", "url": "/swagger/", "new_window": True},
    ],
    "show_sidebar": True,
    "navigation_expanded": True,
}

JAZZMIN_UI_TWEAKS = {
    "theme": "darkly",
    "dark_mode_theme": "darkly",
    "navbar": "navbar-dark navbar-primary",
    "sidebar": "sidebar-dark-primary",
    "brand_colour": "navbar-primary",
    "accent": "accent-primary",
}