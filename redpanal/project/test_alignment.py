"""Parts that line up in time play together; the rest play on their own until someone aligns them."""
import shutil
import tempfile

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from audio.models import Audio
from .models import Project, Contribution, Version, VISIBILITY_OPEN_CALL, guess_alignment, durations_match
from .test_collaboration import tone

TEMP_MEDIA = tempfile.mkdtemp()


def lasting(ms):
    """An unsaved audio that lasts `ms` milliseconds (enough for the duration heuristics)."""
    return Audio(samplerate=1000, totalframes=ms)


@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class AlignmentTestCase(TestCase):

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA, ignore_errors=True)

    def setUp(self):
        self.lucia = User.objects.create_user("lucia", "l@example.com", "pw")
        self.tincho = User.objects.create_user("tincho", "t@example.com", "pw")
        self.stranger = User.objects.create_user("stranger", "s@example.com", "pw")

    def work(self, visibility="public", **extra):
        self.client.login(username="lucia", password="pw")
        data = {"audio": tone(), "name": "Lluvia en Pichincha", "status": "idea", "visibility": visibility,
                "missing": ["bass"], "part_instrument": "guitar"}
        data.update(extra)
        self.client.post(reverse("create"), data)
        self.client.logout()
        return Project.objects.get(name="Lluvia en Pichincha")

    def set_length(self, audio, ms):
        Audio.objects.filter(pk=audio.pk).update(samplerate=1000, totalframes=ms)

    def contribute(self, project, user="tincho", **extra):
        self.client.login(username=user, password="pw")
        data = {"audio": tone("tone.ogg"), "instrument": "bass", "offset_ms": "0", "accept_terms": "1"}
        data.update(extra)
        response = self.client.post(reverse("project-contribute", args=[project.slug]), data)
        self.client.logout()
        return response

    # -- heuristics ----------------------------------------------------------

    def test_durations_match_tolerates_rounding_only(self):
        self.assertTrue(durations_match(180000, 180040))
        self.assertTrue(durations_match(600000, 602900))  # 0.5 % on long takes
        self.assertFalse(durations_match(180000, 150000))
        self.assertFalse(durations_match(None, 180000))

    def test_the_first_part_sets_the_timeline(self):
        project = self.work()
        self.assertEqual(project.parts().get().alignment, Contribution.ALIGNED)
        empty = Project.objects.create(user=self.lucia, name="Vacía", slug="vacia")
        self.assertEqual(guess_alignment(empty, lasting(30000)), Contribution.ALIGNED)

    def test_a_part_as_long_as_the_aligned_ones_is_aligned(self):
        project = self.work()
        self.set_length(project.parts().get().audio, 180000)
        self.assertEqual(guess_alignment(project, lasting(180020)), Contribution.ALIGNED)
        self.assertEqual(guess_alignment(project, lasting(42000)), Contribution.PENDING)

    def test_stems_uploaded_together_share_the_longest_duration(self):
        empty = Project.objects.create(user=self.lucia, name="Vacía", slug="vacia")
        batch = [180000, 180010, 12000]
        self.assertEqual(guess_alignment(empty, lasting(180000), batch), Contribution.ALIGNED)
        self.assertEqual(guess_alignment(empty, lasting(12000), batch), Contribution.PENDING)

    # -- contribute ------------------------------------------------------------

    def test_a_part_of_another_length_waits_to_be_aligned(self):
        project = self.work()
        self.set_length(project.parts().get().audio, 180000)
        self.contribute(project, user="lucia")
        part = project.contributions.exclude(contributor=self.lucia, audio__instrument="guitar").get()
        self.assertEqual(part.alignment, Contribution.PENDING)
        self.assertNotIn(part, project.aligned_parts())
        self.assertIn(part, project.loose_parts())

    def test_lining_up_by_ear_puts_the_part_in_the_player(self):
        project = self.work()
        self.set_length(project.parts().get().audio, 180000)
        self.contribute(project, user="lucia", aligned_by_ear="1", offset_ms="-120")
        part = project.contributions.get(audio__instrument="bass")
        self.assertEqual(part.alignment, Contribution.ALIGNED)
        self.assertEqual(part.offset_ms, -120)
        self.assertIn(part, project.aligned_parts())

    def test_loose_parts_are_files_like_the_others(self):
        project = self.work()
        self.set_length(project.parts().get().audio, 180000)
        self.contribute(project, user="lucia")
        response = self.client.get(project.get_absolute_url())
        self.assertEqual(len(response.context["aligned_parts"]), 1)
        self.assertEqual(len(response.context["loose_parts"]), 1)
        part = response.context["loose_parts"][0]
        # No separate section: every file of the work is a row with its own play; no "play the work".
        self.assertContains(response, 'id="capa-%d"' % part.pk)
        self.assertNotContains(response, 'id="sueltas"')
        self.assertNotContains(response, "rp-playerbar")
        self.client.login(username="lucia", password="pw")
        self.assertContains(self.client.get(project.get_absolute_url()),
                            reverse("contribution-align", args=[project.slug, part.pk]))

    # -- align page --------------------------------------------------------------

    def loose_part(self):
        project = self.work()
        self.set_length(project.parts().get().audio, 180000)
        self.contribute(project)
        part = project.contributions.get(contributor=self.tincho)
        self.client.login(username="lucia", password="pw")
        self.client.post(reverse("contribution-status", args=[project.slug, part.pk]), {"status": "included"})
        self.client.logout()
        part.refresh_from_db()
        self.assertEqual(part.alignment, Contribution.PENDING)
        return project, part

    def test_only_the_owner_and_the_contributor_align(self):
        project, part = self.loose_part()
        url = reverse("contribution-align", args=[project.slug, part.pk])
        self.assertEqual(self.client.get(url).status_code, 302)  # login first
        self.client.login(username="stranger", password="pw")
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.post(url, {"decision": "aligned", "offset_ms": "0"}).status_code, 403)
        for who in ("lucia", "tincho"):
            self.client.login(username=who, password="pw")
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "data-align-target")

    def test_align_with_an_offset(self):
        project, part = self.loose_part()
        self.client.login(username="tincho", password="pw")
        response = self.client.post(reverse("contribution-align", args=[project.slug, part.pk]),
                                    {"decision": "aligned", "offset_ms": "-2500"})
        self.assertRedirects(response, project.get_absolute_url() + "#partes", fetch_redirect_response=False)
        part.refresh_from_db()
        self.assertEqual((part.alignment, part.offset_ms), (Contribution.ALIGNED, -2500))
        self.assertIn(part, project.aligned_parts())

    def test_mark_a_part_as_independent(self):
        project, part = self.loose_part()
        self.client.login(username="lucia", password="pw")
        self.client.post(reverse("contribution-align", args=[project.slug, part.pk]), {"decision": "separate"})
        part.refresh_from_db()
        self.assertEqual(part.alignment, Contribution.SEPARATE)
        self.assertIn(part, project.loose_parts())

    def test_offset_is_clamped(self):
        project, part = self.loose_part()
        self.client.login(username="lucia", password="pw")
        self.client.post(reverse("contribution-align", args=[project.slug, part.pk]),
                         {"decision": "aligned", "offset_ms": "99999999"})
        part.refresh_from_db()
        self.assertEqual(part.offset_ms, 600000)

    def test_version_page_plays_aligned_parts_and_lists_the_rest(self):
        project, part = self.loose_part()
        version = project.save_version(self.lucia)
        response = self.client.get(reverse("project-version", args=[project.slug, version.number]))
        self.assertEqual([c.pk for c in response.context["parts"]], [project.aligned_parts().get().pk])
        self.assertEqual([c.pk for c in response.context["loose_parts"]], [part.pk])


