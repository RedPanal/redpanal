from django.urls import path, re_path
from django.views.generic import RedirectView

from . import views

home = RedirectView.as_view(pattern_name='index', permanent=False)

urlpatterns = [
    path('', views.index, name='index'),
    # Old activity feed and landing pages: Home now shows what happened in your works.
    path('actividad/', home, name='activity-feed'),
    path('sw.js', views.service_worker, name='service-worker'),
    path('robots.txt', views.robots, name='robots'),
    path('sin-conexion/', views.offline, name='offline'),
    path('live/', home, name="activity-all"),
    path('live/iframe', views.activity_all_iframe, name="activity-all-iframe"),
    path('landing-page/', home, name="landing-page"),
]