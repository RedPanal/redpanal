"""Reports, the moderators' panel, and hiding without deleting."""
import shutil
import tempfile

from actstream.models import Action
from django.contrib.auth.models import Group, User
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase, override_settings
from django.urls import reverse

from audio.models import Audio
from project.models import Contribution, Project, WorkSource
from project.test_collaboration import tone
from social.models import Message
from .models import MODERATORS_GROUP, Report, is_moderator

TEMP_MEDIA = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class ModerationTestCase(TestCase):

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA, ignore_errors=True)

    def setUp(self):
        self.author = User.objects.create_user("autora", "a@example.com", "pw")
        self.reporter = User.objects.create_user("vecino", "v@example.com", "pw")
        self.mod = User.objects.create_user("mod", "m@example.com", "pw")
        Group.objects.get_or_create(name=MODERATORS_GROUP)[0].user_set.add(self.mod)
        self.work = Project.objects.create(name="Obra pública", user=self.author, visibility="public")
        self.audio = Audio.objects.create(user=self.author, name="sample dudoso", audio=tone())
        Contribution.objects.create(project=self.work, audio=self.audio, contributor=self.author, status="included")
        self.work.audios.add(self.audio)
        self.derived = Project.objects.create(name="Remix", user=self.reporter, visibility="public")
        WorkSource.objects.create(project=self.derived, audio=self.audio)

    def as_user(self, user):
        self.client.logout()
        if user:
            self.client.login(username=user.username, password="pw")

    def report(self, kind, obj, reason="copyright"):
        self.as_user(self.reporter)
        return self.client.post(reverse("report-create", args=[kind, obj.pk]), {"reason": reason, "detail": "es de un disco"})

    def test_who_moderates(self):
        self.assertTrue(is_moderator(self.mod))
        self.assertFalse(is_moderator(self.reporter))
        self.assertTrue(is_moderator(User.objects.create_user("staff", "", "pw", is_staff=True)))

    def test_reporting_and_panel_access(self):
        self.report("audio", self.audio)
        report = Report.objects.get()
        self.assertEqual(report.content_object, self.audio)
        self.assertEqual(self.client.get(reverse("moderation-panel")).status_code, 403)
        self.as_user(self.mod)
        panel = self.client.get(reverse("moderation-panel"))
        self.assertContains(panel, "sample dudoso")
        self.assertContains(panel, "Remix")  # what was made from it, so the decision is informed

    def test_cannot_report_what_you_cannot_see(self):
        private = Project.objects.create(name="Privada", user=self.author, visibility="private")
        self.as_user(self.reporter)
        self.assertEqual(self.client.get(reverse("report-create", args=["obra", private.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("report-create", args=["nada", 1])).status_code, 404)

    def test_hiding_an_audio_keeps_works_and_credits(self):
        self.report("audio", self.audio)
        self.as_user(self.mod)
        self.client.post(reverse("moderation-decide", args=[Report.objects.get().pk]), {"decision": "hide"})
        self.audio.refresh_from_db()
        self.assertTrue(self.audio.moderation_hidden)
        self.assertTrue(Audio.objects.filter(pk=self.audio.pk).exists())

        self.as_user(self.reporter)
        self.assertEqual(self.client.get(reverse("audio-stream", args=[self.audio.pk])).status_code, 404)
        page = self.client.get(self.work.get_absolute_url())
        self.assertContains(page, "autora")  # the credit stays
        self.assertNotContains(page, self.audio.get_stream_url())
        self.assertEqual(self.client.get(self.derived.get_absolute_url()).status_code, 200)
        self.assertNotIn(self.audio, Audio.objects.visible_to(self.reporter))

        self.as_user(self.author)
        self.assertEqual(self.client.get(reverse("audio-stream", args=[self.audio.pk])).status_code, 302)

    def test_hiding_a_work_and_bringing_it_back(self):
        self.report("obra", self.work, "spam")
        self.as_user(self.mod)
        self.client.post(reverse("moderation-decide", args=[Report.objects.get().pk]), {"decision": "hide"})
        self.work.refresh_from_db()
        self.assertTrue(self.work.moderation_hidden)
        self.assertNotIn(self.work, Project.objects.listed())
        self.assertFalse(Action.objects.get(verb="project_created", actor_object_id=str(self.author.pk)).public)
        self.as_user(None)
        self.assertEqual(self.client.get(self.work.get_absolute_url()).status_code, 404)
        self.as_user(self.author)
        self.assertContains(self.client.get(self.work.get_absolute_url()), 'class="alert alert-warning"')

        self.as_user(self.mod)
        self.client.post(reverse("moderation-decide", args=[Report.objects.get().pk]), {"decision": "restore"})
        self.work.refresh_from_db()
        self.assertFalse(self.work.moderation_hidden)
        self.as_user(None)
        self.assertEqual(self.client.get(self.work.get_absolute_url()).status_code, 200)

    def test_hiding_a_comment(self):
        comment = Message.objects.create(msg="spam spam #oferta", user=self.reporter,
                                         content_type=ContentType.objects.get_for_model(Project), object_id=self.work.pk)
        self.as_user(self.author)
        self.client.post(reverse("report-create", args=["comentario", comment.pk]), {"reason": "spam"})
        self.as_user(self.mod)
        self.client.post(reverse("moderation-decide", args=[Report.objects.get().pk]), {"decision": "hide"})
        self.as_user(None)
        self.assertNotContains(self.client.get(self.work.get_absolute_url()), "spam spam")
        self.assertNotContains(self.client.get(reverse("hashtaged-list", args=["oferta"])), "spam spam")

    def test_dismissing(self):
        self.report("audio", self.audio)
        self.as_user(self.mod)
        self.client.post(reverse("moderation-decide", args=[Report.objects.get().pk]), {"decision": "dismiss"})
        self.assertEqual(Report.objects.get().status, Report.DISMISSED)
        self.audio.refresh_from_db()
        self.assertFalse(self.audio.moderation_hidden)

    def test_only_moderators_decide(self):
        self.report("audio", self.audio)
        self.as_user(self.reporter)
        self.assertEqual(self.client.post(reverse("moderation-decide", args=[Report.objects.get().pk]),
                                          {"decision": "hide"}).status_code, 403)
