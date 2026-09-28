"""
Django settings for CantinaOS project.

Environment-based configuration:
- Development: DEBUG=True, SQLite, console email
- Production: DEBUG=False, PostgreSQL, env-based secrets

Controlled via environment variables:
- DJANGO_DEBUG (default: True)
- DJANGO_SECRET_KEY (required in production)
- ALLOWED_HOSTS (comma-separated, required in production)
- CSRF_TRUSTED_ORIGINS (comma-separated, required in production)
- DATABASE_URL or individual DB_* vars (for production PostgreSQL)
"""

from pathlib import Path
import os

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# =============================================================================
# CORE SETTINGS
# =============================================================================

# SECURITY WARNING: keep the secret key used in production secret!
# In development, use a default. In production, MUST be set via env var.
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'django-insecure-dev-key-change-in-production')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get('DJANGO_DEBUG', 'True').lower() == 'true'

# ALLOWED_HOSTS - comma-separated list
# Default for development
_allowed_hosts = os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1,0.0.0.0,testserver')
ALLOWED_HOSTS = [h.strip() for h in _allowed_hosts.split(',') if h.strip()]

# CSRF trusted origins - comma-separated
_csrf_origins = os.environ.get('CSRF_TRUSTED_ORIGINS', '')
CSRF_TRUSTED_ORIGINS = [o.strip() for o in _csrf_origins.split(',') if o.strip()] if _csrf_origins else []


# =============================================================================
# APPLICATION DEFINITION
# =============================================================================

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'frontend',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
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

WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'


# =============================================================================
# DATABASE
# =============================================================================

# Default: SQLite for development
# Production: Use PostgreSQL via DATABASE_URL or individual DB_* vars
DATABASE_URL = os.environ.get('DATABASE_URL')

if DATABASE_URL:
    # Parse DATABASE_URL (format: postgres://user:pass@host:port/dbname)
    import urllib.parse
    url = urllib.parse.urlparse(DATABASE_URL)
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': url.path[1:],
            'USER': url.username,
            'PASSWORD': url.password,
            'HOST': url.hostname,
            'PORT': url.port or 5432,
            'CONN_MAX_AGE': 60,
            'OPTIONS': {'connect_timeout': 10},
        }
    }
else:
    # Individual DB settings (for production without DATABASE_URL)
    db_engine = os.environ.get('DB_ENGINE', 'django.db.backends.sqlite3')
    
    if db_engine == 'django.db.backends.postgresql':
        DATABASES = {
            'default': {
                'ENGINE': 'django.db.backends.postgresql',
                'NAME': os.environ.get('DB_NAME', 'cantinaos'),
                'USER': os.environ.get('DB_USER', 'cantinaos'),
                'PASSWORD': os.environ.get('DB_PASSWORD', ''),
                'HOST': os.environ.get('DB_HOST', 'localhost'),
                'PORT': os.environ.get('DB_PORT', '5432'),
                'CONN_MAX_AGE': 60,
                'OPTIONS': {'connect_timeout': 10},
            }
        }
    else:
        # SQLite (development)
        DATABASES = {
            'default': {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': BASE_DIR / 'db.sqlite3',
            }
        }


# =============================================================================
# PASSWORD VALIDATION
# =============================================================================

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Disable validators in development for easier testing
if DEBUG:
    AUTH_PASSWORD_VALIDATORS = []


# =============================================================================
# INTERNATIONALIZATION
# =============================================================================

LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Sao_Paulo'
USE_I18N = True
USE_TZ = True


# =============================================================================
# STATIC & MEDIA FILES
# =============================================================================

STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Use manifest storage in production for cache busting
if not DEBUG:
    STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.ManifestStaticFilesStorage'
else:
    STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'


# =============================================================================
# DEFAULT PRIMARY KEY
# =============================================================================

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# =============================================================================
# AUTH / LOGIN
# =============================================================================

LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_REDIRECT_URL = '/login/'


# =============================================================================
# SECURITY SETTINGS
# =============================================================================

# Base security (always on)
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = 'DENY'
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = 'Lax'

# Production-only security
if not DEBUG:
    # Require environment variables for production
    if not SECRET_KEY or SECRET_KEY.startswith('django-insecure-'):
        raise ValueError('DJANGO_SECRET_KEY must be set in production')
    
    if not ALLOWED_HOSTS:
        raise ValueError('ALLOWED_HOSTS must be set in production')
    
    if not CSRF_TRUSTED_ORIGINS:
        raise ValueError('CSRF_TRUSTED_ORIGINS must be set in production')
    
    # HTTPS enforcement
    SECURE_SSL_REDIRECT = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_HSTS_SECONDS = 31536000  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_SAMESITE = 'None'
    CSRF_COOKIE_SECURE = True
    CSRF_COOKIE_SAMESITE = 'None'


# =============================================================================
# EMAIL
# =============================================================================

if DEBUG:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
else:
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST = os.environ.get('EMAIL_HOST', 'localhost')
    EMAIL_PORT = int(os.environ.get('EMAIL_PORT', '587'))
    EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'True').lower() == 'true'
    EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
    EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
    DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'noreply@cantinaos.local')


# =============================================================================
# LOGGING
# =============================================================================

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'simple' if not DEBUG else 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO' if DEBUG else 'WARNING',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO' if DEBUG else 'WARNING',
            'propagate': False,
        },
        'django.request': {
            'handlers': ['console'],
            'level': 'ERROR',
            'propagate': False,
        },
        'frontend': {
            'handlers': ['console'],
            'level': 'DEBUG' if DEBUG else 'INFO',
            'propagate': False,
        },
    },
}