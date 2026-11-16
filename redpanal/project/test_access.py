"""Privacy stages: who sees, listens to and contributes to a work, and what leaks nowhere."""
import os
import shutil
import tempfile

from actstream.models import Action
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase, override_settings
from django.urls import reverse

from audio.models import Audio
from social.models import Message
from .models import Project, Contribution, Membership
from .search_indexes import ProjectIndex
from audio.search_indexes import AudioIndex
from .test_collaboration import tone

TEMP_MEDIA = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class AccessTestCase(TestCase):

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA, ignore_errors=True)

    def setUp(self):
        self.lucia = User.objects.create_user("lucia", "l@example.com", "pw")
        self.tincho = User.objects.create_user("tincho", "t@example.com", "pw")
        self.stranger = User.objects.create_user("stranger", "s@example.com", "pw")

    def work(self, visibility, name="Lluvia en Pichincha"):
        self.client.login(username="lucia", password="pw")
        self.client.post(reverse("create"), {
            "audio": tone(), "name": name, "status": "idea", "visibility": visibility,
            "missing": ["bass"], "part_instrument": "guitar"})
        self.client.logout()
        project = Project.objects.get(name=name)
        return project, project.parts().get().audio

    def as_user(self, username):
        self.client.logout()
        if username:
            self.client.login(username=username, password="pw")

    def stream_status(self, audio):
        return self.client.get(reverse("audio-stream", args=[audio.pk])).status_code

    # -- private ------------------------------------------------------------

    def test_private_work_is_invisible_from_outside(self):
        project, audio = self.work("private")
        for who in (None, "stranger"):
            self.as_user(who)
            self.assertEqual(self.client.get(project.get_absolute_url()).status_code, 404)
            self.assertEqual(self.stream_status(audio), 404)
            self.assertEqual(self.client.get(reverse("audio_peaks_json", args=[audio.pk])).status_code, 404)
            self.assertEqual(self.client.get(audio.get_absolute_url()).status_code, 404)
            self.assertEqual(self.client.get(reverse("project-parts-zip", args=[project.slug])).status_code, 404)
            self.assertNotContains(self.client.get(reverse("explore") + "?ver=obras"), project.name)

    def test_owner_and_invited_people_listen(self):
        project, audio = self.work("private")
        self.as_user("lucia")
        self.assertEqual(self.stream_status(audio), 302)
        self.client.post(reverse("project-invite", args=[project.slug]), {"username": "@tincho"})
        self.assertTrue(project.is_member(self.tincho))
        self.as_user("tincho")
        self.assertEqual(self.client.get(project.get_absolute_url()).status_code, 200)
        response = self.client.get(reverse("audio-stream", args=[audio.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], audio.audio.url)

    def test_new_uploads_have_unguessable_addresses(self):
        project, audio = self.work("private")
        folder = audio.audio.name.split("/")[-2]
        self.assertEqual(len(audio.audio.name.split("/")), 5)
        self.assertGreaterEqual(len(folder), 20)

    def test_private_audio_stays_out_of_listings_api_and_feeds(self):
        project, audio = self.work("private")
        self.as_user("stranger")
        api = self.client.get("/api/audio/list/").json()
        self.assertNotIn(audio.pk, [a["id"] for a in api["results"]])
        self.assertEqual(self.client.get("/api/audio/by-slug/%s/" % audio.slug).status_code, 404)
        self.assertNotContains(self.client.get(reverse("user-tracks", args=["lucia"])), audio.name)
        self.assertFalse(Action.objects.filter(public=True, verb__in=["audio_created", "project_created"],
                                               actor_object_id=str(self.lucia.pk)).exists())
        self.assertFalse(AudioIndex().is_public(audio))
        self.assertFalse(ProjectIndex().is_public(project))

    def test_comments_on_private_work_are_not_public(self):
        project, audio = self.work("private")
        self.as_user("lucia")
        self.client.post(reverse("project-comment", args=[project.slug]), {"msg": "nota #secreta"})
        message = Message.objects.get(object_id=project.pk)
        self.assertFalse(Action.objects.get(verb="commented").public)
        self.as_user("stranger")
        self.assertNotContains(self.client.get(reverse("hashtaged-list", args=["secreta"])), "nota")

    def test_strangers_cannot_contribute_or_comment(self):
        project, audio = self.work("private")
        self.as_user("stranger")
        self.assertEqual(self.client.get(reverse("project-contribute", args=[project.slug])).status_code, 404)
        self.assertEqual(self.client.post(reverse("project-comment", args=[project.slug]),
                                          {"msg": "hola"}).status_code, 404)

    # -- link ---------------------------------------------------------------

    def test_secret_link_gives_access_and_lets_people_join(self):
        project, audio = self.work("link")
        self.as_user(None)
        self.assertEqual(self.client.get(project.get_absolute_url()).status_code, 404)
        self.assertEqual(self.client.get(project.get_absolute_url() + "?k=wrong").status_code, 404)
        self.assertEqual(self.client.get(project.get_share_url()).status_code, 200)
        self.assertEqual(self.stream_status(audio), 302)  # the link is remembered in the session

        self.as_user("tincho")
        self.client.get(project.get_share_url())
        self.assertFalse(project.can_contribute(self.tincho))
        self.client.post(reverse("project-join", args=[project.slug]))
        self.assertTrue(project.can_contribute(self.tincho))

    # -- open call ----------------------------------------------------------

    def test_open_call_shows_needs_and_preview_but_not_the_work(self):
        project, audio = self.work("open_call")
        project.refresh_from_db()
        self.assertTrue(project.preview)
        self.assertTrue(os.path.exists(project.preview.path))
        self.as_user(None)
        self.assertContains(self.client.get(reverse("explore") + "?ver=obras"), project.name)
        page = self.client.get(project.get_absolute_url())
        self.assertTemplateUsed(page, "project/project_open_call.html")
        self.assertContains(page, project.preview.url)
        self.assertNotContains(page, audio.get_stream_url())
        self.assertEqual(self.stream_status(audio), 404)
        self.assertTrue(ProjectIndex().is_public(project))
        self.assertFalse(AudioIndex().is_public(audio))

    def test_asking_to_join_an_open_call(self):
        project, audio = self.work("open_call")
        self.as_user("tincho")
        response = self.client.get(reverse("project-contribute", args=[project.slug]))
        self.assertRedirects(response, project.get_absolute_url(), fetch_redirect_response=False)
        self.client.post(reverse("project-access-request", args=[project.slug]), {"message": "toco el bajo"})
        membership = Membership.objects.get(project=project, user=self.tincho)
        self.assertEqual(membership.status, Membership.REQUESTED)
        self.assertEqual(self.stream_status(audio), 404)

        self.as_user("lucia")
        self.assertEqual([n.kind for n in self.client.get(reverse("index")).context["notices"]], ["access_requested"])
        self.assertContains(self.client.get(project.get_absolute_url()), "toco el bajo")
        self.client.post(reverse("project-member-decide", args=[project.slug, membership.pk]), {"decision": "accept"})
        self.as_user("tincho")
        self.assertEqual(self.stream_status(audio), 302)
        self.assertEqual(self.client.get(reverse("project-contribute", args=[project.slug])).status_code, 200)

    def test_only_the_owner_manages_access(self):
        project, audio = self.work("open_call")
        self.as_user("stranger")
        self.assertEqual(self.client.post(reverse("project-invite", args=[project.slug]),
                                          {"username": "stranger"}).status_code, 403)
        self.assertEqual(self.client.post(reverse("project-visibility", args=[project.slug]),
                                          {"visibility": "public", "confirm_public": "1"}).status_code, 403)

    # -- publishing ---------------------------------------------------------

    def test_publishing_needs_confirmation_and_opens_everything(self):
        project, audio = self.work("private")
        self.as_user("lucia")
        self.client.post(reverse("project-visibility", args=[project.slug]), {"visibility": "public"})
        project.refresh_from_db()
        self.assertEqual(project.visibility, "private")

        self.client.post(reverse("project-visibility", args=[project.slug]),
                         {"visibility": "public", "confirm_public": "1"})
        project.refresh_from_db()
        self.assertEqual(project.visibility, "public")
        self.assertTrue(Action.objects.get(verb="project_created").public)
        self.as_user(None)
        self.assertEqual(self.stream_status(audio), 302)
        self.assertTrue(AudioIndex().is_public(Audio.objects.get(pk=audio.pk)))

    def test_closing_a_work_moves_old_files_out_of_guessable_addresses(self):
        project, audio = self.work("public")
        old_name = "uploads/audios/2016_01/vieja.mp3"
        os.makedirs(os.path.join(TEMP_MEDIA, "uploads/audios/2016_01"), exist_ok=True)
        os.replace(audio.audio.path, os.path.join(TEMP_MEDIA, old_name))
        Audio.objects.filter(pk=audio.pk).update(audio=old_name)
        project.set_visibility("private")
        audio.refresh_from_db()
        self.assertNotEqual(audio.audio.name, old_name)
        self.assertTrue(os.path.exists(audio.audio.path))
        self.assertFalse(os.path.exists(os.path.join(TEMP_MEDIA, old_name)))

    # -- contribution terms and proof -----------------------------------------

    def test_contributing_follows_the_license_of_the_work_by_default(self):
        project, audio = self.work("public")
        self.as_user("tincho")
        self.client.post(reverse("project-contribute", args=[project.slug]), {"audio": tone("tone.ogg")})
        track = project.contributions.get(contributor=self.tincho)
        self.assertIsNotNone(track.terms_accepted_at)
        self.assertEqual(track.audio.license, project.license)

    def test_publishing_warns_about_parts_without_consent(self):
        project, audio = self.work("private")
        Membership.objects.create(project=project, user=self.tincho)
        other = Audio.objects.create(user=self.tincho, name="bajo viejo", audio=tone("tone.ogg"))
        Contribution.objects.create(project=project, audio=other, contributor=self.tincho,
                                    status=Contribution.INCLUDED)  # older part: no terms_accepted_at
        self.as_user("lucia")
        response = self.client.get(reverse("project-settings", args=[project.slug]))
        self.assertEqual(response.context["without_consent"], [self.tincho])

    def test_proof_of_authorship(self):
        project, audio = self.work("private")
        self.as_user("stranger")
        self.assertEqual(self.client.get(reverse("project-certificate", args=[project.slug])).status_code, 404)
        self.as_user("lucia")
        response = self.client.get(reverse("project-certificate", args=[project.slug]))
        audio.refresh_from_db()
        self.assertEqual(len(audio.sha256), 64)
        self.assertContains(response, audio.sha256)
