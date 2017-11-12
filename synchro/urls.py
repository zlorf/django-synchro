# flake8: noqa
from django.conf.urls import url

from views import synchro


urlpatterns = (
    url(r'^$', synchro, name='synchro'),
)
