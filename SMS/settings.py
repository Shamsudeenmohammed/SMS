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
DEBUG = os.getenv('DEBUG', 'True') == 'True'
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', '127.0.0.1,localhost').split(',')

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
    'library',
    'inventory',
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
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = "smtp.gmail.com"
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.getenv("mohammedshamsudeen310@gmail.com")
EMAIL_HOST_PASSWORD = os.getenv("vsgl irge nkax rqdn")  # Use app password for Gmail
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER

# -----------------------------------------
# 🗂 Static & Media Files
# -----------------------------------------
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# WhiteNoise — for serving static files in production
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# -----------------------------------------
# 🌍 Timezone / Language
# -----------------------------------------
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

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
