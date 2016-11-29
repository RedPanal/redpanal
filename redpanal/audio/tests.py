import os

from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth.models import User
from django.utils.translation import ugettext_lazy as _
from django.core.urlresolvers import reverse

from models import Audio, GENRE_CHOICES, TYPE_CHOICES, INSTRUMENT_CHOICES
from project.models import Project
from core import licenses
from forms import AudioForm
from ..utils.test import InstanceTestMixin

TEST_DATA_PATH = os.path.join(os.path.dirname(__file__), "test_data")

class AudioTestCase(TestCase, InstanceTestMixin):
    def setUp(self):
        self.user = User.objects.create_user("owner", "e@a.com", "password")
        self.project = Project.objects.create(name="the project", user=self.user)

    def login(self):
        self.client.login(username="owner", password="password")

    def create_instance(self):
        with open(os.path.join(TEST_DATA_PATH, 'tone.mp3'), 'rb') as audio_file:
            audiofile = SimpleUploadedFile("the audio.mp3", audio_file.read(),
                                           content_type="audio/mpeg")
        audio = Audio(name="Un audio", description="This is an audio",
                      audio=audiofile, user=self.user)
        audio.save()
        return audio

    def get_model_name(self):
        return 'audio'

    def test_agregar_tags_a_un_audio(self):
        audio = self.create_instance()

        audio.tags.add("rock", "MiProject", "guitarr")
        self.assertTrue(Audio.objects.filter(tags__name__in=["rock"]))
        self.assertFalse(Audio.objects.filter(tags__name__in=["Rock"]))

    def create_audio_form_data(self, filename, content_type):
        data = {"name": "test audio", "description": "This is a test audio",
                "project": self.project.pk,
                "genre": GENRE_CHOICES[0][0],
                "use_type": TYPE_CHOICES[0][0],
                "instrument": INSTRUMENT_CHOICES[0][0],
                "license": licenses.DEFAULT_LICENSE.code,
                }
        with open(os.path.join(TEST_DATA_PATH, filename)) as audio_file:
            audiofile = SimpleUploadedFile(filename, audio_file.read(),
                                           content_type=content_type)
        return data, audiofile

    def test_upload_mp3(self):
        data, audiofile = self.create_audio_form_data("tone.mp3", "audio/mpeg")
        form = AudioForm(data, {"audio":audiofile}, user=self.user)
        self.assertTrue(form.is_valid())
        audio = form.save()

    def test_upload_flac(self):
        data, audiofile = self.create_audio_form_data("tone.flac", "audio/mpeg")
        form = AudioForm(data, {"audio":audiofile}, user=self.user)
        self.assertTrue(form.is_valid())
        audio = form.save()

    def test_upload_ogg(self):
        data, audiofile = self.create_audio_form_data("tone.ogg", "audio/mpeg")
        form = AudioForm(data, {"audio":audiofile}, user=self.user)
        self.assertTrue(form.is_valid())
        audio = form.save()

    def test_edit_audio(self):
        data, audiofile = self.create_audio_form_data("tone.mp3", "audio/mpeg")
        form = AudioForm(data, {"audio": audiofile}, user=self.user)
        self.assertTrue(form.is_valid())
        audio = form.save()

        data['description'] = "new desc"
        edit_form = AudioForm(data, instance=audio, user=self.user)
        self.assertTrue(form.is_valid())
        edit_form.save()

    def test_upload_audio_with_wrong_extension(self):
        data, _ = self.create_audio_form_data("tone.mp3", "audio/mpeg")
        audiofile = SimpleUploadedFile("tone.mpe", "file content", content_type="audio/mpeg")
        form = AudioForm(data, {"audio": audiofile}, user=self.user)
        self.assertFalse(form.is_valid())
