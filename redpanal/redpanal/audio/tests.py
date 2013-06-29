from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth.models import User
from django.utils.translation import ugettext_lazy as _
from django.core.urlresolvers import reverse

from models import Audio
from ..utils.test import InstanceTestMixin

class AudioTestCase(TestCase, InstanceTestMixin):
    def setUp(self):
        self.user = User.objects.create_user("owner", "e@a.com", "password")

    def login(self):
        self.client.login(username="owner", password="password")

    def create_instance(self):
        audio = Audio(name="Un audio", description="This is an audio",
                          audio=SimpleUploadedFile("the audio.mp3", "content"),
                          user=self.user)
        audio.save()
        return audio

    def get_model_name(self):
        return 'audio'

    def test_agregar_tags_a_un_audio(self):
        audio = self.create_instance()

        audio.tags.add("rock", "MiProject", "guitarr")
        self.assertTrue(Audio.objects.filter(tags__name__in=["rock"]))
        self.assertFalse(Audio.objects.filter(tags__name__in=["Rock"]))
