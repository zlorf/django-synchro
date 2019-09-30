# flake8: noqa
from __future__ import absolute_import
from django.contrib import admin
from django.conf.urls import url, include


urlpatterns = (
    url(r'^admin/', include(admin.site.urls)),
    url(r'^synchro/', include('synchro.urls')),
)
