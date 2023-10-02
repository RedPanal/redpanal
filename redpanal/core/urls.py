from django.conf.urls import include, url

from . import views

urlpatterns = [
    url(r'^$', views.index, name='index'),
    url(r'^live/$', views.activity_all, {'page': 'all_activities'}, name="activity-all"),
    url(r'^live/iframe$', views.activity_all_iframe, name="activity-all-iframe"),
    url(r'^landing-page/$', views.activity_all, {'page': 'landing_page'}, name="landing-page"),
]
