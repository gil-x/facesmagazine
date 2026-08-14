"""
Configuration Django du site FACES Magazine.

Toute la configuration variable d'un environnement à l'autre est lue dans
l'environnement (ou dans un fichier .env non versionné à la racine du projet).
Voir .env.example pour la liste des variables et leurs valeurs par défaut.
"""
import sys
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BASE_DIR / 'facesmagazine'

env = environ.Env(
    DJANGO_DEBUG=(bool, False),
    DJANGO_ALLOWED_HOSTS=(list, []),
    DJANGO_CSRF_TRUSTED_ORIGINS=(list, []),
    EMAIL_USE_TLS=(bool, True),
    EMAIL_PORT=(int, 587),
    CONTACT_RECIPIENTS=(list, []),
)
environ.Env.read_env(BASE_DIR / '.env')

DEBUG = env('DJANGO_DEBUG')

# En développement, une clé de repli évite d'avoir à en générer une ;
# en production la variable est obligatoire et l'absence lève une erreur.
if DEBUG:
    SECRET_KEY = env('DJANGO_SECRET_KEY', default='dev-only-insecure-key')
else:
    SECRET_KEY = env('DJANGO_SECRET_KEY')

ALLOWED_HOSTS = env('DJANGO_ALLOWED_HOSTS') or (['localhost', '127.0.0.1'] if DEBUG else [])
CSRF_TRUSTED_ORIGINS = env('DJANGO_CSRF_TRUSTED_ORIGINS')

# URL publique du site, utilisée pour les retours de paiement Stripe.
DOMAIN = env('DJANGO_DOMAIN', default='http://127.0.0.1:8000/')

INSTALLED_APPS = [
    'honeypot',
    'magazine.apps.MagazineConfig',
    'users.apps.UsersConfig',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'facesmagazine.urls'
WSGI_APPLICATION = 'facesmagazine.wsgi.application'

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

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': env('DJANGO_DB_PATH', default=str(BASE_DIR / 'db.sqlite3')),
        'OPTIONS': {
            # Le mode WAL évite les « database is locked » sous charge concurrente.
            'init_command': 'PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL;',
            'transaction_mode': 'IMMEDIATE',
            'timeout': 20,
        },
    }
}

# La base historique a été créée avec des clés primaires AutoField (Django < 3.2).
# Conserver ce réglage évite une migration qui réécrirait toutes les tables.
DEFAULT_AUTO_FIELD = 'django.db.models.AutoField'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

AUTHENTICATION_BACKENDS = [
    'users.accounts.backends.EmailOrUsernameModelBackend',
    'django.contrib.auth.backends.ModelBackend',
]

LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/'

LANGUAGE_CODE = 'fr-fr'
TIME_ZONE = 'Europe/Zurich'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [PROJECT_ROOT / 'static']

MEDIA_URL = '/media/'
MEDIA_ROOT = Path(env('DJANGO_MEDIA_ROOT', default=str(BASE_DIR / 'media')))

# Le stockage à manifeste (noms de fichiers versionnés, mise en cache longue)
# suppose que collectstatic a été exécuté. C'est vrai en production, mais
# l'imposer en développement et pendant les tests n'apporterait rien.
TESTING = 'test' in sys.argv

STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': (
            'django.contrib.staticfiles.storage.StaticFilesStorage'
            if DEBUG or TESTING
            else 'whitenoise.storage.CompressedManifestStaticFilesStorage'
        ),
    },
}

# --- E-mail -----------------------------------------------------------------
# Par défaut les messages sont affichés dans la console : aucun envoi réel
# tant qu'un serveur SMTP n'est pas configuré explicitement.
EMAIL_BACKEND = env(
    'DJANGO_EMAIL_BACKEND',
    default='django.core.mail.backends.console.EmailBackend',
)
EMAIL_HOST = env('EMAIL_HOST', default='localhost')
EMAIL_PORT = env('EMAIL_PORT')
EMAIL_USE_TLS = env('EMAIL_USE_TLS')
EMAIL_HOST_USER = env('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL = env('DEFAULT_FROM_EMAIL', default='info@facesmagazine.ch')
SERVER_EMAIL = DEFAULT_FROM_EMAIL

# Destinataires du formulaire de contact (auparavant codés en dur dans les vues).
CONTACT_RECIPIENTS = env('CONTACT_RECIPIENTS') or ['info@facesmagazine.ch']

# --- Stripe -----------------------------------------------------------------
# La clé publique n'est plus nécessaire : la page de paiement est hébergée
# par Stripe et le site ne charge aucun script Stripe côté navigateur.
STRIPE_SECRET_KEY = env('STRIPE_SECRET_KEY', default='')
STRIPE_WEBHOOK_SECRET = env('STRIPE_WEBHOOK_SECRET', default='')

# --- Sécurité ---------------------------------------------------------------
# Ces réglages n'ont de sens que derrière HTTPS : ils restent inactifs en
# développement pour ne pas casser le serveur local en http.
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {'class': 'logging.StreamHandler'},
    },
    'root': {'handlers': ['console'], 'level': 'INFO'},
    'loggers': {
        'django.request': {'handlers': ['console'], 'level': 'ERROR', 'propagate': False},
    },
}
