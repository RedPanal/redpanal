# -*- coding: utf-8 -*-
import os
import shutil
import tempfile
import unittest

from django.test import TestCase
from django.contrib.auth.models import User
from django.core.files import File
from django.conf import settings
from django.core.signals import setting_changed

from .models import Project
from redpanal.utils.test import InstanceTestMixin
from audio.models import Audio
from audio.tests import get_test_audiofile

class ProjectTestCase(TestCase, InstanceTestMixin):
    TEST_FILE = File(open(__file__))

    def setUp(self):
        self.user = User.objects.create_user("owner", "e@a.com", "password")
        self._temp_media = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self._temp_media, ignore_errors=True)

    def login(self):
        self.client.login(username="owner", password="password")

    def create_instance(self, name="", description="", user=None):
        user = user or self.user
        name = "the NAME"
        description = description or "This is THE project"
        instance = Project.objects.create(name=name, user=user,
                                          description=description)
        return instance

    def create_audio(self, user, name="foobar"):
        audio_file = get_test_audiofile()
        audio = Audio(user=user, audio=audio_file, name=name)
        audio.save()
        return audio

    def get_model_name(self):
        return 'project'

    def test_collaborators(self):
        john = User.objects.create_user('john', '', '')
        peter = User.objects.create_user('peter', '', '')

        project = self.create_instance(name="project one", user=john)
        project.audios.add(self.create_audio(user=john))
        self.assertListEqual([john], list(project.collaborators()))

        project_version = self.create_instance(name="project one", user=peter)
        project_version.version_of = project
        project_version.save()
        version1 = self.create_audio(user=peter)
        project_version.audios.add(version1)
        version2 = self.create_audio(user=peter)
        project_version.audios.add(version2)

        self.assertListEqual([peter], list(project_version.collaborators()))
        self.assertListEqual([john, peter], list(project.collaborators()))

    def test_audios_list(self):

        john = User.objects.create_user('john', '', '')
        peter = User.objects.create_user('peter', '', '')

        project = self.create_instance(name="project one", user=john)
        audio_0 = self.create_audio(user=john)
        project.audios.add(audio_0)

        self.assertListEqual([audio_0], list(project.all_audios()))

        project_version = self.create_instance(name="project one", user=peter)
        project_version.version_of = project
        project_version.save()
        audio_version_1 = self.create_audio(user=peter, name="version1")
        project_version.audios.add(audio_version_1)
        audio_version_2 = self.create_audio(user=peter, name="version2")
        project_version.audios.add(audio_version_2)

        self.assertSetEqual({audio_0, audio_version_1, audio_version_2}, set(project.all_audios()))
        self.assertSetEqual({audio_version_1, audio_version_2}, set(project.audios_from_versions()))

    def test_download_audio_mix(self):
        with self.settings(MEDIA_ROOT=self._temp_media):
            john = User.objects.create_user('john', '', '')
            project = self.create_instance(name="project one", user=john)
            project.audios.add(self.create_audio(user=john))
            project.audios.add(self.create_audio(user=john))
            project.save()

            ids = [audio.id for audio in project.audios.all()]
            filename = project.mix_audios(ids)
            self.assertTrue(os.path.exists(os.path.join(settings.MEDIA_ROOT, 'audio_cache', filename)))
