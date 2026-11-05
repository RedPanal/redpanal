from django.db import models
from django.db.models.signals import post_save
from django.contrib.auth.models import User, Group, Permission
from django.utils.translation import gettext_lazy as _

from taggit.managers import TaggableManager

import actstream.models
from actstream import actions, registry

DEFAULT_GROUP = 'users'

User.add_to_class('following', lambda self: actstream.models.following(self)[::-1])
User.add_to_class('followers', lambda self: actstream.models.followers(self)[::-1])
User.add_to_class('action_list', lambda self: actstream.models.actor_stream(self))

@property
def created_at(self):
    return self.date_joined
User.add_to_class('created_at', created_at)

def profile_cover_upload_to(instance, filename):
    from audio.models import image_upload_to
    return image_upload_to("profiles", filename)


# The four sets of colors; only colors change between them, never the layout.
PALETTE_CHOICES = (
    ("moderna", _("Modern: cyan and mint")),
    ("neon", _("Neon: dark, for the night")),
    ("calida", _("Warm: sand and terracotta")),
    ("lavanda", _("Lavender: soft pastels")),
)
PALETTE_DEFAULT = "moderna"


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    realname = models.CharField(null=True, max_length=20, verbose_name=_("name"), help_text=_("how you want your name on RedPanal?") )
    about = models.TextField(blank=True, null=True, verbose_name=_("about"), help_text=_("something about you"))
    website = models.URLField(blank=True, null=True, verbose_name=_("website"), help_text=_("your website"))
    location = models.CharField(blank=True, null=True, max_length=50, verbose_name=_("location"), help_text=_("where do you live"))
    tags = TaggableManager(blank=True)
    # Instrument codes from audio.models.INSTRUMENT_CHOICES; used to suggest open requests.
    instruments = models.JSONField(default=list, blank=True, verbose_name=_("instruments you play"))
    # Notification kinds this person turned off (see social.models.Notification.PREFERENCES).
    notify_off = models.JSONField(default=list, blank=True)
    # Artistic identity and collaboration details shown on the profile.
    cover = models.ImageField(_("cover image"), upload_to=profile_cover_upload_to, blank=True, null=True, max_length=200)
    open_to_collaborate = models.BooleanField(_("available to collaborate"), default=False)
    genres = models.CharField(_("genres"), max_length=200, blank=True, help_text=_("separated by commas"))
    tools = models.CharField(_("records with"), max_length=200, blank=True, help_text=_("separated by commas"))
    other_link = models.URLField(_("another link"), blank=True, null=True)
    # Empty: the browser's language. Otherwise one of settings.LANGUAGES, the same on every device.
    language = models.CharField(_("language"), max_length=8, blank=True, default="")
    # The colors of the site for this person (redpanal/static/css/rp-palettes.css).
    palette = models.CharField(_("colors"), max_length=16, choices=PALETTE_CHOICES, default=PALETTE_DEFAULT)

    def get_absolute_url(self):
        return self.user.get_absolute_url()

    @staticmethod
    def _split(value):
        return [v.strip() for v in (value or "").split(",") if v.strip()]

    def genre_list(self):
        return self._split(self.genres)

    def tool_list(self):
        return self._split(self.tools)

    def instrument_labels(self):
        from audio.models import INSTRUMENT_CHOICES
        labels = dict(INSTRUMENT_CHOICES)
        return [labels[code] for code in self.instruments or [] if code in labels]

    def __str__(self):
        return str(self.user)

def create_profile(user):
    profile = UserProfile(user=user)
    profile.save()
    group, created = Group.objects.get_or_create(name=DEFAULT_GROUP)
    if created:
        add_audio = Permission.objects.get(codename='add_audio')
        group.permissions.add(add_audio)
        group.save()
    user.groups.add(group)
    return profile

def _create_profile(sender, **kw):
    user = kw["instance"]
    if kw["created"]:
        create_profile(user)
        follow_default_users(user)

post_save.connect(_create_profile, sender=User, dispatch_uid="users-profilecreation-signal")


PROFILE_IMAGES_MAX = 10


class ProfileImage(models.Model):
    """Pictures on a profile (rehearsals, gigs, the studio): up to ten, between the bio and the posts."""
    user = models.ForeignKey(User, related_name="profile_images", on_delete=models.CASCADE)
    image = models.ImageField(_("image"), upload_to=profile_cover_upload_to, max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]


class DefaultFollowedUser(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)


def follow_default_users(user):
    for default_user in DefaultFollowedUser.objects.all():
        actions.follow(user, default_user.user, send_action=False, actor_only=True)
