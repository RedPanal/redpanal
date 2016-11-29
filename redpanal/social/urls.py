from django.conf.urls import url

from . import views

urlpatterns = [
    # Follow/Unfollow API
    url(r'^follow/(?P<content_type_id>\d+)/(?P<object_id>\d+)/$',
        views.follow_unfollow, name='actstream_follow'),
    url(r'^follow_all/(?P<content_type_id>\d+)/(?P<object_id>\d+)/$',
        views.follow_unfollow, {'actor_only': False}, name='actstream_follow_all'),
    url(r'^unfollow/(?P<content_type_id>\d+)/(?P<object_id>\d+)/$',
        views.follow_unfollow, {'do_follow': False}, name='actstream_unfollow'),

    url(r'^followers/(?P<content_type_id>\d+)/(?P<object_id>\d+)/$', views.followers,
        name='social-followers'),
    url(r'^following/(?P<user_id>\d+)/', views.following, name="social-following"),
    url(r'^messsage/create/', views.message_create, name="message-create"),
    url(r'^messsage/create-with-content/', views.message_with_content_create,
        name="message-with-content-create"),
]
