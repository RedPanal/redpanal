"""Old addresses under /u/: they keep working, moved permanently to the new ones."""
from django.urls import re_path

from redpanal.utils.redirects import moved

USERNAME = r'(?P<username>[\w.@+-]+)'

urlpatterns = [
    re_path(r'^people/$', moved('all-people')),
    re_path(r'^delete/$', moved('delete-account')),
    re_path(r'^%s/$' % USERNAME, moved('user-tracks')),
    re_path(r'^%s/seguir/$' % USERNAME, moved('person-follow')),
    re_path(r'^%s/interactions/$' % USERNAME, moved('user-interactions')),
    re_path(r'^%s/activities/$' % USERNAME, moved('user-activities')),
    re_path(r'^%s/(?:projects|tracks)/$' % USERNAME, moved('user-tracks')),
]
