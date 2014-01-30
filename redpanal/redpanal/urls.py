from django.conf import settings
from django.conf.urls import patterns, include, url
from django.views.generic import TemplateView
from django.contrib import admin
admin.autodiscover()

urlpatterns = patterns('',
    url(r'', include('redpanal.core.urls')),
    url(r'^tag/(?P<slug>[\w-]+)/$', 'redpanal.core.views.hashtaged_list', name="hashtaged-list"),
    url(r'^u/', include('redpanal.users.urls')),
    url(r'^p/', include('redpanal.project.urls')),
    url(r'^a/', include('redpanal.audio.urls')),
    url(r'^accounts/profile/$', 'redpanal.users.views.user_profile', name="user-profile"),
    url(r'^accounts/', include('allauth.urls')),
    url(r'^activity/', include('redpanal.social.urls')),
    url(r'^activity/', include('actstream.urls')),
    url(r'^avatar/', include('avatar.urls')),
    url(r'^search/', include('haystack.urls')),
    url(r'^admin/', include(admin.site.urls)),
)



if settings.DEBUG:

    from django.conf.urls.static import static
    urlpatterns = urlpatterns + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
