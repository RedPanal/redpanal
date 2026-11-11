"""Review of RedPanal 3.0 (PR #160): what isn't public must not leak through feeds, the API or downloads."""
import json
import shutil
import tempfile
from unittest.mock import patch

from actstream import action
from actstream.actions import follow
from actstream.models import Action
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase, override_settings
from django.urls import reverse

from audio.models import Audio
from moderation.views import set_hidden
from project.models import Contribution, Membership, Project, Version
from project.test_collaboration import tone
from social.models import Message, message_is_public, visible_messages

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

    def test_restoring_a_sound_restores_its_announcement(self):
        sound = Audio.objects.create(user=self.lucia, name="Pad", audio=tone())
        announcement = Action.objects.get(verb="audio_created", action_object_object_id=str(sound.pk))
        self.assertTrue(announcement.public)
        set_hidden(sound, True)
        announcement.refresh_from_db()
        self.assertFalse(announcement.public)
        set_hidden(sound, False)
        announcement.refresh_from_db()
        self.assertTrue(announcement.public)

    def test_comunidad_hides_replies_to_hidden_comments_even_with_a_stale_flag(self):
        from social.following import community_feed
        work, _audio, _part = self.work_with_part()
        parent = Message.objects.create(msg="padre", user=self.lucia, content_object=work)
        reply = Message.objects.create(msg="respuesta", user=self.lucia, parent=parent,
                                       content_type=parent.content_type, object_id=parent.object_id)
        follow(self.tincho, self.lucia, send_action=False, actor_only=True)
        Action.objects.filter(verb="commented", action_object_object_id=str(reply.pk)).update(public=True)
        # Simulate an old row whose stored flag was never resynced.
        Message.objects.filter(pk=parent.pk).update(moderation_hidden=True)
        comments = [item["object"].pk for item in community_feed(self.tincho) if item["kind"] == "comment"]
        self.assertNotIn(reply.pk, comments)

    def test_a_comment_on_a_deleted_target_is_not_public(self):
        ct = ContentType.objects.get_for_model(Project)
        orphan = Message.objects.create(msg="huérfano", user=self.lucia, content_type=ct, object_id=999999)
        post = Message.objects.create(msg="post general", user=self.lucia)
        self.assertFalse(message_is_public(orphan))
        self.assertFalse(visible_messages(Message.objects.filter(pk=orphan.pk), None).exists())
        self.assertTrue(visible_messages(Message.objects.filter(pk=post.pk), None).exists())

    @patch("redpanal.utils.search.reindex")
    def test_reindex_search_includes_comments_on_the_work_audio(self, reindex):
        work, audio, _part = self.work_with_part()
        comment = Message.objects.create(msg="en la parte", user=self.tincho, content_object=audio)
        work.reindex_search()
        self.assertIn(comment, reindex.call_args[0][0])

    def test_hidden_versions_are_not_in_version_navigation(self):
        work, _audio, _part = self.work_with_part()
        first = work.save_version(self.lucia)
        hidden = work.save_version(self.lucia)
        work.save_version(self.lucia)
        Version.objects.filter(pk=hidden.pk).update(hidden=True)
        self.client.login(username="tincho", password="pw")
        page = self.client.get(reverse("project-version", args=[work.slug, 3]))
        self.assertEqual(page.context["previous"].pk, first.pk)

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

    def test_a_hidden_work_has_no_certificate_for_its_members(self):
        work, _audio, _part = self.work_with_part()
        Membership.objects.create(project=work, user=self.tincho)
        Project.objects.filter(pk=work.pk).update(moderation_hidden=True)
        self.client.login(username="tincho", password="pw")
        self.assertEqual(self.client.get(reverse("project-certificate", args=[work.slug])).status_code, 404)

    def test_certificate_leaves_out_hidden_parts_of_someone_else(self):
        work, _audio, _part = self.work_with_part()
        hidden = Audio.objects.create(user=self.tincho, name="Bajo oculto", audio=tone("tone.ogg"))
        Contribution.objects.create(project=work, audio=hidden, contributor=self.tincho,
                                    status=Contribution.INCLUDED)
        Audio.objects.filter(pk=hidden.pk).update(moderation_hidden=True)
        self.client.login(username="lucia", password="pw")
        rows = self.client.get(reverse("project-certificate", args=[work.slug])).context["rows"]
        self.assertNotIn(hidden, [contribution.audio for contribution, _digest in rows])

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

    def test_private_object_urls_are_not_expanded_in_comments(self):
        from django.contrib.sites.models import Site
        Project.objects.create(user=self.lucia, name="Obra privada", slug="privada", visibility="private")
        domain = Site.objects.get_current().domain
        html = Message.to_html("mirá http://%s/p/privada/" % domain)
        self.assertNotIn("Obra privada", html)

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

    # -- P2 / P3 --------------------------------------------------------------------------------

    def test_changing_the_password_revokes_api_tokens(self):
        token = self.token("lucia")
        self.assertEqual(self.client.get("/api/activity/me/", **token).status_code, 200)
        self.lucia.set_password("otra")
        self.lucia.save()
        self.assertEqual(self.client.get("/api/activity/me/", **token).status_code, 401)

    def test_a_bad_limit_does_not_break_popular_tags(self):
        self.assertEqual(self.client.get("/api/tags/popular/?limit=abc").status_code, 200)
        self.assertEqual(self.client.get("/api/tags/popular/?limit=-5").status_code, 200)

    def test_api_comments_have_the_same_length_limit_as_the_site(self):
        sound = Audio.objects.create(user=self.lucia, name="Pad", audio=tone())
        self.client.post("/api/audio/%s/comments/" % sound.slug, {"msg": "a" * 5000}, **self.token("tincho"))
        self.assertEqual(len(Message.objects.get().msg), 1000)
