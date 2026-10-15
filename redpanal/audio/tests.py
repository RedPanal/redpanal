# -*- coding: utf-8 -*-
import os
import shutil
import tempfile
from unittest import mock

from django.test import TestCase, override_settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _
from django.urls import reverse

from .models import Audio, GENRE_CHOICES, TYPE_CHOICES, INSTRUMENT_CHOICES
from project.models import Project
from core import licenses
from .forms import AudioUploadForm, AudioEditForm
from redpanal.utils.test import InstanceTestMixin

TEST_DATA_PATH = os.path.join(os.path.dirname(__file__), "test_data")
def get_test_audiofile():
    with open(os.path.join(TEST_DATA_PATH, u'tone.mp3'), 'rb') as audio_file:
        audiofile = SimpleUploadedFile(u"the audio.mp3", audio_file.read(),
                                       content_type="audio/mpeg")
    return audiofile

class AudioTestCase(TestCase, InstanceTestMixin):
    create_url_name = 'create-sound'
    def setUp(self):
        self.user = User.objects.create_user("owner", "e@a.com", "password")
        self.project = Project.objects.create(name="My Rock project", user=self.user)

    def login(self):
        self.client.login(username="owner", password="password")

    def create_instance(self):
        audiofile = get_test_audiofile()
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

    def test_modify_audio_file_reprocess_file(self):
        audio = self.create_instance()

        audio.tags.add("rock", "MiProject", "guitarr")
        self.assertTrue(Audio.objects.filter(tags__name__in=["rock"]))
        self.assertFalse(Audio.objects.filter(tags__name__in=["Rock"]))


    def test_add_unicode_tags(self):
        audio = self.create_instance()
        audio.tags.add("rock", "MiProject", u"guitarræ")
        self.assertTrue(u"guitarræ" in audio.get_tags())

    def create_audio_form_data(self, filename, content_type):
        data = {"name": u"test audiø", "description": u"This is a test audio with →UTF-8 øæ€ ««",
                "project": self.project.pk,
                "genre": GENRE_CHOICES[0][0],
                "use_type": TYPE_CHOICES[0][0],
                "instrument": INSTRUMENT_CHOICES[0][0],
                "license": licenses.DEFAULT_LICENSE.code,
                }

        audiofile = get_test_audiofile()
        return data, audiofile

    def test_upload_mp3(self):
        data, audiofile = self.create_audio_form_data(u"tone.mp3", "audio/mpeg")
        form = AudioEditForm(data, {"audio":audiofile}, user=self.user)
        self.assertTrue(form.is_valid())
        audio = form.save()

    def test_upload_flac(self):
        data, audiofile = self.create_audio_form_data(u"tone.flac", "audio/mpeg")
        form = AudioEditForm(data, {"audio":audiofile}, user=self.user)
        self.assertTrue(form.is_valid())
        audio = form.save()

    def test_upload_ogg(self):
        data, audiofile = self.create_audio_form_data(u"tone.ogg", "audio/mpeg")
        form = AudioEditForm(data, {"audio":audiofile}, user=self.user)
        self.assertTrue(form.is_valid())
        audio = form.save()

    def test_edit_audio(self):
        data, audiofile = self.create_audio_form_data(u"tone.mp3", "audio/mpeg")
        form = AudioEditForm(data, {"audio": audiofile}, user=self.user)
        self.assertTrue(form.is_valid())
        audio = form.save()

        data['description'] = "new desc"
        edit_form = AudioEditForm(data, instance=audio, user=self.user)
        self.assertTrue(form.is_valid())
        edit_form.save()

    def test_upload_audio_with_wrong_extension(self):
        data, _ = self.create_audio_form_data(u"tone.mp3", "audio/mpeg")
        audiofile = SimpleUploadedFile(u"tone.mpe", b"file content", content_type="audio/mpeg")
        form = AudioEditForm(data, {"audio": audiofile}, user=self.user)
        self.assertFalse(form.is_valid())

    def test_create_audio_without_project(self):
        data, audiofile = self.create_audio_form_data(u"tone.flac", "audio/mpeg")
        del data["project"]
        form = AudioEditForm(data, {"audio":audiofile}, user=self.user)
        self.assertTrue(form.is_valid())
        audio = form.save()

    # def test_create_audio_view(self):
    #     data, _ = self.create_audio_form_data("tone.mp3", "audio/mpeg")
    #     self.login()
    #     with open(os.path.join(TEST_DATA_PATH, u'tone.mp3'), 'rb') as audio_file:
    #         data['audio'] = audio_file
    #         resp = self.client.post("/a/upload/", data)
    #         self.assertEqual(resp.url, '/a/test-audi/')
    #         self.assertEqual(resp.status_code, 302)

    #         resp = self.client.get(resp.url)
    #         self.assertEqual(resp.status_code, 200)
    #         self.assertTrue(self.project.name in resp.content.decode())

    # def test_create_audio_view_without_project(self):
    #     data, _ = self.create_audio_form_data("tone.mp3", "audio/mpeg")
    #     del data['project']
    #     self.login()
    #     with open(os.path.join(TEST_DATA_PATH, u'tone.mp3'), 'rb') as audio_file:
    #         data['audio'] = audio_file
    #         resp = self.client.post("/a/upload/", data)
    #         self.assertEqual(resp.url, '/a/test-audi/')
    #         self.assertEqual(resp.status_code, 302)
    #         resp = self.client.get(resp.url)
    #         self.assertEqual(resp.status_code, 200)
    #         self.assertFalse(self.project.name in resp.content.decode())


