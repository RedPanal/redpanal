import os
import time
import logging
import datetime
import posixpath
import unicodedata
import hashlib
import secrets

from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
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
    ("master", _("master")),
    ("mix", _("mix")),
    ("track", _("track")),
    ("loop", _("loop")),
    ("sample", _("sample")),
    ("demo", _("demo")),
    ("field", _("field recording")),
    ("song", _("song")),
    ("other", _("other")),
)
# What the upload offers: master and mix mark a work's reference; field recordings stay out of
# sight (a location makes one), song and other remain for older sounds.
UPLOAD_TYPES = ("master", "mix", "track", "loop", "sample", "demo")
REFERENCE_TYPES = ("master", "mix")

VISIBILITY_PRIVATE = "private"
VISIBILITY_OPEN = "public"
SOUND_VISIBILITY_CHOICES = ((VISIBILITY_PRIVATE, _("only you and who you share it with")),
                            (VISIBILITY_OPEN, _("public")))

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

_NOT_LOADED = object()


def audio_file_upload_to(instance, filename):
    # A random folder per file: the address can't be guessed, so the app decides
    # who gets it (see Audio.can_listen and the stream view).
    dirname = datetime.datetime.now().strftime('uploads/audios/%Y_%m')
    filename = unicodedata.normalize('NFKD', filename).encode('ascii', 'ignore').decode()
    return posixpath.join(dirname, secrets.token_urlsafe(16), filename)


def image_upload_to(kind, filename):
    """Pictures of projects and sounds: a random folder, like the audio files, so private ones can't be guessed."""
    dirname = datetime.datetime.now().strftime('uploads/images/%s/%%Y_%%m' % kind)
    filename = unicodedata.normalize('NFKD', filename).encode('ascii', 'ignore').decode()
    return posixpath.join(dirname, secrets.token_urlsafe(12), filename[-80:])


def audio_image_upload_to(instance, filename):
    return image_upload_to("sounds", filename)


class AudioQuerySet(models.QuerySet):

    def visible_to(self, user):
        """Audios this user may hear.

        An audio that belongs to a work is only visible to people who can listen
        to that work; audios outside any work stay public as they always were.
        """
        from project.models import Project, Contribution
        listenable = Project.objects.listenable_by(user).values("pk")
        restricted = Contribution.objects.exclude(project__in=listenable).values("audio_id")
        allowed = Contribution.objects.filter(project__in=listenable).values("audio_id")
        # A sound on its own that hasn't been shared yet.
        private_loose = ~Q(pk__in=Contribution.objects.values("audio_id")) & ~Q(visibility=VISIBILITY_OPEN)
        q = (~Q(pk__in=restricted) | Q(pk__in=allowed)) & ~private_loose & Q(moderation_hidden=False)
        if user is not None and user.is_authenticated:
            q |= private_loose & Q(moderation_hidden=False) & self.shared_q(user)
            q |= Q(user=user)
        return self.filter(q)

    @staticmethod
    def shared_q(user):
        """Sounds shared with this person directly or through one of their groups (no joins: no duplicates)."""
        from project.models import WorkGroup
        groups = WorkGroup.objects.filter(Q(owner=user) | Q(members__user=user)).values("pk")
        through_people = Audio.shared_with.through.objects.filter(user=user).values("audio_id")
        through_groups = Audio.shared_groups.through.objects.filter(workgroup__in=groups).values("audio_id")
        return Q(pk__in=through_people) | Q(pk__in=through_groups)


