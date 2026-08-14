import os
from pathlib import Path
try:
    import dj_database_url  # type: ignore[import]
except Exception:
    dj_database_url = None

# dotenv may not be available in all environments (e.g., some linters or minimal containers)
try:
    from dotenv import load_dotenv  # type: ignore[import]
except Exception:
    # Provide a no-op fallback so settings load without the package installed.
    def load_dotenv(*args, **kwargs):
        return None

# -----------------------------------------
# ✅ Load environment variables
# -----------------------------------------
load_dotenv()  # Load from .env file (local only)

BASE_DIR = Path(__file__).resolve().parent.parent

# -----------------------------------------
# 🔒 Security Settings
# -----------------------------------------
SECRET_KEY = os.getenv('SECRET_KEY', 'unsafe-secret-key-for-local')
DEBUG = os.getenv('DEBUG', 'False') == 'True'
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', '.onrender.com,127.0.0.1,localhost').split(',')
# Production-only security settings
if not DEBUG:
    SECURE_SSL_REDIRECT = os.getenv('SECURE_SSL_REDIRECT', 'True') == 'True'
    SESSION_COOKIE_SECURE = os.getenv('SESSION_COOKIE_SECURE', 'True') == 'True'
    CSRF_COOKIE_SECURE = os.getenv('CSRF_COOKIE_SECURE', 'True') == 'True'
    SECURE_HSTS_SECONDS = int(os.getenv('SECURE_HSTS_SECONDS', '31536000'))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    CSRF_TRUSTED_ORIGINS = os.getenv('CSRF_TRUSTED_ORIGINS', 'https://*.onrender.com').split(',')

SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

# -----------------------------------------
# ⚙️ Installed Apps
# -----------------------------------------
INSTALLED_APPS = [
    'jazzmin',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Local apps
    'accounts',
    'academics',
    'attendance',
    'finance',
    'reportcard',
    'communications',
    'results',
    'core',
]

# -----------------------------------------
# 🧱 Middleware
# -----------------------------------------
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # Serve static files
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'SMS.urls'

# -----------------------------------------
# 🖼 Templates
# -----------------------------------------
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'SMS.wsgi.application'

# -----------------------------------------
# 🗃️ Database Configuration (Auto Switch)
# -----------------------------------------
DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL and dj_database_url:
    # Use PostgreSQL (Render)
    DATABASES = {
        "default": dj_database_url.config(default=DATABASE_URL, conn_max_age=600, ssl_require=True)
    }
else:
    # Default to SQLite locally
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

# -----------------------------------------
# 👥 Authentication
# -----------------------------------------
AUTH_USER_MODEL = "accounts.CustomUser"

LOGIN_URL = '/accounts/login/'
LOGOUT_REDIRECT_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/accounts/dashboard/'

# -----------------------------------------
# 📧 Email Configuration
# -----------------------------------------
EMAIL_BACKEND = os.getenv('EMAIL_BACKEND', 'django.core.mail.backends.smtp.EmailBackend')
EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', '587'))
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'True') == 'True'
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', EMAIL_HOST_USER)

# -----------------------------------------
# 🗂 Static & Media Files
# -----------------------------------------
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# WhiteNoise — for serving static files in production
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# -----------------------------------------
# 🌍 Timezone / Language
# -----------------------------------------
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Accra'
USE_I18N = True
USE_TZ = True

# -----------------------------------------
# 🔍 Logging
# -----------------------------------------
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': os.getenv('DJANGO_LOG_LEVEL', 'INFO'),
    },
}

# -----------------------------------------
# 🔄 Proxy Settings (for Render)
# -----------------------------------------
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# -----------------------------------------
# ⚡ Channels / ASGI (Optional)
# -----------------------------------------
ASGI_APPLICATION = "SMS.asgi.application"
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [(os.getenv("REDIS_URL", "127.0.0.1"), 6379)],
        },
    },
}

