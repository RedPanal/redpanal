import os
import time
import logging
import datetime
import posixpath
import unicodedata
import hashlib

from django.db import models
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils.translation import ugettext_lazy as _
from django.db.models.signals import post_save
from django.core.files.storage import default_storage
from django.conf import settings
from actstream import action, registry

from taggit.managers import TaggableManager
from autoslug.fields import AutoSlugField
from pydub import AudioSegment
from pydub.exceptions import CouldntDecodeError

from redpanal.utils.models import BaseModelMixin
from core import licenses
from .waveform import Waveform


logger = logging.getLogger(__name__)

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
    ("violin", _("violin")),
    ("multiple", _("multiple")),
    ("other", _("other")),
)

def audio_file_upload_to(instance, filename):
    dirname = datetime.datetime.now().strftime('uploads/audios/%Y_%m')
    filename = unicodedata.normalize('NFKD', filename).encode('ascii', 'ignore').decode()
    return posixpath.join(dirname, filename)

class Audio(models.Model, BaseModelMixin):

    _original_audio_file = None

    name = models.CharField(_('name'), max_length=100)
    slug = AutoSlugField(populate_from='name', always_update=False,
                         editable=False, blank=True, unique=True)
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    description = models.TextField(_('description'))
    audio = models.FileField(_('audio'), max_length=250,
                              upload_to=audio_file_upload_to)
    license = models.CharField(_('license'), max_length=30, choices=LICENSES_CHOICES,
                                default=licenses.DEFAULT_LICENSE.code)

    genre = models.CharField(_('genre'), max_length=30, choices=GENRE_CHOICES)
    use_type = models.CharField(_('type'), max_length=30, choices=TYPE_CHOICES)
    instrument = models.CharField(_('instrument'), max_length=30, choices=INSTRUMENT_CHOICES)

    channels = models.IntegerField(null=True, editable=False)
    blocksize  =  models.IntegerField(null=True, editable=False)
    samplerate  =  models.IntegerField(null=True, editable=False)
    totalframes  =  models.IntegerField(null=True, editable=False)
    hashsum = models.CharField(max_length=40, null=True, blank=True, editable=False)

    user = models.ForeignKey(User, editable=False, on_delete=models.CASCADE)

    tags = TaggableManager(blank=True, verbose_name=_('hashtags'))

    position_lat = models.DecimalField(verbose_name=_('latitude'), max_digits=9, decimal_places=5, blank=True, null=True)
    position_long = models.DecimalField(verbose_name=_('longitude'), max_digits=9, decimal_places=5, blank=True, null=True)

    def __init__(self, *args, **kwargs):
        super(Audio, self).__init__(*args, **kwargs)
        if (self.audio):
            self.original_audio_file = self.audio.path

    def get_duration(self):
        duration = None
        if self.samplerate is not None:
           duration = self.totalframes / float(self.samplerate) * 1000
        return duration

    def get_license(self):
        return licenses.LICENSES[self.license]

    def get_absolute_url(self):
        return reverse('audio-detail', kwargs={'slug': self.slug})

    def get_tags(self):
        return [str(t) for t in self.tags.all()]

    def __str__(self):
        return self.name

    def audio_has_changed(self):
        return (self._original_audio_file != self.audio.path)

    class Meta:
        verbose_name = "audio"
        verbose_name_plural = "audios"
        ordering = ["-created_at"]


def audio_processing(audio):
    try:
        sound = AudioSegment.from_file(audio.audio.path)
        Waveform(sound, width=460, height=100, bar_count=int(460/8)).save(audio.audio.path + '.png')
        Waveform(sound, width=940, height=150, bar_count=int(940/8)).save(audio.audio.path + '.big.png')

        audio.channels = sound.channels
        audio.blocksize = 0
        audio.samplerate = sound.frame_rate
        audio.totalframes = sound.frame_count()
        audio._original_audio_file = audio.audio.path
        audio.hashsum = calculate_hashsum(audio.audio.path)
        audio.save()

    except CouldntDecodeError:
        logger.exception('could not decode %r', audio.audio.path)

def calculate_hashsum(path):
    BUF_SIZE = 65536  # lets read stuff in 64kb chunks!
    sha1 = hashlib.sha1()
    with default_storage.open(path, 'rb') as f:
        while True:
            data = f.read(BUF_SIZE)
            if not data:
                break
            sha1.update(data)
    return sha1.hexdigest()

def audio_created_signal(sender, instance, created, **kwargs):
    if created:
        action.send(instance.user, verb='audio_created', action_object=instance)

    if instance.audio_has_changed():
        audio_processing(instance)


post_save.connect(audio_created_signal, sender=Audio)
