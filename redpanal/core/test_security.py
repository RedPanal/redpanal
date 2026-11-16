"""Holes found reviewing the original code: the API, following, comments and mixing."""
import json
import os
import shutil
import tempfile

from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from audio.models import Audio
from project.models import Project
from project.test_collaboration import tone
from social.models import Message

TEMP_MEDIA = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class SecurityTestCase(TestCase):

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA, ignore_errors=True)

    def setUp(self):
        self.lucia = User.objects.create_user("lucia", "l@example.com", "pw")
        self.tincho = User.objects.create_user("tincho", "t@example.com", "pw")
        self.sound = Audio.objects.create(user=self.lucia, name="Pad", audio=tone())

    def token(self, username):
        r = self.client.post("/api/auth/login/", json.dumps({"username": username, "password": "pw"}),
                             content_type="application/json")
        return {"HTTP_AUTHORIZATION": "Bearer " + r.json()["token"]}

    # -- API ---------------------------------------------------------------------------

    def test_the_api_lets_only_the_author_change_or_delete_a_sound(self):
        url = "/api/audio/%d/" % self.sound.pk
        as_tincho = self.token("tincho")
        self.assertEqual(self.client.patch(url, json.dumps({"name": "Robado"}), content_type="application/json",
                                           **as_tincho).status_code, 403)
        self.assertEqual(self.client.delete(url, **as_tincho).status_code, 403)
        self.sound.refresh_from_db()
        self.assertEqual((self.sound.name, self.sound.user), ("Pad", self.lucia))

    def test_the_api_does_not_hand_a_sound_to_someone_else(self):
        url = "/api/audio/%d/" % self.sound.pk
        response = self.client.patch(url, json.dumps({"name": "Pad 2", "user_id": self.tincho.pk}),
                                     content_type="application/json", **self.token("lucia"))
        self.assertEqual(response.status_code, 200)
        self.sound.refresh_from_db()
        self.assertEqual((self.sound.name, self.sound.user), ("Pad 2", self.lucia))

    def test_the_api_source_must_be_a_sound_you_can_hear(self):
        hidden = Audio.objects.create(user=self.tincho, name="Oculto", audio=tone(), moderation_hidden=True)
        response = self.client.patch("/api/audio/%d/" % self.sound.pk, json.dumps({"source_audio_id": hidden.pk}),
                                     content_type="application/json", **self.token("lucia"))
        self.assertEqual(response.status_code, 400)

    # -- following ------------------------------------------------------------------------

    def test_following_needs_a_post_with_the_csrf_token(self):
        from actstream.models import Follow
        client = Client(enforce_csrf_checks=True)
        client.login(username="tincho", password="pw")
        url = reverse("actstream_follow", args=[ContentType.objects.get_for_model(User).pk, self.lucia.pk])
        self.assertEqual(client.get(url).status_code, 405)
        self.assertEqual(client.post(url).status_code, 403)  # what another site could send: no token
        self.assertFalse(Follow.objects.exists())

    # -- comments ---------------------------------------------------------------------------

    def comment(self, obj, text):
        return self.client.post(reverse("message-with-content-create"), {
            "msg": text, "content_type": ContentType.objects.get_for_model(obj).pk, "object_id": obj.pk})

    def test_comments_need_an_account_and_access(self):
        secret = Project.objects.create(user=self.lucia, name="Secreto", slug="secreto", visibility="private")
        self.assertEqual(self.comment(self.sound, "anónimo").status_code, 302)
        self.client.login(username="tincho", password="pw")
        self.assertEqual(self.comment(secret, "me meto").status_code, 403)
        self.assertEqual(self.comment(self.lucia, "en tu usuario").status_code, 403)
        self.comment(self.sound, "qué lindo pad")
        self.assertEqual(list(Message.objects.values_list("msg", flat=True)), ["qué lindo pad"])

    # -- mixing -----------------------------------------------------------------------------

    def test_a_file_that_failed_does_not_break_the_mix(self):
        project = Project.objects.create(user=self.lucia, name="Mezcla", slug="mezcla", visibility="public")
        other = Audio.objects.create(user=self.lucia, name="Bajo", audio=tone("tone.ogg"))
        broken = Audio.objects.create(user=self.lucia, name="Roto", audio=tone())
        Audio.objects.filter(pk=broken.pk).update(hashsum=None)
        os.remove(broken.audio.path)
        project.audios.add(self.sound, other, broken)
        filename = project.mix_audios([self.sound.pk, other.pk, broken.pk])
        self.assertTrue(os.path.exists(os.path.join(TEMP_MEDIA, "audio_cache", filename)))
