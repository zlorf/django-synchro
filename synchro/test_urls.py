from django.contrib import admin
from django.conf.urls.defaults import patterns, url, include


urlpatterns = patterns('',
    url(r'^admin/', include(admin.site.urls)),
    url(r'^synchro/', include('synchro.urls')),
)
