from django.urls import path, re_path

from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('live/', views.activity_all, {'page': 'all_activities'}, name="activity-all"),
    path('live/iframe', views.activity_all_iframe, name="activity-all-iframe"),
    path('landing-page/', views.activity_all, {'page': 'landing_page'}, name="landing-page"),
]
