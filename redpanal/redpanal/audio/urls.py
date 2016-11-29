from django.conf.urls import include, url
from django.conf import settings
from django.conf.urls.static import static

from . import views


urlpatterns = [
    url(r'^upload/$', views.audio_create_update, name='audio-create'),
    #url(r'^list/$', "list", name='audio-list',
    url(r'^(?P<slug>[\w-]+)/$', views.AudioDetailView.as_view(), name='audio-detail'),
    url(r'^(?P<slug>[\w-]+)/edit/$', views.audio_create_update, name='audio-edit'),
    url(r'^(?P<slug>[\w-]+)/delete/$', views.AudioDeleteView.as_view(), name='audio-delete'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