@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class PlayersEverywhereTestCase(TestCase):
    """Cards and lists play in place, with a waveform, for everyone who can listen."""

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
            "missing": ["bass"], "part_instrument": "guitar"})
        self.client.logout()
        self.project = Project.objects.get(name="Lluvia en Pichincha")

    def test_anonymous_home_has_players(self):
        response = self.client.get(reverse("index"))
        self.assertContains(response, "data-combined-wave")
        self.assertContains(response, self.project.parts().get().audio.get_stream_url())

    def test_logged_in_home_has_players_for_others_works(self):
        self.client.login(username="tincho", password="pw")
        self.client.post(reverse("person-follow", args=["lucia"]))
        response = self.client.get(reverse("index"))
        self.assertIn(self.project, [item["work"] for item in response.context["feed"]])
        self.assertContains(response, "data-combined-wave")
        self.assertContains(response, "data-track")

    def test_open_call_cards_play_only_the_preview(self):
        audio = self.project.parts().get().audio
        self.project.visibility = VISIBILITY_OPEN_CALL
        self.project.save()
        self.project.refresh_preview()
        self.project.refresh_from_db()
        response = self.client.get(reverse("explore") + "?ver=pedidos")
        self.assertNotContains(response, audio.get_stream_url())
        if self.project.preview:
            self.assertContains(response, self.project.preview.url)
