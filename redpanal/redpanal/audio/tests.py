from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth.models import User
from django.utils.translation import ugettext_lazy as _
from django.core.urlresolvers import reverse

from models import AudioFile


class AudioFileTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("owner", "e@a.com", "password")

    def test_crear_audio(self):
        user = User.objects.create_user('john', 'lennon@thebeatles.com', 'johnpassword')
        audio = AudioFile(name="Un audio", description="This is an audio",
                          audio=SimpleUploadedFile("the audio.mp3", "content"),
                          user=user)
        audio.save()

        self.assertEquals("un-audio", audio.slug)

    def test_agregar_tags_a_un_audio(self):
        user = User.objects.create_user('john', 'lennon@thebeatles.com', 'johnpassword')
        audio = AudioFile(name="Un audio", description="This is an audio",
                          audio=SimpleUploadedFile("the audio.mp3", "content"),
                          user=user)
        audio.save()

        audio.tags.add("rock", "MiProject", "guitarr")
        self.assertTrue(AudioFile.objects.filter(tags__name__in=["rock"]))
        self.assertFalse(AudioFile.objects.filter(tags__name__in=["Rock"]))

    def test_upload_audio_fail_unauthenticated(self):
        response = self.client.get(reverse('audio-create'))
        self.assertEqual(302, response.status_code)

    def test_upload_audio(self):

        self.client.login(username="owner", password="password")
        response = self.client.get(reverse('audio-create'))
        self.assertEqual(200, response.status_code)

