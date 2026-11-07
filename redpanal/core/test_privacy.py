"""Review of RedPanal 3.0 (PR #160): what isn't public must not leak through feeds, the API or downloads."""
import json
import shutil
import tempfile

from actstream import action
from actstream.actions import follow
from actstream.models import Action
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase, override_settings
from django.urls import reverse

from audio.models import Audio
from moderation.views import set_hidden
from project.models import Contribution, Project, Version
from project.test_collaboration import tone
from social.models import Message, visible_messages

TEMP_MEDIA = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class PrivacyTestCase(TestCase):

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA, ignore_errors=True)

    def setUp(self):
        self.lucia = User.objects.create_user("lucia", "l@example.com", "pw")
        self.tincho = User.objects.create_user("tincho", "t@example.com", "pw")

    def token(self, username):
        r = self.client.post("/api/auth/login/", json.dumps({"username": username, "password": "pw"}),
                             content_type="application/json")
        return {"HTTP_AUTHORIZATION": "Bearer " + r.json()["token"]}

    def private_sound(self):
        return Audio.objects.create(user=self.lucia, name="Boceto secreto", audio=tone(), visibility="private")

    def comment_action(self, message):
        ct = ContentType.objects.get_for_model(Message)
        return Action.objects.get(verb="commented", action_object_content_type=ct,
                                  action_object_object_id=str(message.pk))

    def work_with_part(self, visibility="public", **kwargs):
        work = Project.objects.create(user=self.lucia, name="Obra secreta", slug="obra-secreta",
                                      visibility=visibility, **kwargs)
        audio = Audio(user=self.lucia, name="Guitarra", audio=tone())
        audio._part_of_work = True
        audio.save()
        part = Contribution.objects.create(project=work, audio=audio, contributor=self.lucia,
                                           status=Contribution.INCLUDED)
        work.audios.add(audio)
        return work, audio, part

    # -- SEC-01 / SEC-02: comments on sounds ------------------------------------------------

    def test_a_comment_on_a_private_sound_is_not_public(self):
        sound = self.private_sound()
        m = Message.objects.create(msg="hola", user=self.lucia, content_object=sound)
        self.assertFalse(self.comment_action(m).public)

    def test_a_comment_on_a_public_sound_is_public(self):
        sound = Audio.objects.create(user=self.lucia, name="Pad", audio=tone())
        m = Message.objects.create(msg="hola", user=self.tincho, content_object=sound)
        self.assertTrue(self.comment_action(m).public)

    def test_comments_on_sounds_someone_cant_hear_are_left_out(self):
        sound = self.private_sound()
        Message.objects.create(msg="nota privada", user=self.lucia, content_object=sound)
        self.assertFalse(visible_messages(Message.objects.all(), None).exists())
        self.assertFalse(visible_messages(Message.objects.all(), self.tincho).exists())
        self.assertTrue(visible_messages(Message.objects.all(), self.lucia).exists())

    def test_replies_to_a_hidden_comment_are_left_out(self):
        sound = Audio.objects.create(user=self.lucia, name="Pad", audio=tone())
        parent = Message.objects.create(msg="hola", user=self.lucia, content_object=sound)
        Message.objects.create(msg="respuesta", user=self.tincho, parent=parent,
                               content_type=parent.content_type, object_id=parent.object_id)
        set_hidden(parent, True)
        self.assertFalse(visible_messages(Message.objects.all(), None).exists())

    # -- SEC-03 / SEC-04: activity streams ------------------------------------------------

    def test_following_someone_does_not_open_their_private_work(self):
        work, _audio, _part = self.work_with_part(visibility="private")
        version = work.save_version(self.lucia)
        # A stale public flag, as left by older code: the read path must not trust it.
        action.send(self.lucia, verb="version_saved", action_object=version, target=work, public=True)
        follow(self.tincho, self.lucia, send_action=False, actor_only=True)
        feed = self.client.get("/api/activity/feed/", **self.token("tincho")).json()
        self.assertEqual([a for a in feed if a["verb"] == "version_saved"], [])

    def test_the_activity_page_does_not_show_private_actions(self):
        work, _audio, _part = self.work_with_part(visibility="private")
        version = work.save_version(self.lucia)
        action.send(self.lucia, verb="version_saved", action_object=version, target=work, public=True)
        response = self.client.get(reverse("user-activities", args=["lucia"]))
        self.assertNotContains(response, "Obra secreta")

    def test_actstream_feeds_are_not_served(self):
        ct = ContentType.objects.get_for_model(User).pk
        self.assertEqual(self.client.get("/activity/feed/%d/%d/" % (ct, self.lucia.pk)).status_code, 404)

    # -- SEC-05: moderation must not republish ------------------------------------------------

    def test_hiding_a_public_work_takes_its_news_out_of_the_feeds(self):
        work, audio, part = self.work_with_part()
        version = work.save_version(self.lucia)
        action.send(self.lucia, verb="version_saved", action_object=version, target=work, public=True)
        on_part = Message.objects.create(msg="lindo", user=self.tincho, content_object=audio)
        set_hidden(work, True)
        self.assertFalse(Action.objects.filter(public=True, verb="version_saved").exists())
        self.assertFalse(self.comment_action(on_part).public)

    def test_hiding_a_sound_takes_its_comments_out_of_the_feeds(self):
        sound = Audio.objects.create(user=self.lucia, name="Pad", audio=tone())
        m = Message.objects.create(msg="hola", user=self.tincho, content_object=sound)
        set_hidden(sound, True)
        self.assertFalse(self.comment_action(m).public)
        set_hidden(sound, False)
        self.assertTrue(self.comment_action(m).public)

    # -- SEC-06: hidden versions ------------------------------------------------------------

    def test_a_hidden_version_cant_be_opened_or_downloaded(self):
        work, _audio, _part = self.work_with_part(allow_downloads=True)
        version = work.save_version(self.lucia)
        Version.objects.filter(pk=version.pk).update(hidden=True)
        self.client.login(username="tincho", password="pw")
        self.assertEqual(self.client.get(reverse("project-version", args=[work.slug, 1])).status_code, 404)
        self.assertEqual(self.client.get(reverse("project-version-mix", args=[work.slug, 1])).status_code, 404)
        detail = self.client.get("/api/works/%s/" % work.slug, **self.token("tincho")).json()
        self.assertEqual(detail["versions"], [])
        page = self.client.get(work.get_absolute_url())
        self.assertNotContains(page, reverse("project-version-mix", args=[work.slug, 1]))

    # -- SEC-07: hidden parts ---------------------------------------------------------------

    def test_a_hidden_part_is_left_out_of_downloads_and_the_api(self):
        work, audio, _part = self.work_with_part(allow_downloads=True)
        Audio.objects.filter(pk=audio.pk).update(moderation_hidden=True)
        self.client.login(username="tincho", password="pw")
        import io
        import zipfile
        response = self.client.get(reverse("project-parts-zip", args=[work.slug]))
        names = zipfile.ZipFile(io.BytesIO(b"".join(response.streaming_content))).namelist()
        self.assertEqual(names, [])
        detail = self.client.get("/api/works/%s/" % work.slug, **self.token("tincho")).json()
        self.assertEqual(detail["parts"], [])
        with self.assertRaises(ValueError):
            work.mix_audios([audio.pk])

    # -- SEC-08: hidden comments --------------------------------------------------------------

    def test_hidden_comments_stay_out_of_the_api_and_the_sound_page(self):
        sound = Audio.objects.create(user=self.lucia, name="Pad", audio=tone())
        Message.objects.create(msg="comentario oculto", user=self.tincho, content_object=sound,
                               moderation_hidden=True)
        comments = self.client.get("/api/audio/%s/comments/" % sound.slug).json()
        self.assertEqual(comments, [])
        self.assertNotContains(self.client.get(sound.get_absolute_url()), "comentario oculto")

    def test_sync_visibility_fixes_stale_flags(self):
        from django.core.management import call_command
        sound = self.private_sound()
        m = Message.objects.create(msg="hola", user=self.lucia, content_object=sound)
        Action.objects.filter(pk=self.comment_action(m).pk).update(public=True)
        call_command("sync_visibility", stdout=open("/dev/null", "w"))
        self.assertFalse(self.comment_action(m).public)

    # -- SEC-09: hidden works in Estudio and groups ---------------------------------------------

    def test_a_hidden_work_is_not_listed_in_estudio_for_its_contributors(self):
        work, _audio, _part = self.work_with_part()
        audio = Audio.objects.create(user=self.tincho, name="Bajo", audio=tone())
        Contribution.objects.create(project=work, audio=audio, contributor=self.tincho,
                                    status=Contribution.INCLUDED)
        Project.objects.filter(pk=work.pk).update(moderation_hidden=True)
        self.client.login(username="tincho", password="pw")
        self.assertNotContains(self.client.get(reverse("my-stuff")), "Obra secreta")

    # -- SEC-10: cached mixes ---------------------------------------------------------------

    def test_making_a_work_private_throws_its_cached_mixes_away(self):
        import os
        from django.conf import settings
        work, a1, _p = self.work_with_part()
        a2 = Audio(user=self.lucia, name="Bajo", audio=tone("tone.ogg"))
        a2._part_of_work = True
        a2.save()
        work.audios.add(a2)
        filename = work.mix_audios([a1.pk, a2.pk])
        path = os.path.join(settings.MEDIA_ROOT, "audio_cache", filename)
        self.assertTrue(os.path.exists(path))
        work.set_visibility("private")
        self.assertFalse(os.path.exists(path))

    # -- SEC-11: open redirects ----------------------------------------------------------------

    def test_next_cant_send_people_to_another_site(self):
        self.client.login(username="tincho", password="pw")
        response = self.client.post(reverse("person-follow", args=["lucia"]), {"next": "https://evil.example/"})
        self.assertEqual(response["Location"], self.lucia.get_absolute_url())
        response = self.client.post(reverse("message-create"), {"msg": "hola"},
                                    HTTP_REFERER="https://evil.example/")
        self.assertEqual(response["Location"], "/")

    # -- SEC-12: comments are escaped -----------------------------------------------------------

    def test_names_and_addresses_in_comments_cant_inject_markup(self):
        from django.contrib.sites.models import Site
        Audio.objects.create(user=self.lucia, name='<img src=x onerror=alert(1)>', audio=tone(), slug="pad")
        domain = Site.objects.get_current().domain
        html = Message.to_html('mirá http://%s/a/pad/ y http://x.example/"onmouseover="alert(1) <b' % domain)
        self.assertNotIn("<img", html)
        self.assertNotIn('"onmouseover', html)
        self.assertNotIn("<b", html)

    # -- QUOTA-01 --------------------------------------------------------------------------------

    def test_every_upload_counts_against_the_space(self):
        self.client.login(username="lucia", password="pw")
        with self.settings(RP_USER_QUOTA_MB=0):
            self.client.post(reverse("create-sound"), {"audio": tone(), "name": "Loop", "use_type": "loop"})
            self.client.post(reverse("create"), {"audio": tone(), "name": "Lluvia", "status": "idea",
                                                 "visibility": "public", "part_instrument": "guitar"})
            r = self.client.post("/api/audio/", {"name": "Api", "audio": tone(), "tags": "[]"}, **self.token("lucia"))
        self.assertEqual(r.status_code, 400)
        self.assertFalse(Audio.objects.exists())
