from django.conf import settings
from django.conf.urls import patterns, include, url
from django.views.generic import TemplateView
from django.contrib import admin
admin.autodiscover()

urlpatterns = patterns('',
    url(r'^$', 'redpanal.core.views.index', name="index"),
    url(r'^tag/(?P<slug>[\w-]+)/$', 'redpanal.core.views.hashtaged_list', name="hashtaged-list"),

    url(r'^audio/', include('redpanal.audio.urls')),
    url(r'^accounts/profile/$', 'redpanal.core.views.user_profile', name="user-profile"),
    (r'^accounts/', include('allauth.urls')),
    ('^activity/', include('redpanal.social.urls')),
    ('^activity/', include('actstream.urls')),
    url(r'^admin/', include(admin.site.urls)),
    url(r'^(?P<slug>[\w-]+)/$', 'redpanal.core.views.user_page', name="user-page"),
)



if settings.DEBUG:

    from django.conf.urls.static import static
    urlpatterns = urlpatterns + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
