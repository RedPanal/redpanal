from django.conf.urls import patterns, url


urlpatterns = patterns('redpanal.social.views',
    url(r'^followers/(?P<content_type_id>\d+)/(?P<object_id>\d+)/$', 'followers',
        name='social-followers'),
    url(r'^following/(?P<user_id>\d+)/', 'following', name="social-following"),
    url(r'^messsage/create/', 'message_create', name="message-create"),
)
