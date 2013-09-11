from django.conf.urls import patterns, include, url
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = patterns('redpanal.users.views',
    url(r'^people/$', "user_list", name='user-list'),
    url(r'^(?P<slug>[\w-]+)/$', 'user_page', name="user-page"),
    url(r'^(?P<slug>[\w-]+)/interactions/$', 'user_interactions',
        name="user-interactions"),
)
