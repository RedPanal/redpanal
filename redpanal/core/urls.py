from django.urls import path

from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('live/', views.activity_all, name="activity-all"),
    path('live/iframe', views.activity_all_iframe, name="activity-all-iframe"),
]
