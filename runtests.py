#!/usr/bin/env python
import django
from django.conf import settings
from django.core.management import call_command


if not settings.configured:
    settings.configure(
        DATABASES = {
            'default': {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': ':memory:',
            },
            'remote_db': {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': ':memory:',
            }
        },
        INSTALLED_APPS = (
            'django.contrib.admin',
            'django.contrib.auth',
            'django.contrib.contenttypes',
            'django.contrib.sites',
            'django.contrib.sessions',
            'dbsettings',
            'synchro',
        ),
        SITE_ID = 1,
        SYNCHRO_REMOTE = 'remote_db',
        ROOT_URLCONF = 'can be anything - tests override this',
        USE_I18N = True,
        MIDDLEWARE_CLASSES=(
            'django.contrib.sessions.middleware.SessionMiddleware',
            'django.contrib.auth.middleware.AuthenticationMiddleware',
            'django.contrib.messages.middleware.MessageMiddleware',
        ),
    )

if django.VERSION >= (1, 7):
    django.setup()
call_command('test', 'synchro')
