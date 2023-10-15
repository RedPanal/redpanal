from django.urls import path, re_path
from django.conf import settings
from django.conf.urls.static import static

from . import views

urlpatterns = [
    path('upload/', views.audio_upload, name='audio-create'),
    #url(r'^list/$', "list", name='audio-list',
    re_path(r'^(?P<slug>[\w-]+)/$', views.AudioDetailView.as_view(), name='audio-detail'),
    re_path(r'^(?P<slug>[\w-]+)/edit/$', views.audio_create_update, name='audio-edit'),
    re_path(r'^(?P<slug>[\w-]+)/delete/$', views.AudioDeleteView.as_view(), name='audio-delete'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
