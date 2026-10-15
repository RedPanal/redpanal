"""What each page puts first, according to the interaction design."""
import re
import shutil
import tempfile

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Project, Contribution, Membership
from .test_collaboration import tone

TEMP_MEDIA = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class HierarchyTestCase(TestCase):

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA, ignore_errors=True)

    def setUp(self):
        self.lucia = User.objects.create_user("lucia", "l@example.com", "pw")
        self.tincho = User.objects.create_user("tincho", "t@example.com", "pw")
        self.client.login(username="lucia", password="pw")
        self.client.post(reverse("create"), {
            "audio": tone(), "name": "Lluvia en Pichincha", "status": "idea", "visibility": "public",
            "missing": ["bass"], "missing_text": "un bajo tranqui", "part_instrument": "guitar"})
        self.work = Project.objects.get(name="Lluvia en Pichincha")

    def order_of(self, html, *markers):
        positions = [html.find(m) for m in markers]
        self.assertNotIn(-1, positions, dict(zip(markers, positions)))
        return positions

    # -- work page -------------------------------------------------------------

    def test_owner_adds_a_part_from_the_top(self):
        html = self.client.get(self.work.get_absolute_url()).content.decode()
        header = html[html.find('class="rp-obra-head"'):html.find("</header>", html.find('class="rp-obra-head"'))]
        add = reverse("project-contribute", args=[self.work.slug])
        self.assertIn('class="btn rp-btn-primary" href="%s"' % add, header)
        menu = header[header.find("dropdown-menu"):]
        self.assertNotIn(add, menu)

    def test_sections_follow_the_designed_order(self):
        html = self.client.get(self.work.get_absolute_url()).content.decode()
        # Collaborations show as slots among the layers; their detail lives in the side column.
        positions = self.order_of(html, 'id="partes"', 'id="conversacion"', 'id="pedidos"', 'id="historia"')
        self.assertEqual(positions, sorted(positions))

    def test_access_lives_in_the_settings_and_requests_to_join_on_the_page(self):
        self.work.set_visibility("open_call")
        membership = Membership.objects.create(project=self.work, user=self.tincho, status=Membership.REQUESTED,
                                               message="toco bajo")
        html = self.client.get(self.work.get_absolute_url()).content.decode()
        self.assertNotIn('id="acceso"', html)
        self.assertIn(reverse("project-settings", args=[self.work.slug]), html)
        self.assertLess(html.find('id="solicitudes"'), html.find('id="partes"'))  # waiting for a decision: first
        self.assertIn("toco bajo", html)
        settings = self.client.get(reverse("project-settings", args=[self.work.slug]))
        self.assertContains(settings, 'id="acceso"')
        self.assertContains(settings, reverse("project-delete", args=[self.work.slug]))
        # Answering a request goes back to the work; changing access, to the settings.
        response = self.client.post(reverse("project-member-decide", args=[self.work.slug, membership.pk]),
                                    {"decision": "accept"})
        self.assertRedirects(response, self.work.get_absolute_url(), fetch_redirect_response=False)
        response = self.client.post(reverse("project-visibility", args=[self.work.slug]), {"visibility": "private"})
        self.assertRedirects(response, reverse("project-settings", args=[self.work.slug]),
                             fetch_redirect_response=False)

    def test_settings_are_only_for_the_author(self):
        self.client.logout()
        self.client.login(username="tincho", password="pw")
        self.assertEqual(self.client.get(reverse("project-settings", args=[self.work.slug])).status_code, 403)

    def test_a_request_shows_once(self):
        html = self.client.get(self.work.get_absolute_url()).content.decode()
        self.assertEqual(html.count("un bajo tranqui"), 1)
        self.assertNotIn("rp-track-missing", html)

    def test_empty_lineage_and_studio_files_stay_out_of_the_way(self):
        self.client.logout()
        html = self.client.get(self.work.get_absolute_url()).content.decode()
        self.assertNotIn('id="linaje-title"', html)
        # "More data" holds at least the license; what has nothing in it stays out.
        fold = html[html.find('id="historia"'):html.find("</details>", html.find('id="historia"'))]
        self.assertIn('rel="license"', fold)
        for empty in ('id="versiones"', 'id="alternativas"', 'id="archivos"'):
            self.assertNotIn(empty, fold)

    def test_follow_download_and_stems_live_in_the_menu(self):
        self.client.logout()
        self.client.login(username="tincho", password="pw")
        html = self.client.get(self.work.get_absolute_url()).content.decode()
        start = html.find('class="rp-obra-head"')
        header = html[start:html.find("</header>", start)]
        menu = header[header.find("dropdown-menu"):]
        self.assertIn(reverse("project-follow", args=[self.work.slug]), menu)
        self.assertNotIn('href="#juntos"', html)  # a single file: nothing to hear in sync

    def test_the_page_proposes_more_to_listen(self):
        other = Project.objects.create(user=self.tincho, name="Otra zamba", slug="otra", visibility="public")
        other.tags.add("zamba")
        self.work.tags.add("zamba")
        response = self.client.get(self.work.get_absolute_url())
        self.assertIn(other, [i["obj"] for i in response.context["more_to_listen"]])
        self.assertContains(response, 'id="mas-title"')

    def test_history_and_files_fold_together(self):
        self.client.post(reverse("project-version-create", args=[self.work.slug]), {"message": "primera"})
        html = self.client.get(self.work.get_absolute_url()).content.decode()
        self.assertRegex(html, r'<details class="rp-card rp-history" id="historia">')
        fold = html[html.find('id="historia"'):html.find("</details>", html.find('id="historia"'))]
        self.assertIn('id="versiones"', fold)

    def test_versions_are_made_on_their_own(self):
        # No "Save version" button: adding a file makes the next version.
        html = self.client.get(self.work.get_absolute_url()).content.decode()
        self.assertNotIn('id="version-form"', html)
        self.assertNotIn('href="#version-form"', html)

    def test_open_call_preview_uses_the_shared_player(self):
        self.work.set_visibility("open_call")
        self.work.refresh_preview()
        self.client.logout()
        html = self.client.get(self.work.get_absolute_url()).content.decode()
        self.assertNotIn("<audio", html)
        if self.work.preview:
            self.assertIn("data-combined-wave", html)

    # -- contribute ----------------------------------------------------------------

    def test_adding_a_track_is_record_or_choose_a_file(self):
        self.client.logout()
        self.client.login(username="tincho", password="pw")
        html = self.client.get(reverse("project-contribute", args=[self.work.slug])).content.decode()
        record, choose = self.order_of(html, "data-rec-start", 'for="id_audio"')
        self.assertLess(record, choose)
        # Nothing else to decide: no alignment by ear, no license checkbox, no instrument to pick.
        for gone in ('id="id_offset_ms"', "data-nudge", 'name="accept_terms"', 'id="id_instrument"', "rp-daw"):
            self.assertNotIn(gone, html)
        self.assertIn('name="note"', html)

    def test_the_track_comes_in_with_the_license_and_the_instrument_of_the_collaboration(self):
        self.client.logout()
        self.client.login(username="tincho", password="pw")
        bass = self.work.requests.get(instrument="bass")
        self.client.post(reverse("project-contribute", args=[self.work.slug]),
                         {"audio": tone("tone.ogg", "toma1.ogg"), "request": bass.pk})
        track = self.work.contributions.get(contributor=self.tincho)
        self.assertIsNotNone(track.terms_accepted_at)
        self.assertEqual((track.audio.instrument, track.request), ("bass", bass))

    # -- profile -----------------------------------------------------------------

    def test_profile_shows_instruments_works_contributions_and_sounds(self):
        self.tincho.userprofile.instruments = ["bass", "sinthesizer"]
        self.tincho.userprofile.save()
        self.client.logout()
        self.client.login(username="tincho", password="pw")
        self.client.post(reverse("project-contribute", args=[self.work.slug]), {
            "audio": tone("tone.ogg"), "instrument": "bass", "offset_ms": "0", "accept_terms": "1"})
        contribution = self.work.contributions.get(contributor=self.tincho)
        contribution.status = Contribution.INCLUDED
        contribution.save()
        self.client.logout()

        response = self.client.get(reverse("user-tracks", args=["tincho"]))
        self.assertTemplateUsed(response, "users/profile.html")
        html = response.content.decode()
        self.assertIn("Bajo", html)
        self.assertIn("Lluvia en Pichincha", html)
        self.assertNotIn("Seguidores", html)
        self.assertNotIn("followers", html)
        self.assertEqual([c.pk for c in response.context["contributions"]], [contribution.pk])

    def test_profile_hides_private_works(self):
        self.work.set_visibility("private")
        self.client.logout()
        response = self.client.get(reverse("user-tracks", args=["lucia"]))
        self.assertNotContains(response, "Lluvia en Pichincha")
        self.assertEqual(list(response.context["works"]), [])
        self.assertNotContains(response, 'id="obras"')

    def test_own_profile_invites_to_fill_the_gaps(self):
        response = self.client.get(reverse("user-tracks", args=["lucia"]))
        self.assertContains(response, reverse("user-profile"))
        self.assertNotContains(response, 'id="aportes"')  # nothing to show yet: no empty section

    def test_old_projects_tab_goes_to_the_profile(self):
        response = self.client.get(reverse("user-projects", args=["lucia"]))
        self.assertRedirects(response, reverse("user-tracks", args=["lucia"]))
