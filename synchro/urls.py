# flake8: noqa
from __future__ import absolute_import
from django.conf.urls import url

from .views import synchro


urlpatterns = (
    url(r'^$', synchro, name='synchro'),
)
