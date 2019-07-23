# flake8: noqa
from django.conf.urls import url
from django.urls import path

from .views import synchro


urlpatterns = (
    path('', synchro, name='synchro'),
)