class Audio(models.Model, BaseModelMixin):

    _original_audio_file = None

    name = models.CharField(_('name'), max_length=100)
    slug = AutoSlugField(populate_from='name', always_update=False,
                         editable=False, blank=True, unique=True)
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    description = models.TextField(_('description'), blank=True)
    # Visual identity of a sound shared on its own; parts of a project use the project's image.
    image = models.ImageField(_('image'), upload_to=audio_image_upload_to, blank=True, null=True, max_length=200)
    audio = models.FileField(_('audio'), max_length=250,
                              upload_to=audio_file_upload_to)
    license = models.CharField(_('license'), max_length=30, choices=LICENSES_CHOICES,
                                default=licenses.DEFAULT_LICENSE.code)

    genre = models.CharField(_('genre'), max_length=30, choices=GENRE_CHOICES, blank=True)
    use_type = models.CharField(_('type'), max_length=30, choices=TYPE_CHOICES, default="track")
    instrument = models.CharField(_('instrument'), max_length=30, choices=INSTRUMENT_CHOICES, blank=True)
    tempo = models.PositiveSmallIntegerField(_('tempo (BPM)'), null=True, blank=True)
    musical_key = models.CharField(_('key'), max_length=20, blank=True)

    channels = models.IntegerField(null=True, editable=False)
    blocksize  =  models.IntegerField(null=True, editable=False)
    samplerate  =  models.IntegerField(null=True, editable=False)
    totalframes  =  models.IntegerField(null=True, editable=False)
    hashsum = models.CharField(max_length=40, null=True, blank=True, editable=False)
    sha256 = models.CharField(max_length=64, blank=True, editable=False, db_index=True)
    size = models.BigIntegerField(null=True, blank=True, editable=False)
    # Fingerprint of the file as it was uploaded, before any conversion: recognises re-uploads.
    source_sha256 = models.CharField(max_length=64, blank=True, editable=False, db_index=True)
    # Hidden by the volunteers after a report: works that used it keep their credits.
    moderation_hidden = models.BooleanField(default=False, editable=False)

    user = models.ForeignKey(User, editable=False, on_delete=models.CASCADE)

    tags = TaggableManager(blank=True, verbose_name=_('hashtags'))

    position_lat = models.DecimalField(verbose_name=_('latitude'), max_digits=9, decimal_places=5, blank=True, null=True)
    position_long = models.DecimalField(verbose_name=_('longitude'), max_digits=9, decimal_places=5, blank=True, null=True)

    source_audio = models.ForeignKey(
        'self', verbose_name=_('source audio'),
        null=True, blank=True,
        related_name='collaborations',
        on_delete=models.SET_NULL,
    )

    # A sound on its own (outside any work) is private until it's shared; older sounds are public.
    # Inside a work, the work decides who hears it.
    visibility = models.CharField(_("who can listen"), max_length=10, choices=SOUND_VISIBILITY_CHOICES,
                                  default=VISIBILITY_OPEN)
    shared_groups = models.ManyToManyField("project.WorkGroup", blank=True, related_name="shared_sounds")
    shared_with = models.ManyToManyField(User, blank=True, related_name="sounds_shared_with_me")
    # Uploaded in one go, without details: Estudio asks to complete them.
    needs_details = models.BooleanField(default=False, editable=False)

    objects = AudioQuerySet.as_manager()

    def __init__(self, *args, **kwargs):
        super(Audio, self).__init__(*args, **kwargs)
        # Remember the stored file to know, after a save, whether it was replaced.
        # A deferred "audio" field is left unknown instead of loading it here.
        if 'audio' in self.get_deferred_fields():
            self._original_audio_file = _NOT_LOADED
        else:
            self._original_audio_file = self.audio.name or None

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

    def get_stream_url(self):
        """Where pages play this audio from: always through the permission check."""
        return reverse('audio-stream', kwargs={'pk': self.pk})

    def can_listen(self, user, request=None):
        if user is not None and user.is_authenticated and user == self.user:
            return True
        if self.moderation_hidden:
            from moderation.models import is_moderator
            return is_moderator(user)
        projects = [c.project for c in self.contributions.select_related("project")]
        if not projects:
            if self.visibility == VISIBILITY_OPEN:
                return True
            return Audio.objects.visible_to(user).filter(pk=self.pk).exists()
        return any(p.can_listen(user, request) for p in projects)

    def publish(self):
        """Make a sound on its own public: anyone listens, it shows up in feeds and search."""
        from actstream.models import Action
        from django.contrib.contenttypes.models import ContentType
        self.visibility = VISIBILITY_OPEN
        self.save(update_fields=["visibility"])
        ct = ContentType.objects.get_for_model(Audio)
        Action.objects.filter(action_object_content_type=ct, action_object_object_id=str(self.pk),
                              verb="audio_created").update(public=True)

    def get_sha256(self):
        """SHA-256 of the stored file, for the proof of prior existence."""
        if not self.sha256 and self.audio:
            self.sha256 = calculate_hashsum(self.audio.path, hashlib.sha256)
            Audio.objects.filter(pk=self.pk).update(sha256=self.sha256)
        return self.sha256

    def move_to_private_path(self):
        """Give a file stored at a guessable address (older uploads) a random folder."""
        name = self.audio.name
        parts = name.split("/")
        if not name or len(parts) >= 5:  # uploads/audios/YYYY_MM/<token>/file
            return False
        new_name = posixpath.join(posixpath.dirname(name), secrets.token_urlsafe(16), parts[-1])
        old_path = self.audio.path
        new_path = default_storage.path(new_name)
        os.makedirs(os.path.dirname(new_path), exist_ok=True)
        for suffix in ("", ".json", ".big.json"):
            if os.path.exists(old_path + suffix):
                os.replace(old_path + suffix, new_path + suffix)
        Audio.objects.filter(pk=self.pk).update(audio=new_name)
        self.audio.name = new_name
        self._original_audio_file = new_name
        return True

    def audio_has_changed(self):
        if self._original_audio_file is _NOT_LOADED:
            return False
        return self._original_audio_file != (self.audio.name or None)

    class Meta:
        verbose_name = "audio"
        verbose_name_plural = "audios"
        ordering = ["-created_at"]