# -----------------------------------------
# 🌐 Site URL
# -----------------------------------------
SITE_URL = os.getenv("SITE_URL", "http://127.0.0.1:8000")

# -----------------------------------------
# 🎨 Django Jazzmin Admin Theme
# -----------------------------------------
JAZZMIN_SETTINGS = {
    "site_title": "SMS Admin Portal",
    "site_header": "School Management System",
    "site_brand": "SMS Portal",
    "site_logo": "img/logo.png",
    "site_logo_classes": "img-fluid",
    "login_logo": "img/logo.png",
    "welcome_sign": "Welcome to the School Management System",
    "copyright": "School Management System",
    "search_model": [
        "accounts.CustomUser",
        "accounts.Student",
        "accounts.Teacher",
        "academics.ClassRoom",
        "academics.Subject",
    ],
    "topmenu_links": [
        {"name": "Dashboard", "url": "admin:index", "permissions": ["view"], "icon": "fas fa-tachometer-alt"},
        {"name": "View Site", "url": "/", "icon": "fas fa-globe", "new_window": True},
    ],
    "show_sidebar": True,
    "navigation_expanded": True,
    "order_with_respect_to": [
        "accounts", "academics", "attendance", "finance",
        "results", "reportcard", "communications", "core", "auth",
    ],
    "icons": {
        "accounts": "fas fa-users-cog",
        "accounts.CustomUser": "fas fa-user",
        "accounts.Admin": "fas fa-user-shield",
        "accounts.Teacher": "fas fa-chalkboard-teacher",
        "accounts.Student": "fas fa-user-graduate",
        "accounts.Accountant": "fas fa-calculator",
        "accounts.Parent": "fas fa-user-friends",
        "academics": "fas fa-book-open",
        "academics.ClassRoom": "fas fa-door-open",
        "academics.Subject": "fas fa-book",
        "academics.Enrollment": "fas fa-user-plus",
        "attendance": "fas fa-clipboard-check",
        "attendance.AttendanceSession": "fas fa-calendar-check",
        "attendance.AttendanceRecord": "fas fa-check-double",
        "finance": "fas fa-coins",
        "finance.FeeType": "fas fa-tag",
        "finance.StudentFeeRecord": "fas fa-file-invoice-dollar",
        "finance.Payment": "fas fa-credit-card",
        "finance.Invoice": "fas fa-file-invoice",
        "finance.FinanceSummary": "fas fa-chart-pie",
        "finance.Session": "fas fa-calendar-alt",
        "finance.BulkFeeAssignment": "fas fa-layer-group",
        "results": "fas fa-poll",
        "results.ResultRecord": "fas fa-file-alt",
        "results.ResultSummary": "fas fa-chart-bar",
        "reportcard": "fas fa-file-pdf",
        "reportcard.ReportCard": "fas fa-scroll",
        "communications": "fas fa-comments",
        "communications.Conversation": "fas fa-comment-dots",
        "communications.Message": "fas fa-envelope",
        "communications.Attachment": "fas fa-paperclip",
        "communications.MessageFlag": "fas fa-flag",
        "core": "fas fa-bullhorn",
        "core.SiteUpdate": "fas fa-newspaper",
        "auth": "fas fa-user-lock",
        "auth.Group": "fas fa-users",
    },
    "related_modal_active": True,
    "show_ui_builder": False,
    "changeform_format": "horizontal_tabs",
    "use_google_fonts_cdn": True,
}

JAZZMIN_UI_TWEAKS = {
    "accent": "accent-primary",
    "navbar": "navbar-dark navbar-primary",
    "sidebar": "sidebar-dark-primary",
    "sidebar_nav_compact_style": True,
    "theme": "default",
    "button_classes": {
        "primary": "btn-primary",
        "secondary": "btn-secondary",
        "info": "btn-info",
        "warning": "btn-warning",
        "danger": "btn-danger",
        "success": "btn-success",
    },
}
