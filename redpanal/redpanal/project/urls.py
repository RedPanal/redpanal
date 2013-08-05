from django.conf.urls import patterns, include, url

from views import ProjectDetailView, ProjectCreateView, ProjectUpdateView, \
                   ProjectDeleteView, ProjectListView


urlpatterns = patterns('redpanal.project.views',
    url(r'^create/$', ProjectCreateView.as_view(), name='project-create'),
    url(r'^list/$', ProjectListView.as_view(), name='project-list'),
    url(r'^(?P<slug>[\w-]+)/$', ProjectDetailView.as_view(), name='project-detail'),
    url(r'^(?P<slug>[\w-]+)/edit/$', ProjectUpdateView.as_view(), name='project-edit'),
    url(r'^(?P<slug>[\w-]+)/delete/$', ProjectDeleteView.as_view(), name='project-delete'),
)
