"""Tests for the collaboration cycle: create a work, contribute, decide, save versions."""
import io
import os
import shutil
import tempfile
import zipfile

from actstream.models import Action
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from audio.models import Audio
from audio.uploads import prepare_audio_file
from social.models import Message
from .models import Project, PartRequest, Contribution, Version

TEST_DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "audio", "test_data")
TEMP_MEDIA = tempfile.mkdtemp()


def tone(name="tone.mp3", as_name=None):
    with open(os.path.join(TEST_DATA, name), "rb") as f:
        return SimpleUploadedFile(as_name or name, f.read())


@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class CollaborationTestCase(TestCase):

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA, ignore_errors=True)

    def setUp(self):
        self.lucia = User.objects.create_user("lucia", "l@example.com", "pw")
        self.tincho = User.objects.create_user("tincho", "t@example.com", "pw")

    def create_work(self, **extra):
        self.client.login(username="lucia", password="pw")
        data = {"audio": tone(), "name": "Lluvia en Pichincha", "status": "idea",
                "visibility": "public", "missing": ["bass", "drums"],
                "missing_text": "un bajo tranqui", "part_instrument": "guitar"}
        data.update(extra)
        response = self.client.post(reverse("create"), data)
        self.client.logout()
        return response, Project.objects.get(name=data["name"])

    def contribute(self, project, user="tincho", **extra):
        self.client.login(username=user, password="pw")
        data = {"audio": tone("tone.ogg"), "instrument": "bass", "offset_ms": "-40",
                "note": "probé algo con walking", "accept_terms": "1"}
        data.update(extra)
        response = self.client.post(reverse("project-contribute", args=[project.slug]), data)
        self.client.logout()
        return response

    def set_status(self, project, contribution, status, user):
        self.client.login(username=user, password="pw")
        response = self.client.post(reverse("contribution-status", args=[project.slug, contribution.pk]),
                                    {"status": status})
        self.client.logout()
        return response

    # -- flow 1: publish an idea ------------------------------------------

    def test_create_work_from_upload(self):
        response, project = self.create_work()
        self.assertRedirects(response, project.get_absolute_url(), fetch_redirect_response=False)
        self.assertEqual(project.status, "idea")
        self.assertEqual(project.user, self.lucia)
        part = project.parts().get()
        self.assertEqual(part.contributor, self.lucia)
        self.assertEqual(part.audio.instrument, "guitar")
        self.assertIn(part.audio, project.audios.all())
        self.assertEqual(sorted(project.requests.values_list("instrument", flat=True)), ["bass", "drums"])

    def test_create_work_requires_login(self):
        response = self.client.get(reverse("create"))
        self.assertEqual(response.status_code, 302)

    def test_create_work_with_trim_converts_to_mp3(self):
        response, project = self.create_work(trim_start_ms="100", trim_end_ms="600")
        audio = project.parts().get().audio
        self.assertTrue(audio.audio.name.endswith(".mp3"))
        self.assertLessEqual(audio.get_duration(), 600)

    def test_create_work_based_on_another(self):
        _, source = self.create_work()
        response, derived = self.create_work(name="Lluvia (remix)", source=str(source.pk))
        self.assertEqual(derived.version_of, source)
        self.assertIn(derived, source.versions.all())

    def test_browser_recording_formats_are_accepted(self):
        converted = prepare_audio_file(tone("tone.ogg", as_name="grabacion.webm"))
        self.assertTrue(converted.name.endswith(".mp3"))

    # -- flow 4: contribute = make a version -------------------------------

    def test_contributing_makes_a_version_without_asking(self):
        _, project = self.create_work()
        bass = project.requests.get(instrument="bass")
        response = self.contribute(project, request=str(bass.pk))
        contribution = project.contributions.get(contributor=self.tincho)
        self.assertEqual(contribution.status, Contribution.VERSIONED)
        self.assertEqual((contribution.request, contribution.offset_ms), (bass, -40))
        # Lucía's version stays as it is; Tincho's has her files and his.
        self.assertEqual(project.parts().count(), 1)
        self.assertNotIn(contribution.audio, project.audios.all())
        v1, v2 = project.versions_saved.order_by("number")
        self.assertEqual((v1.created_by, v1.contributions.count()), (self.lucia, 1))
        self.assertEqual((v2.created_by, v2.contributions.count(), v2.parent), (self.tincho, 2, v1))
        self.assertRedirects(response, "%s?v=2" % project.get_absolute_url(), fetch_redirect_response=False)
        self.assertTrue(Action.objects.filter(verb="contributed", actor_object_id=str(self.tincho.pk)).exists())
        self.assertEqual(list(self.lucia.notifications.values_list("kind", flat=True)), ["contributed"])

    def test_a_version_can_come_from_another_version(self):
        _, project = self.create_work()
        self.contribute(project)
        carla = User.objects.create_user("carla", "c@example.com", "pw")
        self.client.login(username="carla", password="pw")
        self.client.post(reverse("project-contribute", args=[project.slug]), {
            "audio": tone("tone.ogg"), "instrument": "drums", "offset_ms": "0", "accept_terms": "1", "version": "2"})
        v3 = project.versions_saved.get(number=3)
        self.assertEqual((v3.created_by, v3.parent.number, v3.contributions.count()), (carla, 2, 3))

    def test_listening_to_a_version_and_coming_back(self):
        _, project = self.create_work()
        self.contribute(project)
        theirs = project.contributions.get(contributor=self.tincho)
        page = self.client.get(project.get_absolute_url())
        self.assertNotContains(page, 'id="capa-%d"' % theirs.pk)
        self.assertContains(page, "?v=2")  # the other versions, one click away
        version = self.client.get(project.get_absolute_url() + "?v=2")
        self.assertContains(version, 'id="capa-%d"' % theirs.pk)
        self.assertEqual(version.context["viewing"].number, 2)
        self.assertNotContains(version, reverse("project-version-restore", args=[project.slug, 2]))  # only the author adopts

    def test_the_author_adopts_a_version(self):
        _, project = self.create_work()
        self.contribute(project)
        theirs = project.contributions.get(contributor=self.tincho)
        self.client.login(username="lucia", password="pw")
        self.assertContains(self.client.get(project.get_absolute_url() + "?v=2"),
                            reverse("project-version-restore", args=[project.slug, 2]))
        self.client.post(reverse("project-version-restore", args=[project.slug, 2]))
        theirs.refresh_from_db()
        self.assertEqual(theirs.status, Contribution.INCLUDED)
        self.assertEqual({c["user"] for c in project.credits()}, {self.lucia, self.tincho})
        self.assertEqual(project.current_version().number, 2)
        self.assertIn("included", self.tincho.notifications.values_list("kind", flat=True))

    def test_the_author_hides_a_version_from_the_page(self):
        _, project = self.create_work()
        self.contribute(project)
        self.client.login(username="lucia", password="pw")
        self.assertContains(self.client.get(reverse("project-settings", args=[project.slug])),
                            reverse("project-version-hide", args=[project.slug, 2]))
        self.client.post(reverse("project-version-hide", args=[project.slug, 2]))
        self.client.logout()
        self.assertIsNone(self.client.get(project.get_absolute_url() + "?v=2").context["viewing"])
        self.client.login(username="tincho", password="pw")  # still there for whoever made it
        self.assertEqual(self.client.get(project.get_absolute_url() + "?v=2").context["viewing"].number, 2)

    def test_contribute_suggests_a_request_the_person_can_cover(self):
        _, project = self.create_work()
        self.tincho.userprofile.instruments = ["bass"]
        self.tincho.userprofile.save()
        self.client.login(username="tincho", password="pw")
        form = self.client.get(reverse("project-contribute", args=[project.slug])).context["form"]
        self.assertEqual(form.initial["instrument"], "bass")
        self.assertEqual(form.initial["request"], project.requests.get(instrument="bass"))

    def test_owner_adds_part_directly(self):
        _, project = self.create_work()
        self.contribute(project, user="lucia")
        self.assertEqual(project.parts().count(), 2)
        self.assertEqual(project.current_version().contributions.count(), 2)  # a new version, on its own

    # -- older works: proposals that waited for a decision ---------------------

    def legacy_proposal(self, project):
        audio = Audio.objects.create(user=self.tincho, name="Bajo viejo", audio=tone("tone.ogg"))
        return Contribution.objects.create(project=project, audio=audio, contributor=self.tincho,
                                           status=Contribution.PROPOSED, note="probé algo con walking",
                                           request=project.requests.get(instrument="bass"))

    def test_owner_includes_an_older_proposal_and_can_undo(self):
        _, project = self.create_work()
        contribution = self.legacy_proposal(project)
        self.client.login(username="lucia", password="pw")
        response = self.client.post(reverse("contribution-status", args=[project.slug, contribution.pk]),
                                    {"status": "included", "close_request": "1"})
        self.client.logout()
        self.assertRedirects(response, project.get_absolute_url(), fetch_redirect_response=False)
        contribution.refresh_from_db()
        self.assertEqual(contribution.status, Contribution.INCLUDED)
        self.assertIn(contribution.audio, project.audios.all())
        self.assertFalse(project.requests.get(instrument="bass").is_open)
        self.assertEqual(project.current_version().contributions.count(), 2)

        self.set_status(project, contribution, "proposed", "lucia")
        contribution.refresh_from_db()
        self.assertEqual(contribution.status, Contribution.PROPOSED)
        self.assertNotIn(contribution.audio, project.audios.all())

    def test_alternative_keeps_the_audio(self):
        _, project = self.create_work()
        contribution = self.legacy_proposal(project)
        self.set_status(project, contribution, "alternative", "lucia")
        self.assertEqual(list(project.alternatives()), [contribution])
        self.assertTrue(Audio.objects.filter(pk=contribution.audio_id).exists())

    def test_only_owner_decides(self):
        _, project = self.create_work()
        contribution = self.legacy_proposal(project)
        self.assertEqual(self.set_status(project, contribution, "included", "tincho").status_code, 403)

    def test_only_contributor_withdraws(self):
        _, project = self.create_work()
        contribution = self.legacy_proposal(project)
        self.assertEqual(self.set_status(project, contribution, "withdrawn", "lucia").status_code, 403)
        self.set_status(project, contribution, "withdrawn", "tincho")
        contribution.refresh_from_db()
        self.assertEqual(contribution.status, Contribution.WITHDRAWN)

    def test_owner_listens_to_each_proposal_on_its_own(self):
        _, project = self.create_work()
        proposal = self.legacy_proposal(project)
        self.client.login(username="lucia", password="pw")
        response = self.client.get(project.get_absolute_url())
        # Files are rarely in sync: each proposal plays alone, no "with it / without it".
        self.assertContains(response, 'data-item-id="%d"' % proposal.audio_id)
        self.assertNotContains(response, 'data-candidate')
        self.assertContains(response, "probé algo con walking")

    # -- versions and credits ---------------------------------------------

    def test_a_saved_version_credits_everyone_and_thanks(self):
        _, project = self.create_work()
        self.contribute(project)
        self.client.login(username="lucia", password="pw")
        self.client.post(reverse("project-version-restore", args=[project.slug, 2]))
        response = self.client.post(reverse("project-version-create", args=[project.slug]),
                                    {"message": "¡Gracias! Quedó hermoso."})
        version = project.latest_version()
        self.assertRedirects(response, version.get_absolute_url())
        self.assertEqual(version.contributions.count(), 2)
        self.assertEqual({c["user"] for c in version.credits()}, {self.lucia, self.tincho})
        self.assertTrue(Message.objects.filter(msg__startswith="@tincho").exists())
        self.assertEqual(self.client.get(version.get_absolute_url()).status_code, 200)

    def test_version_keeps_parts_after_later_changes(self):
        _, project = self.create_work()
        version = project.save_version(self.lucia)
        self.contribute(project, user="lucia")
        self.assertEqual(version.contributions.count(), 1)
        self.assertEqual(project.parts().count(), 2)

    # -- requests, comments, downloads ------------------------------------

    def test_requests_are_managed_by_owner(self):
        _, project = self.create_work()
        self.client.login(username="lucia", password="pw")
        self.client.post(reverse("project-request-create", args=[project.slug]),
                         {"instrument": "voice", "description": "segunda voz"})
        voice = project.requests.get(instrument="voice")
        self.client.post(reverse("project-request-toggle", args=[project.slug, voice.pk]))
        voice.refresh_from_db()
        self.assertFalse(voice.is_open)
        self.client.logout()
        self.client.login(username="tincho", password="pw")
        response = self.client.post(reverse("project-request-toggle", args=[project.slug, voice.pk]))
        self.assertEqual(response.status_code, 403)

    def test_comment_anchored_to_a_moment(self):
        _, project = self.create_work()
        self.client.login(username="tincho", password="pw")
        self.client.post(reverse("project-comment", args=[project.slug]),
                         {"msg": "¡qué lindo este arranque!", "at_ms": "42000"})
        comment = Message.objects.get(object_id=project.pk)
        self.assertEqual(comment.at_ms, 42000)
        self.assertContains(self.client.get(project.get_absolute_url()), "0:42")

    def test_parts_zip(self):
        _, project = self.create_work()
        response = self.client.get(reverse("project-parts-zip", args=[project.slug]))
        self.assertEqual(response.status_code, 200)
        archive = zipfile.ZipFile(io.BytesIO(b"".join(response.streaming_content)))
        self.assertEqual(len(archive.namelist()), 1)
        self.assertTrue(archive.namelist()[0].startswith("01-guitar"))

    # -- navigation -------------------------------------------------------

    def test_a_new_contribution_notifies_the_owner_and_requests_filter_by_instrument(self):
        _, project = self.create_work()
        self.contribute(project)
        self.client.login(username="lucia", password="pw")
        response = self.client.get(reverse("index"))
        self.assertEqual([n.kind for n in response.context["notices"]], ["contributed"])
        self.assertContains(response, "Lluvia en Pichincha")
        self.client.logout()

        response = self.client.get(reverse("explore"), {"ver": "pedidos", "instrumento": "bass"})
        self.assertContains(response, "?pedido=%d" % project.requests.get(instrument="bass").pk)
        self.assertNotContains(response, "?pedido=%d" % project.requests.get(instrument="drums").pk)

    def test_public_pages(self):
        _, project = self.create_work()
        _, hidden = self.create_work(name="Secreta", visibility="link")
        for url in [reverse("index"), reverse("explore"), reverse("explore") + "?ver=obras",
                    project.get_absolute_url()]:
            self.assertEqual(self.client.get(url).status_code, 200, url)
        explore = self.client.get(reverse("explore") + "?ver=obras")
        self.assertContains(explore, "Lluvia en Pichincha")
        self.assertNotContains(explore, "Secreta")
        self.assertEqual(self.client.get(hidden.get_absolute_url()).status_code, 404)
        self.assertEqual(self.client.get(hidden.get_share_url()).status_code, 200)

    def test_my_stuff(self):
        _, project = self.create_work()
        self.contribute(project)
        self.client.login(username="tincho", password="pw")
        response = self.client.get(reverse("my-stuff"))
        self.assertContains(response, "Lluvia en Pichincha")
