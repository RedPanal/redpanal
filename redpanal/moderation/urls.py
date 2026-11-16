from django.urls import path

from . import views

urlpatterns = [
    path('', views.panel, name='moderation-panel'),
    path('reporte/<int:pk>/', views.decide, name='moderation-decide'),
    path('reportar/<str:kind>/<int:pk>/', views.report_create, name='report-create'),
]
