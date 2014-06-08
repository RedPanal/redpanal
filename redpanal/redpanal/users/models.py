from django.db import models
from django.db.models.signals import post_save
from django.contrib.auth.models import User
from django.utils.translation import ugettext_lazy as _

from taggit.managers import TaggableManager

import actstream.models

User.add_to_class('following', lambda self: actstream.models.following(self))
User.add_to_class('followers', lambda self: actstream.models.followers(self))
User.add_to_class('action_list', lambda self: actstream.models.actor_stream(self))


class UserProfile(models.Model):
    user = models.OneToOneField(User)
    realname = models.CharField(null=True, max_length=20, verbose_name=_("name"), help_text=_("how you want your name on RedPanal?") )
    about = models.TextField(blank=True, null=True, verbose_name=_("about"), help_text=_("something about you"))
    website = models.URLField(blank=True, null=True, verbose_name=_("website"), help_text=_("your website"))
    location = models.CharField(blank=True, null=True, max_length=50, verbose_name=_("location"), help_text=_("where do you live"))
    tags = TaggableManager(blank=True, verbose_name=_('hashtags'), help_text=_("put tags helps you to contact users who share musical tastes"))
   # TODO TaggableManager verbose_name & help_text does not work?

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

post_save.connect(_create_profile, sender=User, dispatch_uid="users-profilecreation-signal")
