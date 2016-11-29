from django.conf import settings
from django.conf.urls import include, url
from django.contrib import admin

admin.autodiscover()
import core
from users.views import user_profile

urlpatterns = [
    url(r'', include('core.urls')),
    url(r'^tag/(?P<slug>[\w-]+)/$', core.views.hashtaged_list, name="hashtaged-list"),
    url(r'^tag/(?P<slug>[\w-]+)/audios/$', core.views.hashtaged_list, {'filters': 'audios'}, name="hashtaged-list-audios"),
    url(r'^tag/(?P<slug>[\w-]+)/projects/$', core.views.hashtaged_list, {'filters': 'projects'}, name="hashtaged-list-projects"),
    url(r'^tag/(?P<slug>[\w-]+)/messages/$', core.views.hashtaged_list, {'filters': 'messages'}, name="hashtaged-list-messages"),
    url(r'^tag/(?P<slug>[\w-]+)/users/$', core.views.hashtaged_list, {'filters': 'users'}, name="hashtaged-list-users"),
    url(r'^u/', include('users.urls')),
    url(r'^p/', include('project.urls')),
    url(r'^a/', include('audio.urls')),
    url(r'^accounts/profile/$', user_profile, name="user-profile"),
    url(r'^accounts/', include('allauth.urls')),
    url(r'^activity/', include('social.urls')),
    url(r'^activity/', include('actstream.urls')),
    url(r'^avatar/', include('avatar.urls')),
    url(r'^search/', include('haystack.urls')),
    url(r'^admin/', include(admin.site.urls)),
]


if settings.DEBUG:
    from django.conf.urls.static import static
    urlpatterns = urlpatterns + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
