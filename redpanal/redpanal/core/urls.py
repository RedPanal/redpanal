from django.conf.urls import patterns, include, url

urlpatterns = patterns('redpanal.core.views',
    url(r'^$', 'index', name='index'),
    url(r'^live/', 'activity_all', name="activity-all"),
)
