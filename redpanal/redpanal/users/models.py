from django.db import models
from django.db.models.signals import post_save
from django.contrib.auth.models import User
from django.utils.translation import ugettext_lazy as _


class UserProfile(models.Model):
    user = models.OneToOneField(User)
    about = models.TextField(blank=True, null=True, help_text=_("something about you"))
    location = models.TextField(blank=True, null=True, help_text=_("where do you live"))

def create_profile(user):
    profile = UserProfile(user=user)
    profile.save()
    return profile

def _create_profile(sender, **kw):
    user = kw["instance"]
    if kw["created"]:
        create_profile(user)

post_save.connect(_create_profile, sender=User, dispatch_uid="users-profilecreation-signal")
