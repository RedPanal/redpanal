from django.db import models
from django.contrib.auth.models import User
from django.core.urlresolvers import reverse
from django.utils.translation import ugettext_lazy as _
from django.db.models.signals import post_save
from actstream import action

from taggit.managers import TaggableManager
from autoslug.fields import AutoSlugField
from ..utils.models import BaseModelMixin

class Project(models.Model, BaseModelMixin):

    name = models.CharField(verbose_name=_('name'), max_length=100)
    slug = AutoSlugField(populate_from='name', always_update=False,
                         editable=False, blank=True, unique=True)
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    description = models.TextField(verbose_name=_('description'))
    version_of = models.ForeignKey('self', verbose_name=_('version of'),
                                   blank=True, null=True, editable=False)
    audios =  models.ManyToManyField("audio.Audio", verbose_name=_('audios'),
                                     blank=True, null=True)
    user = models.ForeignKey(User, editable=False, verbose_name=_('user'))

    tags = TaggableManager(blank=True, verbose_name=_('hashtags'))

    def get_absolute_url(self):
        return reverse('project-detail', kwargs={'slug': self.slug})

    def __unicode__(self):
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
        versions = Project.objects.filter(version_of=self)
        audios = []
        # this is really slow, replace when speed needed
        for project in versions:
            for audio in project.audios.all():
                audios.append(audio)
        return audios


def project_created_signal(sender, instance, created, **kwargs):
    if created:
        action.send(instance.user, verb='created', target=instance)
	# TODO: 'created version' when the project is a version

post_save.connect(project_created_signal, sender=Project)

