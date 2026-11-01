from pathlib import Path
import os
import logging
import base64

from dotenv import load_dotenv

# ============================================================
# RUTAS Y VARIABLES DE ENTORNO
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


def env_bool(name, default=False):
    """Convierte una variable de entorno en un booleano."""
    value = os.getenv(name)

    if value is None:
        return default

    return value.strip().lower() in {"true", "1", "yes", "on"}


def env_list(name, default=""):
    """Convierte una variable separada por comas en una lista."""
    return [
        item.strip() for item in os.getenv(name, default).split(",") if item.strip()
    ]


# ============================================================
# SEGURIDAD Y ENTORNO
# ============================================================

DJANGO_ENV = os.getenv("DJANGO_ENV", "development").strip().lower()
IS_PRODUCTION = DJANGO_ENV == "production"

SECRET_KEY = os.getenv("SECRET_KEY", "")

if not SECRET_KEY:
    raise ValueError("Debes configurar SECRET_KEY en las variables de entorno.")

if IS_PRODUCTION and len(SECRET_KEY) < 50:
    raise ValueError("SECRET_KEY debe tener al menos 50 caracteres en producción.")

DEBUG = env_bool("DEBUG", default=not IS_PRODUCTION)

if IS_PRODUCTION and DEBUG:
    raise ValueError("DEBUG no puede estar activado en producción.")


ALLOWED_HOSTS = env_list(
    "ALLOWED_HOSTS",
    "localhost,127.0.0.1,[::1]",
)

if IS_PRODUCTION and not ALLOWED_HOSTS:
    raise ValueError("Debes configurar ALLOWED_HOSTS en producción.")


# Render proporciona el hostname del servicio automáticamente.
RENDER_EXTERNAL_HOSTNAME = os.getenv("RENDER_EXTERNAL_HOSTNAME")

if RENDER_EXTERNAL_HOSTNAME:
    if RENDER_EXTERNAL_HOSTNAME not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)


CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS")

if RENDER_EXTERNAL_HOSTNAME:
    render_origin = f"https://{RENDER_EXTERNAL_HOSTNAME}"

    if render_origin not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(render_origin)


# ============================================================
# APLICACIONES
# ============================================================

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "apps.core",
    "apps.catalog",
    "apps.cart",
    "apps.orders",
    "apps.accounts",
]


# ============================================================
# MIDDLEWARE
# ============================================================

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # Debe ir inmediatamente después de SecurityMiddleware.
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]


# ============================================================
# URLS, PLANTILLAS Y WSGI
# ============================================================

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# ============================================================
# BASE DE DATOS MYSQL
# ============================================================

DB_NAME = os.getenv("DB_NAME", "")
DB_USER = os.getenv("DB_USER", "")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "3306")

DB_SSL_CA = os.getenv("DB_SSL_CA", "").strip()
DB_SSL_CA_B64 = os.getenv("DB_SSL_CA_B64", "").strip()

if DB_SSL_CA_B64:
    try:
        certificate_data = base64.b64decode(
            DB_SSL_CA_B64,
            validate=True,
        )

        DB_SSL_CA = "/tmp/aiven-ca.pem"
        Path(DB_SSL_CA).write_bytes(certificate_data)

    except (ValueError, OSError) as error:
        raise ValueError("No se pudo procesar el certificado CA de Aiven.") from error

elif DB_SSL_CA and not Path(DB_SSL_CA).is_absolute():
    DB_SSL_CA = str(BASE_DIR / DB_SSL_CA)


if not all([DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT]):
    raise ValueError(
        "Debes configurar DB_NAME, DB_USER, DB_PASSWORD, " "DB_HOST y DB_PORT."
    )


DATABASE_OPTIONS = {
    "charset": "utf8mb4",
    "connect_timeout": 10,
}


if DB_SSL_CA:
    if not Path(DB_SSL_CA).is_file():
        raise ValueError(f"No se encontró el certificado CA: {DB_SSL_CA}")

    DATABASE_OPTIONS["ssl"] = {
        "ca": DB_SSL_CA,
    }

elif IS_PRODUCTION:
    raise ValueError(
        "En producción debes configurar DB_SSL_CA "
        "o DB_SSL_CA_B64 con el certificado CA de Aiven."
    )


DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": DB_NAME,
        "USER": DB_USER,
        "PASSWORD": DB_PASSWORD,
        "HOST": DB_HOST,
        "PORT": DB_PORT,
        "OPTIONS": DATABASE_OPTIONS,
        # Evita mantener conexiones persistentes en este
        # proyecto pequeño con recursos gratuitos limitados.
        "CONN_MAX_AGE": 0,
    }
}


# ============================================================
# VALIDACIÓN DE CONTRASEÑAS
# ============================================================

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "UserAttributeSimilarityValidator"
        ),
    },
    {
        "NAME": ("django.contrib.auth.password_validation." "MinimumLengthValidator"),
    },
    {
        "NAME": ("django.contrib.auth.password_validation." "CommonPasswordValidator"),
    },
    {
        "NAME": ("django.contrib.auth.password_validation." "NumericPasswordValidator"),
    },
]


# ============================================================
# INTERNACIONALIZACIÓN
# ============================================================

LANGUAGE_CODE = "es-pe"

TIME_ZONE = "America/Lima"

USE_I18N = True

USE_TZ = True


# ============================================================
# ARCHIVOS ESTÁTICOS
# ============================================================

STATIC_URL = "static/"

# Archivos originales de CSS, JavaScript e imágenes.
STATICFILES_DIRS = [
    BASE_DIR / "static",
]

# Destino de collectstatic; no es la carpeta de origen.
STATIC_ROOT = BASE_DIR / "staticfiles"

# WhiteNoise comprime los archivos y genera nombres
# versionados para favorecer la caché del navegador.
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": ("whitenoise.storage.CompressedManifestStaticFilesStorage"),
    },
}


# ============================================================
# SEGURIDAD ADICIONAL EN PRODUCCIÓN
# ============================================================

if IS_PRODUCTION:

    # Render termina HTTPS en su proxy.
    SECURE_PROXY_SSL_HEADER = (
        "HTTP_X_FORWARDED_PROTO",
        "https",
    )

    # Redirigir todas las solicitudes HTTP a HTTPS.
    SECURE_SSL_REDIRECT = True

    # Cookies transmitidas únicamente mediante HTTPS.
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

    # Protección adicional de cabeceras HTTP.
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = "same-origin"
    X_FRAME_OPTIONS = "DENY"

    # HSTS inicial de una hora.
    # Ampliarlo después de verificar HTTPS y el dominio.
    SECURE_HSTS_SECONDS = 3600
    SECURE_HSTS_INCLUDE_SUBDOMAINS = False
    SECURE_HSTS_PRELOAD = False

    # No permitir que el navegador interprete contenido
    # servido con tipos MIME incorrectos.
    SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"


# ============================================================
# AUTENTICACIÓN
# ============================================================

LOGIN_URL = "accounts:login"

LOGIN_REDIRECT_URL = "core:home"

LOGOUT_REDIRECT_URL = "accounts:login"


# ============================================================
# LOGGING
# ============================================================

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": ("{levelname} {asctime} {name} {message}"),
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}


# ============================================================
# MODELOS
# ============================================================

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
