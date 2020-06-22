from django.conf.urls import include, url

from .views import ProjectDetailView, ProjectCreateView, ProjectUpdateView, \
                   ProjectDeleteView, ProjectListView, create_version, \
                   download_mix


urlpatterns = [
    url(r'^create/$', ProjectCreateView.as_view(), name='project-create'),
    url(r'^list/$', ProjectListView.as_view(), name='project-list'),
    url(r'^(?P<slug>[\w-]+)/$', ProjectDetailView.as_view(), name='project-detail'),
    url(r'^(?P<slug>[\w-]+)/edit/$', ProjectUpdateView.as_view(), name='project-edit'),
    url(r'^(?P<slug>[\w-]+)/delete/$', ProjectDeleteView.as_view(), name='project-delete'),
    url(r'^(?P<slug>[\w-]+)/create-version/$', create_version, name='project-create-version'),
    url(r'^(?P<slug>[\w-]+)/download-mix/$', download_mix, name='project-download-mix'),
]
