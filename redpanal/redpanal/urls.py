from django.conf import settings
from django.urls import include, path, re_path
from django.contrib import admin

admin.autodiscover()
import core
from users.views import user_profile
from .api import api_urls

urlpatterns = [
    path('', include('core.urls')),
    re_path(r'^tag/(?P<slug>[\w-]+)/$', core.views.hashtaged_list, name="hashtaged-list"),
    re_path(r'^tag/(?P<slug>[\w-]+)/audios/$', core.views.hashtaged_list, {'filters': 'audios'}, name="hashtaged-list-audios"),
    re_path(r'^tag/(?P<slug>[\w-]+)/projects/$', core.views.hashtaged_list, {'filters': 'projects'}, name="hashtaged-list-projects"),
    re_path(r'^tag/(?P<slug>[\w-]+)/messages/$', core.views.hashtaged_list, {'filters': 'messages'}, name="hashtaged-list-messages"),
    re_path(r'^tag/(?P<slug>[\w-]+)/users/$', core.views.hashtaged_list, {'filters': 'users'}, name="hashtaged-list-users"),
    path('u/', include('users.urls')),
    path('p/', include('project.urls')),
    path('a/', include('audio.urls')),
    path('accounts/profile/', user_profile, name="user-profile"),
    path('accounts/', include('allauth.urls')),
    path('activity/', include('social.urls')),
    path('activity/', include('actstream.urls')),
    path('avatar/', include('avatar.urls')),
    path('search/', include('haystack.urls')),
    path('api/', include(api_urls)),
    path('api-auth/', include('rest_framework.urls')),
    re_path(r'^admin/', admin.site.urls),
]


if settings.DEBUG:
    from django.conf.urls.static import static
    urlpatterns = urlpatterns + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
