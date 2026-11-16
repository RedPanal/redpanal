"""A person's pages, at the root: redpanal.org/<username>/. Included last, after every other route."""
from django.urls import re_path

from social.views import person_follow
from . import views

USERNAME = r'(?P<username>[\w.@+-]+)'

urlpatterns = [
    re_path(r'^%s/$' % USERNAME, views.user_tracks, name="user-tracks"),
    re_path(r'^%s/seguir/$' % USERNAME, person_follow, name="person-follow"),
    re_path(r'^%s/menciones/$' % USERNAME, views.user_interactions, name="user-interactions"),
    re_path(r'^%s/actividad/$' % USERNAME, views.user_activities, name="user-activities"),
    re_path(r'^%s/proyectos/$' % USERNAME, views.user_projects, name="user-projects"),
]
