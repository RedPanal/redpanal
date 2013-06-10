from django.db import models
from django.contrib.auth.models import User
from django.core.urlresolvers import reverse
from django.utils.translation import ugettext_lazy as _
from django.db.models.signals import post_save
from actstream import action

from taggit.managers import TaggableManager
from autoslug.fields import AutoSlugField

class AudioFile(models.Model):
    name = models.CharField(_('name'), max_length=100, unique=True)
    slug = AutoSlugField(populate_from='name', always_update=False,
                         editable=False, blank=True, unique=True)
    description = models.TextField(_('description'))
    audio =  models.FileField(_('audio'), max_length=250,
                              upload_to='uploads/audios/%Y_%m')
    user = models.ForeignKey(User, editable=False)

    tags = TaggableManager(blank=True)

    def get_absolute_url(self):
        return reverse('audio-detail', kwargs={'slug': self.slug})

    def __unicode__(self):
        return self.name

def audio_created_signal(sender, instance, created, **kwargs):
    if created:
        action.send(instance.user, verb=_('created'), target=instance)

post_save.connect(audio_created_signal, sender=AudioFile)