PROCESSING_MEDIA = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=PROCESSING_MEDIA)
class AudioProcessingTestCase(TestCase):
    """The file is decoded with ffmpeg only when it is new or replaced."""

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(PROCESSING_MEDIA, ignore_errors=True)

    def setUp(self):
        self.user = User.objects.create_user("john", "lenon@beatles.com", "yoko")

    def create_audio(self):
        audio = Audio(user=self.user, name="tone", audio=get_test_audiofile())
        audio.save()
        return audio

    def test_new_audio_is_processed(self):
        audio = self.create_audio()
        self.assertIsNotNone(audio.samplerate)
        self.assertTrue(os.path.exists(audio.audio.path + '.json'))
        self.assertTrue(os.path.exists(audio.audio.path + '.big.json'))

    def test_saving_metadata_does_not_reprocess(self):
        audio = self.create_audio()
        with mock.patch("audio.models.audio_processing") as processing:
            audio.description = "new desc"
            audio.save()
            reloaded = Audio.objects.get(pk=audio.pk)
            reloaded.name = "renamed"
            reloaded.save()
        processing.assert_not_called()

    def test_replacing_the_file_reprocesses(self):
        audio = Audio.objects.get(pk=self.create_audio().pk)
        with open(os.path.join(TEST_DATA_PATH, u'tone.ogg'), 'rb') as f:
            audio.audio = SimpleUploadedFile("other.ogg", f.read())
        with mock.patch("audio.models.audio_processing") as processing:
            audio.save()
        processing.assert_called_once_with(audio)

    def test_silent_file_is_accepted(self):
        import io
        from pydub import AudioSegment
        buf = io.BytesIO()
        AudioSegment.silent(duration=3000).export(buf, format="wav")
        audio = Audio(user=self.user, name="pista vacia", audio=SimpleUploadedFile("vacia.wav", buf.getvalue()))
        audio.save()
        self.assertIsNotNone(audio.samplerate)

    def test_deferred_file_is_not_loaded_nor_reprocessed(self):
        self.create_audio()
        with mock.patch("audio.models.audio_processing") as processing:
            audio = Audio.objects.only("id", "name", "user").get()
            self.assertEqual(audio.get_deferred_fields() & {"audio"}, {"audio"})
            audio.save(update_fields=["name"])
        processing.assert_not_called()
