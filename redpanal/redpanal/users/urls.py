from django.conf.urls import patterns, include, url
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = patterns('redpanal.users.views',
    url(r'^people/$', "all_people", name='all-people'),
    url(r'^(?P<username>[\w.@+-]+)/$', 'user_page', name="user-page"),
    url(r'^(?P<username>[\w.@+-]+)/interactions/$', 'user_interactions',
        name="user-interactions"),
    url(r'^(?P<username>[\w.@+-]+)/tracks/$', 'user_tracks',
        name="user-tracks"),
    url(r'^(?P<username>[\w.@+-]+)/projects/$', 'user_projects',
        name="user-projects"),
    url(r'^(?P<username>[\w.@+-]+)/activities/$', 'user_activities',
        name="user-activities"),
)
