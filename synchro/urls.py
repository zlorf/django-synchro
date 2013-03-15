# flake8: noqa
from django.conf.urls import patterns, url

from views import synchro


urlpatterns = patterns('',
    url(r'^$', synchro, name='synchro'),
)
