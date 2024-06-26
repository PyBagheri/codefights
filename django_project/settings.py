"""
Django settings for codefights project.

Generated by 'django-admin startproject' using Django 5.0.2.

For more information on this file, see
https://docs.djangoproject.com/en/5.0/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/5.0/ref/settings/
"""

from pathlib import Path
import importlib
import os

from games.frontend import GAMES_TEMPLATES_DIRS, GAMES_STATIC_DIRS


os.environ.setdefault('GLOBAL_CONFIG_MODULE', 'config')

global_config = importlib.import_module(
    os.environ.get('GLOBAL_CONFIG_MODULE')
)



def get_secret(secret_name, mode='r'):
    path = Path(f'/run/secrets/{secret_name}')
    
    if path.is_file():
        with open(path, mode) as f:
            return f.read()

    # Fallback to environment variables. This is so that
    # one can run this django project without docker too.
    return os.environ.get(secret_name)



# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent



# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = get_secret('DJANGO_SECRET_KEY')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = global_config.DEBUG

ALLOWED_HOSTS = global_config.ALLOWED_HOSTS

CSRF_TRUSTED_ORIGINS = global_config.CSRF_TRUSTED_ORIGINS


ADMIN_URL = global_config.ADMIN_URL


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Local apps
    'accounts',
    'pages',
    'fights',
    'gamespecs',
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

ROOT_URLCONF = 'django_project.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates', *[BASE_DIR / d for d in GAMES_TEMPLATES_DIRS]],
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

WSGI_APPLICATION = 'django_project.wsgi.application'


# Database
# https://docs.djangoproject.com/en/5.0/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': global_config.POSTGRES['DATABASE_NAME'],
        'USER': global_config.POSTGRES['USER'],
        'PASSWORD': get_secret('POSTGRES_PASSWORD'),
        'HOST': global_config.POSTGRES['HOST'],
        'PORT': global_config.POSTGRES['PORT'],
    }
}


# Password validation
# https://docs.djangoproject.com/en/5.0/ref/settings/#auth-password-validators

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
# https://docs.djangoproject.com/en/5.0/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


DEFAULT_FROM_EMAIL = global_config.DEFAULT_FROM_EMAIL


EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = global_config.EMAIL_HOST
EMAIL_PORT = global_config.EMAIL_PORT
EMAIL_HOST_USER = global_config.EMAIL_HOST_USER
EMAIL_HOST_PASSWORD = get_secret('EMAIL_HOST_PASSWORD')
EMAIL_USE_TLS = True


# Minutes until the verification link sent to the email is expired.
EMAIL_VERIFICATION_EXPIRY_MINUTES = 15


AUTHENTICATION_BACKENDS = ['accounts.backends.UsernameOrEmailBackend']


# The frontend.py module inside the games root package.
# The games package must be either a docker volume in a
# container or on the host machine itself. This is so that
# we can run the project without docker too.
GAMES_FRONTEND_MODULE = 'games.frontend'


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.0/howto/static-files/

STATIC_URL = global_config.STATIC_URL

STATICFILES_DIRS = [BASE_DIR / 'static', *[BASE_DIR / d for d in GAMES_STATIC_DIRS]]

# Must be either a docker volume in a container or
# on the host machine itself. This is so that we can
# run the project without docker too.
#
# This is useful for using manage.py collectstatic;
# Django will not be serving static files.
STATIC_ROOT = global_config.STATIC_ROOT



# Default primary key field type
# https://docs.djangoproject.com/en/5.0/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'



USERNAME_MIN_LENGTH = 5

AUTH_USER_MODEL = 'accounts.User'


MEDIA_URL = global_config.MEDIA_URL

# Must be either a docker volume in a container or
# on the host machine itself. This is so that we can
# run the project without docker too.
MEDIA_ROOT = global_config.MEDIA_ROOT


MAX_CODE_UPLOAD_SIZE = 100000  # in bytes

MAX_USER_ATTENDED_FIGHTS = 1


# If the "Origin" header is not present in an HTTPS request,
# the CSRF middleware requires the "Referrer" header. So, 
# instead of completely aborting the "Referrer" header, we 
# just include them for the same-origin situation.
#
# Currently, we have implemented the WebSocket handling
# manually, but still use Django's CSRF middleware. So
# this also applies to the WebSockets for us.
SECURE_REFERRER_POLICY = 'same-origin'

# Custom settings entry.
WEBSOCKET_ROOT_URLCONF = 'django_project.websocket.urls'


REDIS_SERVER_URL = global_config.REDIS_SERVER_URL

REDIS_SIMULATOR_STREAM = global_config.REDIS_SIMULATOR_STREAM


LOGGING_ROOT = global_config.LOGGING_ROOT
LOGGING_FILES_PATHS = global_config.LOGGING_FILES_PATHS


# These are relative to the MEDIA_ROOT.
FIGHT_CODES_DIR = Path(global_config.FIGHT_CODES_DIR)
PRESET_CODES_DIR = Path(global_config.PRESET_CODES_DIR)
TEMPLATE_CODES_DIR = Path(global_config.TEMPLATE_CODES_DIR)
