from django.conf.urls.defaults import patterns, url

from views import synchro


urlpatterns = patterns('',
    url(r'^$', synchro, name='synchro'),
)
