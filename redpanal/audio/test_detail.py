"""The page of a sound: what it is first, technical data on demand, and a way to use it."""
import shutil
import tempfile

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from project.models import Project, WorkSource
from project.test_collaboration import tone
from .models import Audio

TEMP_MEDIA = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class SoundPageTestCase(TestCase):

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA, ignore_errors=True)

    def setUp(self):
        self.tincho = User.objects.create_user("tincho", "t@example.com", "pw")
        self.lucia = User.objects.create_user("lucia", "l@example.com", "pw")
        self.client.login(username="tincho", password="pw")
        self.client.post(reverse("create-sound"), {
            "audio": tone(), "name": "Candombe chico", "use_type": "loop", "instrument": "drums",
            "tempo": "100", "musical_key": "La menor"})
        self.sound = Audio.objects.get(name="Candombe chico")
        self.client.logout()

    def test_tempo_and_key_first_technical_data_folded(self):
        html = self.client.get(self.sound.get_absolute_url()).content.decode()
        header = html[:html.find("</header>", html.find("rp-obra-head"))]
        self.assertIn('<span class="rp-label">100 BPM</span>', header)
        self.assertIn("La menor", header)
        self.assertNotIn("Hz", header)
        self.assertRegex(html, r'<details class="rp-card">\s*<summary class="rp-sec mb-0">')
        # Download is an icon under the waveform; the license, only among the technical data.
        actions = html[html.find("rp-file-actions"):]
        self.assertIn(reverse("audio-download", args=[self.sound.pk]), actions[:actions.find("</div>\n</div>") + 2000])
        technical = html[html.find("rp-techdata"):]
        self.assertIn('rel="license"', technical)
        self.assertEqual(html.count('rel="license"'), 1)

    def test_use_it_in_a_new_work_credits_the_sound(self):
        self.client.login(username="lucia", password="pw")
        html = self.client.get(self.sound.get_absolute_url()).content.decode()
        use_url = "%s?sonido=%d" % (reverse("create"), self.sound.pk)
        self.assertIn(use_url, html)
        response = self.client.get(use_url)
        self.assertEqual(response.context["sound"], self.sound)  # shown as where the upload comes from
        self.client.post(use_url, {
            "audio": tone(), "name": "Con candombe", "status": "idea", "visibility": "public",
            "part_instrument": "guitar", "sources": [self.sound.pk]})
        work = Project.objects.get(name="Con candombe")
        self.assertTrue(WorkSource.objects.filter(project=work, audio=self.sound).exists())
        self.assertContains(self.client.get(self.sound.get_absolute_url()), "Con candombe")

    def test_the_author_does_not_get_use_it(self):
        self.client.login(username="tincho", password="pw")
        self.assertNotContains(self.client.get(self.sound.get_absolute_url()), "?sonido=")

    def test_a_track_of_a_work_has_its_own_page_like_any_file(self):
        self.client.login(username="lucia", password="pw")
        self.client.post(reverse("create"), {
            "audio": tone(), "name": "Lluvia", "status": "idea", "visibility": "public", "part_instrument": "guitar"})
        work = Project.objects.get(name="Lluvia")
        track = work.parts().get().audio
        # The work's page links each track to its page.
        self.assertContains(self.client.get(work.get_absolute_url()), 'href="%s"' % track.get_absolute_url())
        self.client.logout()
        self.client.login(username="tincho", password="pw")
        page = self.client.get(track.get_absolute_url())
        self.assertContains(page, work.get_absolute_url())  # "Track of «Lluvia»"
        self.assertContains(page, "%s?sonido=%d" % (reverse("create"), track.pk))  # usable like any public file
        self.assertNotContains(page, "Listen to it there together")

    def test_a_part_of_a_work_points_to_the_work(self):
        self.client.login(username="lucia", password="pw")
        self.client.post(reverse("create"), {
            "audio": tone(), "name": "Lluvia", "status": "idea", "visibility": "public", "part_instrument": "guitar"})
        part = Project.objects.get(name="Lluvia").parts().get().audio
        html = self.client.get(part.get_absolute_url()).content.decode()
        self.assertIn(Project.objects.get(name="Lluvia").get_absolute_url(), html)
        self.assertNotIn("?sonido=", html)
