from django.urls import path, re_path
from django.conf import settings
from django.conf.urls.static import static

from . import views

urlpatterns = [
    path('people/', views.all_people, name='all-people'),
    re_path(r'^(?P<username>[\w.@+-]+)/$', views.user_tracks, 
        name="user-tracks"),
    re_path(r'^(?P<username>[\w.@+-]+)/interactions/$', views.user_interactions,
        name="user-interactions"),
    #url(r'^(?P<username>[\w.@+-]+)/tracks/$', views.user_tracks,
    #    name="user-tracks"),
    re_path(r'^(?P<username>[\w.@+-]+)/projects/$', views.user_projects,
        name="user-projects"),
    re_path(r'^(?P<username>[\w.@+-]+)/activities/$', views.user_activities,
        name="user-activities"),
]
