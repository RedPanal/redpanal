from django.conf.urls import include, url

from . import views

urlpatterns = [
    url(r'^$', views.index, name='index'),
    url(r'^live/$', views.activity_all, name="activity-all"),
    url(r'^live/iframe$', views.activity_all_iframe, name="activity-all-iframe"),
]
