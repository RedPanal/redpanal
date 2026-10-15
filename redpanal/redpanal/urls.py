from django.conf import settings
from django.urls import include, path, re_path
from django.contrib import admin
from django.views.generic import RedirectView

admin.autodiscover()
import core
from users.views import user_profile, all_people, delete_account, set_language
from project.views import explore, my_stuff, my_favorites, my_downloads, work_create, work_create_folder, sound_create
from project import groups_views, upload
from social import views as social_views
from audio import player
from .api import api_urls
from .utils.redirects import moved

urlpatterns = [
    path('', include('core.urls')),
    path('explorar/', explore, name='explore'),
    path('estudio/', my_stuff, name='my-stuff'),
    path('estudio/favoritos/', my_favorites, name='my-favorites'),
    path('estudio/descargas/', my_downloads, name='my-downloads'),
    path('mis-cosas/', RedirectView.as_view(pattern_name='my-stuff', permanent=True)),  # old address
    path('crear/', work_create, name='create'),
    path('crear/carpeta/', work_create_folder, name='create-folder'),
    path('crear/sonido/', sound_create, name='create-sound'),
    # Uploading: each file on its own, then organize, complete and share.
    path('crear/archivo/', upload.upload_file, name='upload-file'),
    path('crear/ordenar/', upload.upload_organize, name='upload-organize'),
    path('crear/proyecto/', upload.upload_new_project, name='upload-new-project'),
    path('crear/adjunto/<slug:slug>/', upload.upload_attachment, name='upload-attachment'),
    path('crear/completar/', upload.upload_complete, name='upload-complete'),
    path('crear/compartir/', upload.upload_share, name='upload-share'),
    path('avisos/', social_views.notifications, name='notifications'),
    path('ajustes/', user_profile, name='user-profile'),
    path('ajustes/borrar-cuenta/', delete_account, name='delete-account'),
    path('personas/', all_people, name='all-people'),
    path('idioma/', set_language, name='set-language'),
    # The persistent player: what comes next, and the person's collections.
    path('reproductor/siguientes/<int:pk>/', player.next_tracks, name='player-next'),
    path('reproductor/pista/<int:pk>/', player.track_detail, name='player-track'),
    path('reproductor/favoritos/', player.favorites, name='player-favorites'),
    path('reproductor/descargados/', player.downloads, name='player-downloads'),
    path('reproductor/listas/', player.playlists, name='player-playlists'),
    path('reproductor/listas/nueva/', player.playlist_create, name='player-playlist-create'),
    path('reproductor/listas/<int:pk>/', player.playlist_tracks, name='player-playlist'),
    path('reproductor/listas/<int:pk>/agregar/', player.playlist_add, name='player-playlist-add'),
    path('reproductor/listas/<int:pk>/quitar/', player.playlist_remove, name='player-playlist-remove'),
    path('reproductor/listas/<int:pk>/borrar/', player.playlist_delete, name='player-playlist-delete'),
    path('moderacion/', include('moderation.urls')),
    path('grupos/', groups_views.group_list, name='groups'),
    path('grupos/unirme/', groups_views.group_join, name='group-join'),
    path('grupos/<int:pk>/', groups_views.group_by_number),  # old numeric address
    re_path(r'^grupos/(?P<pk>\d+)/(?P<rest>.+)$', groups_views.group_by_number),
    path('grupos/<slug:slug>/', groups_views.group_detail, name='group-detail'),
    path('grupos/<slug:slug>/invitar/', groups_views.group_invite, name='group-invite'),
    path('grupos/<slug:slug>/integrantes/<int:member_pk>/quitar/', groups_views.group_member_remove,
         name='group-member-remove'),
    re_path(r'^p/(?P<slug>[\w-]+)/acceso/grupo/$', groups_views.share_with_group, name='project-share-group'),
    re_path(r'^tag/(?P<slug>[\w-]+)/$', core.views.hashtaged_list, name="hashtaged-list"),
    re_path(r'^tag/(?P<slug>[\w-]+)/audios/$', core.views.hashtaged_list, {'filters': 'audios'}, name="hashtaged-list-audios"),
    re_path(r'^tag/(?P<slug>[\w-]+)/projects/$', core.views.hashtaged_list, {'filters': 'projects'}, name="hashtaged-list-projects"),
    re_path(r'^tag/(?P<slug>[\w-]+)/messages/$', core.views.hashtaged_list, {'filters': 'messages'}, name="hashtaged-list-messages"),
    re_path(r'^tag/(?P<slug>[\w-]+)/users/$', core.views.hashtaged_list, {'filters': 'users'}, name="hashtaged-list-users"),
    path('u/', include('users.legacy_urls')),  # old addresses of people: now at the root
    path('p/', include('project.urls')),
    path('a/', include('audio.urls')),
    path('accounts/profile/', moved('user-profile')),  # old address of the settings
    path('accounts/', include('allauth.urls')),
    path('activity/', include('social.urls')),
    path('activity/', include('actstream.urls')),
    path('avatar/', include('avatar.urls')),
    # Old search page: searching now happens in Explore, across works, sounds and people.
    path('search/', RedirectView.as_view(pattern_name='explore', query_string=True), name='haystack_search'),
    path('api/', include(api_urls)),
    path('api-auth/', include('rest_framework.urls')),
    re_path(r'^admin/', admin.site.urls),
]


if settings.DEBUG:
    from django.conf.urls.static import static
    urlpatterns = urlpatterns + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# People, at the root (redpanal.org/<username>/): last, so every page above wins. Their names can't be the
# name of a page (users/reserved.py).
urlpatterns += [path('', include('users.urls'))]