class Download(models.Model):
    """Who downloaded which sound and when: used to suggest sources later."""
    user = models.ForeignKey(User, related_name="downloads", on_delete=models.CASCADE)
    audio = models.ForeignKey(Audio, related_name="downloads", on_delete=models.CASCADE)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at"]
        unique_together = (("user", "audio"),)


class Playlist(models.Model):
    """A list of sounds someone puts together to listen to in the player. Only its owner sees it."""
    user = models.ForeignKey(User, related_name="playlists", on_delete=models.CASCADE)
    name = models.CharField(_("name"), max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return self.name


class PlaylistItem(models.Model):
    playlist = models.ForeignKey(Playlist, related_name="items", on_delete=models.CASCADE)
    audio = models.ForeignKey(Audio, related_name="+", on_delete=models.CASCADE)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["added_at"]
        unique_together = (("playlist", "audio"),)


def audio_processing(audio):
    try:
        sound = AudioSegment.from_file(audio.audio.path)
        Waveform(sound, width=460, height=100, bar_count=200).save_peaks_to_json(audio.audio.path + '.json')
        Waveform(sound, width=940, height=150, bar_count=400).save_peaks_to_json(audio.audio.path + '.big.json')

        audio.channels = sound.channels
        audio.blocksize = 0
        audio.samplerate = sound.frame_rate
        audio.totalframes = sound.frame_count()
        audio._original_audio_file = audio.audio.name
        audio.hashsum = calculate_hashsum(audio.audio.path)
        audio.sha256 = calculate_hashsum(audio.audio.path, hashlib.sha256)
        audio.size = os.path.getsize(audio.audio.path)
        audio.save()

    except CouldntDecodeError:
        logger.exception('could not decode %r', audio.audio.path)

def calculate_hashsum(path, algorithm=hashlib.sha1):
    BUF_SIZE = 65536  # lets read stuff in 64kb chunks!
    sha1 = algorithm()
    with default_storage.open(path, 'rb') as f:
        while True:
            data = f.read(BUF_SIZE)
            if not data:
                break
            sha1.update(data)
    return sha1.hexdigest()

def audio_created_signal(sender, instance, created, **kwargs):
    # Parts of a work announce themselves through the work, with its visibility.
    if created and not getattr(instance, "_part_of_work", False):
        # A private sound is announced only when it's shared (Audio.publish).
        action.send(instance.user, verb='audio_created', action_object=instance,
                    public=instance.visibility == VISIBILITY_OPEN)

    if (created or instance.audio_has_changed()) and instance.audio:
        audio_processing(instance)


post_save.connect(audio_created_signal, sender=Audio)
