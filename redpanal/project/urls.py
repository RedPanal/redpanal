from django.urls import path, re_path

from .views import ProjectDetailView, ProjectCreateView, ProjectUpdateView, \
                   ProjectDeleteView, ProjectListView, create_version, \
                   download_mix


urlpatterns = [
    path('create/', ProjectCreateView.as_view(), name='project-create'),
    path('list/', ProjectListView.as_view(), name='project-list'),
    re_path(r'^(?P<slug>[\w-]+)/$', ProjectDetailView.as_view(), name='project-detail'),
    re_path(r'^(?P<slug>[\w-]+)/edit/$', ProjectUpdateView.as_view(), name='project-edit'),
    re_path(r'^(?P<slug>[\w-]+)/delete/$', ProjectDeleteView.as_view(), name='project-delete'),
    re_path(r'^(?P<slug>[\w-]+)/create-version/$', create_version, name='project-create-version'),
    re_path(r'^(?P<slug>[\w-]+)/download-mix/$', download_mix, name='project-download-mix'),
]
