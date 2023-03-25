from django.urls import path, re_path

from . import views

urlpatterns = [
    # Follow/Unfollow API
    path('follow/<int:content_type_id>/<int:object_id>/',
        views.follow_unfollow, name='actstream_follow'),
    path('follow_all/<int:content_type_id>/<int:object_id>/',
        views.follow_unfollow, {'actor_only': False}, name='actstream_follow_all'),
    path('unfollow/<int:content_type_id>/<int:object_id>/',
        views.follow_unfollow, {'do_follow': False}, name='actstream_unfollow'),

    path('followers/<int:content_type_id>/<int:object_id>/', views.followers,
        name='social-followers'),
    re_path(r'^following/(?P<user_id>\d+)/', views.following, name="social-following"),
    re_path(r'^messsage/create/', views.message_create, name="message-create"),
    re_path(r'^messsage/create-with-content/', views.message_with_content_create,
        name="message-with-content-create"),
]
