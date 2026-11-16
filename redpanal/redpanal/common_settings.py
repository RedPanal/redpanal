# Django settings for redpanal project.
import os
PROJECT_PATH = os.path.abspath(os.path.dirname(__file__))

SITE_ID = 1

LANGUAGES = (
    ('es', 'Spanish'),
    ('en', 'English'),
    ('pt', 'Portuguese'),
)

LANGUAGE_CODE = 'es'

# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = True

# If you set this to False, Django will not format dates, numbers and
# calendars according to the current locale.

# If you set this to False, Django will not use timezone-aware datetimes.
USE_TZ = True

LOCALE_PATHS = (
    os.path.join(PROJECT_PATH, 'locale'),
)

DEFAULT_AUTO_FIELD = 'django.db.models.AutoField'

# List of finder classes that know how to find static files in
# various locations.
STATICFILES_FINDERS = (
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
#    'django.contrib.staticfiles.finders.DefaultStorageFinder',
)

MIDDLEWARE = (
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'users.middleware.PersonLanguageMiddleware',
    'allauth.account.middleware.AccountMiddleware',
    # Uncomment the next line for simple clickjacking protection:
    # 'django.middleware.clickjacking.XFrameOptionsMiddleware',
)

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(PROJECT_PATH, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.contrib.auth.context_processors.auth',
                'django.template.context_processors.debug',
                'django.template.context_processors.i18n',
                'django.template.context_processors.media',
                'django.template.context_processors.static',
                'django.template.context_processors.tz',
                'django.contrib.messages.context_processors.messages',
                'django.template.context_processors.request',
                "redpanal.utils.context_processors.git_hash",
                "social.context_processors.notifications",
                "users.context_processors.palette",
                "core.analytics.context",
            ],
        },
    },
]



AUTHENTICATION_BACKENDS = (
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
)

ACCOUNT_SIGNUP_FORM_CLASS = 'redpanal.forms.CustomSignupForm'
# After signing in, Home: what happened in your works. After signing up, the profile: say what you play.
LOGIN_REDIRECT_URL = '/'
ACCOUNT_SIGNUP_REDIRECT_URL = '/ajustes/'

ROOT_URLCONF = 'redpanal.urls'

# Python dotted path to the WSGI application used by Django's runserver.
WSGI_APPLICATION = 'redpanal.wsgi.application'

INSTALLED_APPS = (
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.staticfiles',
    'django.contrib.messages',
    'django.contrib.admin',
    'django.contrib.sitemaps',
    'haystack',
    'core',
    'audio.apps.AudioConfig',
    'project.apps.ProjectConfig',
    'social.apps.SocialConfig',
    'users.apps.UsersConfig',
    'moderation.apps.ModerationConfig',
    'redpanal.utils',
    'taggit',
    'crispy_forms',
    'corsheaders',
    'actstream',
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
    'allauth.socialaccount.providers.twitter',
    'avatar',
#    'django_extensions',
    'el_pagination',
    'easy_thumbnails',
    'rest_framework',
    'widget_tweaks',
    'multiupload',
    "crispy_bootstrap5",
)


ABSOLUTE_URL_OVERRIDES = {
    # People live at the root: redpanal.org/<username>/
    'auth.user': lambda o: __import__("django.urls", fromlist=["reverse"]).reverse("user-tracks", args=[o.username]),
}

ACTSTREAM_SETTINGS = {
    'MANAGER': 'actstream.managers.ActionManager',
    'FETCH_RELATIONS': True,
    'USE_PREFETCH': True,
    'USE_JSONFIELD': False,
}

ACCOUNT_ADAPTER = 'users.account_adapter.MyAccountAdapter'

AVATAR_PROVIDERS = (
    'avatar.providers.PrimaryAvatarProvider',
    'avatar.providers.GravatarAvatarProvider',
    'avatar.providers.DefaultAvatarProvider',
)

SOCIALACCOUNT_PROVIDERS = {
    'google':
        {'SCOPE': ['https://www.googleapis.com/auth/userinfo.profile'],
         'AUTH_PARAMS': {'access_type': 'online'}}
}

CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"

CRISPY_TEMPLATE_PACK = "bootstrap5"

SOUTH_TESTS_MIGRATE = False

HAYSTACK_CONNECTIONS = {
    'default': {
        'ENGINE': 'haystack.backends.whoosh_backend.WhooshEngine',
        'PATH': os.path.join(PROJECT_PATH, 'whoosh_index'),
    },
}

HAYSTACK_SIGNAL_PROCESSOR = 'haystack.signals.RealtimeSignalProcessor'

THUMBNAIL_ALIASES = {
    '': {
        'small': {'size': (50, 50), 'crop': True},
        'medium': {'size': (300, 300), 'crop': True},
    },
}

# Storage each person can use for audio and session files (MB). Identical files count once.
RP_USER_QUOTA_MB = 2000
# Largest single session/attachment file (MB).
RP_ATTACHMENT_MAX_MB = 500

REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.DjangoModelPermissionsOrAnonReadOnly'
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 100,
}

# Visit statistics with Umami, hosted by RedPanal (ESTADISTICAS.md). Empty: off, as in development and tests.
# UMAMI_SCRIPT_URL: the tracker, e.g. https://stats.redpanal.org/script.js; UMAMI_DOMAINS: only count on these hosts.
UMAMI_SCRIPT_URL = os.environ.get("UMAMI_SCRIPT_URL", "")
UMAMI_WEBSITE_ID = os.environ.get("UMAMI_WEBSITE_ID", "")
UMAMI_DOMAINS = os.environ.get("UMAMI_DOMAINS", "")
