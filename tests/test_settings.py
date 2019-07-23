#!/usr/bin/env python
import django
from django.conf import settings
from django.core.management import call_command


SECRET_KEY = 'fake-key'

DEBUG = True

INSTALLED_APPS = (
    # Required contrib apps.
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sites',
    'django.contrib.sessions',
    'django.contrib.messages',
    # Our app and it's test app.
    'dbsettings',
    'synchro',
    'tests',
)

ROOT_URLCONF = 'tests.test_urls'

SITE_ID = 1
SYNCHRO_REMOTE = 'remote_db'
SYNCHRO_MODELS = (
        ('tests', 'testmodel', 'PkModelWithSkip', 'ModelWithKey', 'ModelWithFK', 'A', 'X',
         'M2mModelWithKey', 'M2mAnother', 'M2mModelWithInter', 'M2mSelf', 'ModelWithFKtoKey'),
    )

DATABASES =  {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
        'TEST': {
            'NAME': 'auto_tests',
        }
    },
    'remote_db': {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': ':memory:',
            }
}

MIDDLEWARE = (
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
)

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
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

