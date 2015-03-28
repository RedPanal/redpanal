import os
import time

from django.db import models
from django.contrib.auth.models import User
from django.core.urlresolvers import reverse
from django.utils.translation import ugettext_lazy as _
from django.db.models.signals import post_save
from django.conf import settings
from actstream import action

from taggit.managers import TaggableManager
from autoslug.fields import AutoSlugField

from ..utils.models import BaseModelMixin
from redpanal.core import licenses


LICENSES_CHOICES = [(lic.code, lic.name) for lic in licenses.LICENSES.values()]

GENRE_CHOICES = (
    ("pop", _("pop")),
    ("rock", _("rock")),
    ("jazz", _("jazz")),
    ("blues", _("blues")),
    ("folklore", _("folklore")),
    ("electronic", _("electronic")),
    ("other", _("other")),
)

TYPE_CHOICES = (
    ("track", _("track")),
    ("loop", _("loop")),
    ("song", _("song")),
    ("sample", _("sample")),
    ("other", _("other")),
)

INSTRUMENT_CHOICES = (
    ("voice", _("voice")),
    ("guitar", _("guitar")),
    ("electric guitar", _("electric guitar")),
    ("bass", _("bass")),
    ("drums", _("drums")),
    ("saxophone", _("saxophone")),
    ("piano", _("piano")),
    ("sinthesizer", _("sinthesizer")),
    ("electronic", _("electronic")),
    ("strings", _("other strings")),
    ("woodwind", _("woodwind")),
    ("brass", _("brass")),
    ("multiple", _("multiple")),
    ("other", _("other")),
)

class Audio(models.Model, BaseModelMixin):
    name = models.CharField(_('name'), max_length=100)
    slug = AutoSlugField(populate_from='name', always_update=False,
                         editable=False, blank=True, unique=True)
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    description = models.TextField(_('description'))
    audio = models.FileField(_('audio'), max_length=250,
                              upload_to='uploads/audios/%Y_%m')
    license = models.CharField(_('license'), max_length=30, choices=LICENSES_CHOICES,
                                default=licenses.DEFAULT_LICENSE.code)

    genre = models.CharField(_('genre'), max_length=30, choices=GENRE_CHOICES)
    use_type = models.CharField(_('type'), max_length=30, choices=TYPE_CHOICES)
    instrument = models.CharField(_('instrument'), max_length=30, choices=INSTRUMENT_CHOICES)

    channels = models.IntegerField(null=True, editable=False)
    blocksize  =  models.IntegerField(null=True, editable=False)
    samplerate  =  models.IntegerField(null=True, editable=False)
    totalframes  =  models.IntegerField(null=True, editable=False)

    user = models.ForeignKey(User, editable=False)

    tags = TaggableManager(blank=True, verbose_name=_('hashtags'))

    def get_duration(self):
        duration = None
        if self.samplerate is not None:
           duration = self.totalframes / float(self.samplerate) * 1000
        return duration

    def get_license(self):
        return licenses.LICENSES[self.license]

    def get_absolute_url(self):
        return reverse('audio-detail', kwargs={'slug': self.slug})

    def __unicode__(self):
        return self.name

    class Meta:
        verbose_name = "audio"
        verbose_name_plural = "audios"
        ordering = ["-created_at"]

def audio_processing(audio):
    import timeside
    # http://code.google.com/p/timeside/

    track  =  timeside.decoder.FileDecoder(audio.audio.path)

    img_waveform  =  timeside.grapher.WaveformSimple(width=460, height=100)
    img_waveform_big  =  timeside.grapher.WaveformSimple(width=940, height=150)
    img_waveform.set_colors(background=(255,255,255),  scheme='awdio')
    img_waveform_big.set_colors(background=(255,255,255),  scheme='awdio')
    try:
        ( track | img_waveform | img_waveform_big ).run()
    except IOError:
        # TODO: handle this
        return

    img_waveform.render(output=audio.audio.path + '.png')
    img_waveform_big.render(output=audio.audio.path + '.big.png')

    # duration = int(totalframes / float(samplerate) * 1000)
    # print ("samplerate: %s | blocksize: %s | totalframes: %s | channels: %s | duration: %s" % (samplerate, blocksize, totalframes, channels, duration))
    audio.channels = track.channels()
    audio.blocksize = track.blocksize()
    audio.samplerate = track.samplerate()
    audio.totalframes = track.totalframes()
    audio.save()

def audio_created_signal(sender, instance, created, **kwargs):
    if created:
        action.send(instance.user, verb='audio_created', action_object=instance)
        audio_processing(instance)

post_save.connect(audio_created_signal, sender=Audio)
