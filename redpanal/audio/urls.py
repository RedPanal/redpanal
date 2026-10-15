from django.urls import path, re_path
from django.conf import settings
from django.conf.urls.static import static
from redpanal.utils.redirects import moved
from . import views

urlpatterns = [
    # Old address: sharing a sound is now the same screen as Crear › A sound to share.
    path('upload/', moved('create-sound')),
    path('<int:pk>/peaks/', views.audio_peaks_json, name='audio_peaks_json'),
    path('<int:pk>/escuchar/', views.audio_stream, name='audio-stream'),
    path('<int:pk>/bajar/', views.audio_download, name='audio-download'),
    path('<int:pk>/agregar/', views.sound_add_to_project, name='sound-add-to-project'),
    re_path(r'^(?P<slug>[\w-]+)/$', views.AudioDetailView.as_view(), name='audio-detail'),
    re_path(r'^(?P<slug>[\w-]+)/editar/$', views.audio_create_update, name='audio-edit'),
    re_path(r'^(?P<slug>[\w-]+)/borrar/$', views.AudioDeleteView.as_view(), name='audio-delete'),
    # Old addresses.
    re_path(r'^(?P<slug>[\w-]+)/edit/$', moved('audio-edit')),
    re_path(r'^(?P<slug>[\w-]+)/delete/$', moved('audio-delete')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
