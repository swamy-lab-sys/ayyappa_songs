import os
from pathlib import Path
from dotenv import load_dotenv
import dj_database_url
import socket

# -----------------------------
# 🔹 Load Environment Variables
# -----------------------------
load_dotenv()

# -----------------------------
# 🔹 Basic Config
# -----------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-fallback-secret-key")

DEBUG = os.environ.get("DEBUG", "True").lower() == "true"
ALLOWED_HOSTS = ["*"]

# -----------------------------
# 🔹 Installed Apps
# -----------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",  # 3rd party
    "songs",           # Local app
]

# -----------------------------
# 🔹 Middleware
# -----------------------------
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# -----------------------------
# 🔹 URL & WSGI
# -----------------------------
ROOT_URLCONF = "singersite.urls"
WSGI_APPLICATION = "singersite.wsgi.application"

# -----------------------------
# 🔹 Templates
# -----------------------------
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# -----------------------------
# 🔹 Database Configuration (Dual)
# -----------------------------
# 1️⃣ Prefer Render PostgreSQL (production or local CRUD access)
# 2️⃣ Fallback to SQLite if DATABASE_URL not found

DATABASE_URL = os.environ.get("DATABASE_URL")

if DATABASE_URL:
    print("🌐 Using Render PostgreSQL database")
    DATABASES = {
        "default": dj_database_url.config(
            default=DATABASE_URL,
            conn_max_age=600,
            ssl_require=True,
        )
    }
else:
    print("💻 Using local SQLite database")
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

# -----------------------------
# 🔹 Password Validation
# -----------------------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# -----------------------------
# 🔹 Localization
# -----------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

# -----------------------------
# 🔹 Static & Media Files
# -----------------------------
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# ✅ Media files
MEDIA_URL = "/media/"
MEDIA_ROOT = (
    "/opt/render/project/src/media"
    if os.environ.get("RENDER")
    else BASE_DIR / "media"
)

# -----------------------------
# 🔹 REST Framework
# -----------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticatedOrReadOnly",
    ],
}

# -----------------------------
# 🔹 Authentication Redirects
# -----------------------------
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "song_list"
LOGOUT_REDIRECT_URL = "login"

# -----------------------------
# 🔹 Security for Render
# -----------------------------
CSRF_TRUSTED_ORIGINS = [
    "https://*.onrender.com",
    "https://ayyappa-songs.onrender.com",
]
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# -----------------------------
# 🔹 Defaults
# -----------------------------
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# -----------------------------
# 🔹 Debug Info
# -----------------------------
if DEBUG:
    print("⚙️ Running in DEBUG mode — local environment active")
else:
    print("🚀 Running in PRODUCTION mode — Render environment active")
