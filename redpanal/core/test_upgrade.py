"""What broke for data that came from before 3.0, found after deploying 3.2: waveforms and threads."""
import os
import shutil
import tempfile

from actstream import action
from actstream.actions import follow
from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from audio.models import Audio
from project.test_collaboration import tone
from social.following import community_feed
from social.models import Message

TEMP_MEDIA = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class UpgradeTestCase(TestCase):

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA, ignore_errors=True)

    def setUp(self):
        self.lucia = User.objects.create_user("lucia", "l@example.com", "pw")
        self.tincho = User.objects.create_user("tincho", "t@example.com", "pw")
        self.sound = Audio.objects.create(user=self.lucia, name="Pad", audio=tone())

    def old_upload(self):
        """A sound as 2.x left it: the file, no .json waveforms."""
        for suffix in (".json", ".big.json"):
            os.remove(self.sound.audio.path + suffix)
        return reverse("audio_peaks_json", args=[self.sound.pk])

    # -- waveforms ------------------------------------------------------------------------

    def test_a_sound_without_waveform_files_still_tells_its_duration(self):
        data = self.client.get(self.old_upload()).json()
        self.assertEqual(data["peaks"], [])
        self.assertGreater(data["duration"], 0)

    def test_build_waveforms_makes_the_missing_files(self):
        url = self.old_upload()
        call_command("build_waveforms", stdout=open(os.devnull, "w"))
        self.assertTrue(os.path.exists(self.sound.audio.path + ".big.json"))
        self.assertEqual(len(self.client.get(url).json()["peaks"]), 400)

    def test_build_waveforms_goes_on_when_a_file_is_missing_or_broken(self):
        gone = Audio.objects.create(user=self.lucia, name="Perdido", audio=tone())
        os.remove(gone.audio.path)
        self.old_upload()
        call_command("build_waveforms", stdout=open(os.devnull, "w"), stderr=open(os.devnull, "w"))
        self.assertTrue(os.path.exists(self.sound.audio.path + ".json"))

    # -- threads ---------------------------------------------------------------------------

    def thread(self):
        comment = Message.objects.create(msg="primer comentario", user=self.tincho, content_object=self.sound)
        self.client.login(username="lucia", password="pw")
        self.client.post(reverse("reply", args=["comentario", comment.pk]), {"msg": "la respuesta"})
        return comment, Message.objects.get(msg="la respuesta")

    def test_replies_on_a_sound_page_hang_from_their_comment(self):
        comment, reply = self.thread()
        self.assertEqual(reply.parent, comment)
        html = self.client.get(self.sound.get_absolute_url()).content.decode()
        start = html.index('id="c%d"' % comment.pk)
        nested = html.index('class="rp-replies"', start)
        self.assertLess(nested, html.index("la respuesta"))
        self.assertLess(html.index("primer comentario"), html.index("la respuesta"))
        # ...and each comment can be answered right there.
        self.assertIn(reverse("reply", args=["comentario", comment.pk]), html)

    def test_explore_lists_threads_not_loose_replies(self):
        self.thread()
        html = self.client.get(reverse("explore") + "?ver=comentarios").content.decode()
        self.assertIn("primer comentario", html)
        self.assertNotIn("la respuesta", html)

    def test_the_feed_shows_a_reply_inside_its_thread_once(self):
        comment, _reply = self.thread()
        follow(self.tincho, self.lucia, send_action=False, actor_only=True)
        items = [i for i in community_feed(self.tincho) if i["kind"] == "comment"]
        self.assertEqual([i["object"] for i in items], [comment])

    def test_the_activity_page_survives_verbs_without_a_template(self):
        action.send(self.lucia, verb="started following", target=self.tincho)
        self.assertEqual(self.client.get(reverse("user-activities", args=["lucia"])).status_code, 200)

    # -- settings ----------------------------------------------------------------------------

    def test_cors_is_not_open_to_every_origin(self):
        from django.conf import settings
        self.assertFalse(getattr(settings, "CORS_ALLOW_ALL_ORIGINS", False))
        r = self.client.get("/api/tags/popular/", HTTP_ORIGIN="https://otro.example")
        self.assertNotIn("Access-Control-Allow-Origin", r)
        r = self.client.get("/api/tags/popular/", HTTP_ORIGIN="http://localhost:5173")
        self.assertEqual(r["Access-Control-Allow-Origin"], "http://localhost:5173")
