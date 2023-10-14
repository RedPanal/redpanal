import os
import hashlib

from django.db import models
from django.db.models import Q
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.db.models.signals import post_save
from django.core.files.storage import default_storage
from actstream import action, registry

from taggit.managers import TaggableManager
from autoslug.fields import AutoSlugField
from redpanal.utils.models import BaseModelMixin
from audio.models import Audio
from pydub import AudioSegment


class Project(models.Model, BaseModelMixin):

    name = models.CharField(verbose_name=_('name'), max_length=100)
    slug = AutoSlugField(populate_from='name', always_update=False,
                         editable=False, blank=True, unique=True)
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    description = models.TextField(verbose_name=_('description'))
    version_of = models.ForeignKey('self', verbose_name=_('version of'),
                                   blank=True, null=True, editable=False,
                                   related_name="versions", on_delete=models.SET_NULL)
    audios = models.ManyToManyField("audio.Audio", verbose_name=_('audios'),
                                    blank=True)
    image = models.ImageField(verbose_name=_('image'),
                              upload_to="uploads/images/projects/%Y_%m",
                              blank=True, null=True,
                              max_length=150)
    user = models.ForeignKey(User, editable=False, verbose_name=_('user'), on_delete=models.CASCADE)
    tags = TaggableManager(blank=True, verbose_name=_('hashtags'))


    def get_absolute_url(self):
        return reverse('project-detail', kwargs={'slug': self.slug})

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "project"
        verbose_name_plural = "projects"
        ordering = ["-created_at"]

    def create_version(self, user):
        project = Project(name=self.name, description=self.description,
                          version_of=self, user=user)
        project.save()
        project.tags.add(*self.tags.all())
        return project

    def audios_from_versions(self):
        return Audio.objects.filter(project__in=self.versions.all())

    def all_audios(self):
        return Audio.objects.filter(Q(project__in=self.versions.all()) | Q(project=self))

    def collaborators(self):
        return User.objects.filter(Q(audio__in=self.all_audios()) | Q(pk=self.user.pk)).distinct()

    def mix_audios(self, ids):
        audios = self.audios.filter(id__in=ids)
        if len(audios) < 2:
            raise ValueError("Need at least 2 audios to mix")

        hashsum = hashlib.sha1()
        for audio in audios:
            hashsum.update(audio.hashsum.encode())

        hashsum = format(hashsum.hexdigest())
        filename = "%s.ogg" % hashsum

        path = default_storage.path('audio_cache')
        if not default_storage.exists(path):
            os.makedirs(path)

        path = default_storage.path(os.path.join('audio_cache', filename))
        if not default_storage.exists(path):
            mix = AudioSegment.empty()
            for audio in audios:
                a = AudioSegment.from_file(audio.audio.path)
                if a.duration_seconds > mix.duration_seconds:
                    mix = a.overlay(mix)
                else:
                    mix = mix.overlay(a)
            mix.export(path, format="ogg")
        return filename


def project_created_signal(sender, instance, created, **kwargs):
    if created:
        action.send(instance.user, verb='project_created', action_object=instance)
	# TODO: 'created version' when the project is a version

post_save.connect(project_created_signal, sender=Project)
