"""Integration of the alternative wireframes: layers, collaborations, genealogy, profile and archive."""
import datetime
import io
import shutil
import tempfile

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from audio.models import Audio
from social.models import Message
from .models import Project, PartRequest, Contribution, Membership, WorkSource, Attachment
from .test_collaboration import tone

TEMP_MEDIA = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class LayersTestCase(TestCase):

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA, ignore_errors=True)

    def setUp(self):
        self.lucia = User.objects.create_user("lucia", "l@example.com", "pw")
        self.tincho = User.objects.create_user("tincho", "t@example.com", "pw")
        self.carla = User.objects.create_user("carla", "c@example.com", "pw")
        self.lucia.userprofile.location = "Rosario"
        self.lucia.userprofile.save()
        self.login("lucia")
        self.client.post(reverse("create"), {
            "audio": tone(), "name": "Lluvia", "status": "idea", "visibility": "public",
            "missing": ["bass"], "missing_text": "un bajo tranqui", "part_instrument": "guitar"})
        self.work = Project.objects.get(name="Lluvia")
        self.client.logout()

    def login(self, who):
        self.client.logout()
        self.client.login(username=who, password="pw")

    def add_layer(self, who="tincho", instrument="bass"):
        self.login(who)
        self.client.post(reverse("project-contribute", args=[self.work.slug]), {
            "audio": tone("tone.ogg"), "instrument": instrument, "offset_ms": "0", "accept_terms": "1"})
        return self.work.contributions.filter(contributor__username=who).latest("created_at")

    # -- home for visitors -----------------------------------------------------

    def test_visitor_home_explains_layers_and_shows_a_real_demo(self):
        contribution = self.add_layer()
        contribution.set_status(Contribution.INCLUDED)
        self.client.logout()
        response = self.client.get("/")
        self.assertEqual(response.context["demo"], self.work)
        self.assertContains(response, 'id="como-funciona"')
        self.assertContains(response, "Rosario")  # where the collaboration comes from
        self.assertContains(response, reverse("project-contribute", args=[self.work.slug]))

    # -- project ---------------------------------------------------------------------

    def test_layers_grouped_by_instrument_with_the_wanted_slot_inline(self):
        self.login("tincho")
        response = self.client.get(self.work.get_absolute_url())
        groups = response.context["layer_groups"]
        self.assertEqual([len(g["layers"]) for g in groups], [1, 0])
        self.assertEqual([r.instrument for r in groups[1]["wanted"]], ["bass"])
        self.assertContains(response, "rp-track-wanted")

    def test_versions_are_one_click_away_and_only_the_owner_adopts(self):
        self.add_layer()
        version = self.work.latest_version()
        Membership.objects.create(project=self.work, user=self.carla, status=Membership.ACTIVE)
        self.login("carla")
        html = self.client.get(self.work.get_absolute_url()).content.decode()
        self.assertIn("?v=%d" % version.number, html)
        self.assertNotIn(reverse("project-version-restore", args=[self.work.slug, version.number]),
                         self.client.get(self.work.get_absolute_url() + "?v=%d" % version.number).content.decode())
        self.login("lucia")
        self.assertContains(self.client.get(self.work.get_absolute_url() + "?v=%d" % version.number),
                            reverse("project-version-restore", args=[self.work.slug, version.number]))

    def test_a_collaboration_past_its_date_is_closed(self):
        request = self.work.requests.get()
        request.open_until = timezone.localdate() - datetime.timedelta(days=1)
        request.save()
        self.assertEqual(list(self.work.open_requests()), [])
        self.assertNotIn(request, list(self.client.get(reverse("explore")).context["sections"]["pedidos"]["items"]))

    def test_lyrics_and_chords_are_for_everyone(self):
        Attachment.objects.create(project=self.work, uploaded_by=self.lucia, name="letra.txt",
                                  file=SimpleUploadedFile("letra.txt", b"la lluvia..."), size=11)
        response = self.client.get(self.work.get_absolute_url())
        self.assertEqual([a.name for a in response.context["documents"]], ["letra.txt"])
        self.assertEqual(response.context["attachments"], [])

    def test_credits_export(self):
        contribution = self.add_layer()
        contribution.set_status(Contribution.INCLUDED)
        self.client.logout()
        response = self.client.get(reverse("project-credits", args=[self.work.slug]))
        text = response.content.decode()
        self.assertIn("Lluvia", text)
        self.assertIn("tincho", text)
        self.assertIn("attachment", response["Content-Disposition"])

    def test_replies_hang_from_a_comment(self):
        self.login("lucia")
        self.client.post(reverse("project-comment", args=[self.work.slug]), {"msg": "¿qué les parece?"})
        parent = Message.objects.get(msg="¿qué les parece?")
        self.client.post(reverse("project-comment", args=[self.work.slug]), {"msg": "me gusta", "parent": parent.pk})
        self.assertEqual(Message.objects.get(msg="me gusta").parent, parent)
        response = self.client.get(self.work.get_absolute_url())
        self.assertEqual(list(response.context["comments"]), [parent])
        self.assertContains(response, "me gusta")

    def test_following_a_project_brings_its_news_to_comunidad(self):
        self.login("carla")
        self.client.post(reverse("project-follow", args=[self.work.slug]))
        self.add_layer("tincho")
        self.login("carla")
        kinds = [item["kind"] for item in self.client.get(reverse("index")).context["feed"]]
        self.assertIn("layer", kinds)

    # -- sound ---------------------------------------------------------------------------

    def test_add_a_sound_to_an_existing_project(self):
        sound = Audio.objects.create(user=self.tincho, name="Candombe", audio=tone())
        self.login("lucia")
        page = self.client.get(sound.get_absolute_url())
        self.assertIn(self.work, list(page.context["my_projects"]))
        self.client.post(reverse("sound-add-to-project", args=[sound.pk]), {"project": self.work.pk})
        self.assertTrue(WorkSource.objects.filter(project=self.work, audio=sound).exists())
        self.assertEqual(list(self.tincho.notifications.values_list("kind", flat=True)), ["used_as_source"])
        self.assertContains(self.client.get(sound.get_absolute_url()), "rp-gen-node")

    def test_cannot_add_to_someone_elses_project(self):
        sound = Audio.objects.create(user=self.tincho, name="Candombe", audio=tone())
        self.login("carla")
        response = self.client.post(reverse("sound-add-to-project", args=[sound.pk]), {"project": self.work.pk})
        self.assertEqual(response.status_code, 404)

    # -- profile -----------------------------------------------------------------------

    def test_profile_shows_who_they_played_with_and_collaborations_only_to_the_owner(self):
        contribution = self.add_layer()
        contribution.set_status(Contribution.INCLUDED)
        self.tincho.userprofile.instruments = ["bass"]
        self.tincho.userprofile.open_to_collaborate = True
        self.tincho.userprofile.genres = "candombe, cumbia"
        self.tincho.userprofile.save()
        PartRequest.objects.create(project=self.work, instrument="bass", description="otro bajo")
        self.login("carla")
        page = self.client.get(self.tincho.get_absolute_url())
        self.assertIn(self.lucia, page.context["played_with"])
        self.assertContains(page, "cumbia")
        # What matches what you play shows in your Comunidad, not on your profile.
        self.login("tincho")
        self.assertNotContains(self.client.get(self.tincho.get_absolute_url()), "otro bajo")
        feed = self.client.get(reverse("index")).context["feed"]
        self.assertIn(self.work, [i["work"] for i in feed if i.get("reason")])

    def test_invite_to_a_project_from_the_profile(self):
        self.login("lucia")
        page = self.client.get(self.carla.get_absolute_url())
        self.assertIn(self.work, page.context["invite_to"])
        self.client.post(reverse("project-invite", args=[self.work.slug]), {"username": "@carla"})
        self.assertTrue(self.work.is_member(self.carla))

    # -- archive ------------------------------------------------------------------------

    def test_sounds_sorted_by_most_picked_up_and_removable_filter_chips(self):
        quiet = Audio.objects.create(user=self.tincho, name="Quieto", audio=tone(), genre="folklore")
        loved = Audio.objects.create(user=self.tincho, name="Querido", audio=tone(), genre="folklore")
        WorkSource.objects.create(project=self.work, audio=loved)
        response = self.client.get(reverse("explore"), {"ver": "sonidos", "orden": "retomados", "genero": "folklore"})
        names = [s.name for s in response.context["sections"]["sonidos"]["items"]]
        self.assertEqual(names[:2], ["Querido", "Quieto"])
        chips = response.context["active_filters"]
        self.assertEqual(len(chips), 1)
        self.assertNotIn("genero", chips[0]["url"])
        self.assertContains(response, "rp-archive")
