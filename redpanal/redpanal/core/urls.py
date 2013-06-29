from django.conf.urls import patterns, include, url

from views import ProjectDetailView, ProjectCreateView, ProjectUpdateView, \
                   ProjectDeleteView


urlpatterns = patterns('redpanal.core.views',
    url(r'^$', 'index', name='index'),
    url(r'^p/create/$', ProjectCreateView.as_view(), name='project-create'),
    url(r'^p/(?P<slug>[\w-]+)/$', ProjectDetailView.as_view(), name='project-detail'),
    url(r'^(?P<slug>[\w-]+)/edit/$', ProjectUpdateView.as_view(), name='project-edit'),
    url(r'^(?P<slug>[\w-]+)/delete/$', ProjectDeleteView.as_view(), name='project-delete'),
)
