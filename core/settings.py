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
    "REFRESH_TOKEN_LIFETIME": timedelta(days=30),
    "ROTATE_REFRESH_TOKENS": False,
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
    }
}


REDIS_HOST = os.getenv("REDIS_HOST", "127.0.0.1")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
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
    "site_title": "Jojo Admin",
    "site_header": "Jojo Admin",
    "site_brand": "Jojo",
    "welcome_sign": "Jojo Admin Panel",
    "copyright": "Jojo App",

    "show_sidebar": True,
    "navigation_expanded": True,

    "topmenu_links": [
        {"name": "Dashboard", "url": "admin:index", "permissions": ["auth.view_group"]},
        {"name": "API Docs", "url": "/swagger/", "new_window": True},
    ],

    "icons": {
        "parent.User": "fas fa-users",
        "parent.OTPCode": "fas fa-key",
        "parent.PairingCode": "fas fa-qrcode",
        "parent.ParentChild": "fas fa-child",

        "parent.ChildLocation": "fas fa-map-marker-alt",
        "parent.ChildLastLocation": "fas fa-location-arrow",
        "parent.SavedLocation": "fas fa-map-pin",

        "parent.SafeRoute": "fas fa-route",
        "parent.SafeRoutePoint": "fas fa-map-signs",
        "parent.ChildRouteAssignment": "fas fa-road",
        "parent.RouteAlert": "fas fa-exclamation-triangle",

        "parent.DeviceToken": "fas fa-mobile-alt",

        "parent.GameCategory": "fas fa-gamepad",
        "parent.GameItem": "fas fa-puzzle-piece",

        "parent.ShopCategory": "fas fa-store",
        "parent.ShopItem": "fas fa-shopping-bag",
        "parent.ShopPurchase": "fas fa-receipt",

        "parent.ChildWallet": "fas fa-wallet",
        "parent.ChildTransaction": "fas fa-coins",

        "parent.SOSAlert": "fas fa-bell",
        "auth.Group": "fas fa-user-shield",
    },

    "order_with_respect_to": [
        "parent.User",
        "parent.ParentChild",
        "parent.PairingCode",

        "parent.GameCategory",
        "parent.GameItem",

        "parent.ShopCategory",
        "parent.ShopItem",
        "parent.ShopPurchase",

        "parent.ChildWallet",
        "parent.ChildTransaction",

        "parent.ChildLocation",
        "parent.ChildLastLocation",
        "parent.SavedLocation",

        "parent.SafeRoute",
        "parent.ChildRouteAssignment",
        "parent.RouteAlert",

        "parent.SOSAlert",
        "parent.DeviceToken",
    ],

    "hide_apps": [],
    "hide_models": [],
}


JAZZMIN_UI_TWEAKS = {
    "theme": "flatly",
    "dark_mode_theme": "darkly",
    "navbar": "navbar-white navbar-light",
    "sidebar": "sidebar-dark-primary",
    "brand_colour": "navbar-primary",
    "accent": "accent-primary",
    "button_classes": {
        "primary": "btn-primary",
        "secondary": "btn-secondary",
        "info": "btn-info",
        "warning": "btn-warning",
        "danger": "btn-danger",
        "success": "btn-success",
    },
}