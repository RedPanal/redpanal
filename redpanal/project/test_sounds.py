"""Explore sounds, downloads and declared sources."""
import shutil
import tempfile

from actstream.models import Action
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from audio.models import Audio, Download
from .models import Project, WorkSource
from .test_collaboration import tone

TEMP_MEDIA = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class SoundsTestCase(TestCase):

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA, ignore_errors=True)

    def setUp(self):
        self.mica = User.objects.create_user("mica", "m@example.com", "pw")
        self.tincho = User.objects.create_user("tincho", "t@example.com", "pw")
        self.candombe = Audio.objects.create(user=self.mica, name="Candombe chico", audio=tone(),
                                             use_type="loop", instrument="drums", tempo=100, musical_key="Am")
        self.shaker = Audio.objects.create(user=self.mica, name="Shaker", audio=tone("tone.ogg"),
                                           use_type="sample", instrument="drums", tempo=120)

    def explore(self, **params):
        params["ver"] = "sonidos"
        return self.client.get(reverse("explore"), params)

    def names(self, response):
        return [s.name for s in response.context["sections"]["sonidos"]["items"]]

    def test_filters(self):
        self.assertEqual(set(self.names(self.explore())), {"Candombe chico", "Shaker"})
        self.assertEqual(self.names(self.explore(tipo="loop")), ["Candombe chico"])
        self.assertEqual(self.names(self.explore(bpm_min=95, bpm_max=105)), ["Candombe chico"])
        self.assertEqual(self.names(self.explore(tonalidad="am")), ["Candombe chico"])
        self.assertEqual(self.names(self.explore(q="shak")), ["Shaker"])
        self.assertEqual(self.names(self.explore(bpm_min="abc")), self.names(self.explore()))

    def test_parts_of_works_are_not_loose_sounds(self):
        project = Project.objects.create(name="Obra", user=self.mica)
        from .models import Contribution
        Contribution.objects.create(project=project, audio=self.shaker, contributor=self.mica, status="included")
        self.assertEqual(self.names(self.explore()), ["Candombe chico"])

    def test_download_is_remembered_and_suggested_as_source(self):
        self.client.login(username="tincho", password="pw")
        response = self.client.get(reverse("audio-download", args=[self.candombe.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment", response["Content-Disposition"])
        self.assertTrue(Download.objects.filter(user=self.tincho, audio=self.candombe).exists())
        self.assertContains(self.client.get(reverse("my-downloads")), "Candombe chico")

        # What you downloaded is suggested as what a new upload comes from.
        from .upload import _origin_choices
        self.assertIn("a:%d" % self.candombe.pk, [value for value, _label in _origin_choices(self.tincho, None)])

        self.client.post(reverse("create"), {
            "audio": tone(), "name": "Lluvia (remix)", "status": "in_progress", "visibility": "public",
            "sources": [self.candombe.pk]})
        work = Project.objects.get(name="Lluvia (remix)")
        self.assertEqual(list(work.sources.values_list("audio", flat=True)), [self.candombe.pk])
        self.assertTrue(Action.objects.filter(verb="used_as_source", target_object_id=str(self.candombe.pk)).exists())
        self.assertContains(self.client.get(work.get_absolute_url()), "Candombe chico")
        self.assertContains(self.client.get(self.candombe.get_absolute_url()), "Lluvia (remix)")

    def test_sources_cannot_be_sounds_never_downloaded(self):
        self.client.login(username="tincho", password="pw")
        response = self.client.post(reverse("create"), {
            "audio": tone(), "name": "Trampa", "status": "idea", "visibility": "public",
            "sources": [self.shaker.pk]})
        self.assertFalse(Project.objects.filter(name="Trampa").exists())

    def test_based_on_a_work_is_declared_as_source(self):
        source = Project.objects.create(name="Original", user=self.mica, visibility="public")
        self.client.login(username="tincho", password="pw")
        self.client.post(reverse("create") + "?from=original", {
            "audio": tone(), "name": "Derivada", "status": "idea", "visibility": "public", "source": source.pk})
        derived = Project.objects.get(name="Derivada")
        self.assertEqual(derived.version_of, source)
        self.assertTrue(WorkSource.objects.filter(project=derived, source_project=source).exists())

    def test_downloading_a_private_part_is_not_possible(self):
        project = Project.objects.create(name="Secreta", user=self.mica, visibility="private")
        from .models import Contribution
        Contribution.objects.create(project=project, audio=self.shaker, contributor=self.mica, status="included")
        self.client.login(username="tincho", password="pw")
        self.assertEqual(self.client.get(reverse("audio-download", args=[self.shaker.pk])).status_code, 404)
