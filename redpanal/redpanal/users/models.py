from django.db import models
from django.db.models.signals import post_save
from django.contrib.auth.models import User
from django.utils.translation import ugettext_lazy as _

from taggit.managers import TaggableManager

import actstream.models
from actstream import actions, registry

User.add_to_class('following', lambda self: actstream.models.following(self)[::-1])
User.add_to_class('followers', lambda self: actstream.models.followers(self)[::-1])
User.add_to_class('action_list', lambda self: actstream.models.actor_stream(self))
registry.register(User)
@property
def created_at(self):
    return self.date_joined
User.add_to_class('created_at', created_at)

class UserProfile(models.Model):
    user = models.OneToOneField(User)
    realname = models.CharField(null=True, max_length=20, verbose_name=_("name"), help_text=_("how you want your name on RedPanal?") )
    about = models.TextField(blank=True, null=True, verbose_name=_("about"), help_text=_("something about you"))
    website = models.URLField(blank=True, null=True, verbose_name=_("website"), help_text=_("your website"))
    location = models.CharField(blank=True, null=True, max_length=50, verbose_name=_("location"), help_text=_("where do you live"))
    tags = TaggableManager(blank=True)

    def get_absolute_url(self):
        return self.user.get_absolute_url()

    def __unicode__(self):
        return unicode(self.user)

def create_profile(user):
    profile = UserProfile(user=user)
    profile.save()
    return profile

def _create_profile(sender, **kw):
    user = kw["instance"]
    if kw["created"]:
        create_profile(user)
        follow_default_users(user)

post_save.connect(_create_profile, sender=User, dispatch_uid="users-profilecreation-signal")


class DefaultFollowedUser(models.Model):
    user = models.OneToOneField(User)


def follow_default_users(user):
    for default_user in DefaultFollowedUser.objects.all():
        actions.follow(user, default_user.user, send_action=False, actor_only=True)
