from django.urls import path, re_path

from . import views

urlpatterns = [
    # Follow/Unfollow API
    path('follow/<int:content_type_id>/<int:object_id>/',
        views.follow_unfollow, name='actstream_follow'),
    path('follow_all/<int:content_type_id>/<int:object_id>/',
        views.follow_unfollow, {'actor_only': False}, name='actstream_follow_all'),
    path(r'unfollow/<int:content_type_id>/<int:object_id>/',
        views.follow_unfollow, {'do_follow': False}, name='actstream_unfollow'),

    path(r'followers/<int:content_type_id>/<int:object_id>/', views.followers,
        name='social-followers'),
    re_path(r'^following/(?P<user_id>\d+)/', views.following, name="social-following"),
    path('mensaje/nuevo/', views.message_create, name="message-create"),
    path('reaccion/<str:kind>/<str:target>/<int:pk>/', views.react, name="react"),
    path('responder/<str:target>/<int:pk>/', views.reply, name="reply"),
    path('mensaje/nuevo-con-contenido/', views.message_with_content_create, name="message-with-content-create"),
    # Old addresses (with a typo), for pages still open in someone's browser.
    re_path(r'^messsage/create/$', views.message_create),
    re_path(r'^messsage/create-with-content/$', views.message_with_content_create),
]
