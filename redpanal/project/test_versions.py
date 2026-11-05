"""Versions: go back to any of them without losing anything, and download how each one sounds."""
import shutil
import tempfile

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Project, Contribution
from .test_collaboration import tone

TEMP_MEDIA = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class VersionsTestCase(TestCase):

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA, ignore_errors=True)

    def setUp(self):
        self.lucia = User.objects.create_user("lucia", "l@example.com", "pw")
        self.tincho = User.objects.create_user("tincho", "t@example.com", "pw")
        self.client.login(username="lucia", password="pw")
        self.client.post(reverse("create"), {
            "audio": tone(), "name": "Lluvia", "status": "idea", "visibility": "public", "part_instrument": "guitar"})
        self.work = Project.objects.get(name="Lluvia")
        self.guitar = self.work.parts().get()
        self.save_version()                                   # v1: guitar
        self.client.post(reverse("project-contribute", args=[self.work.slug]), {
            "audio": tone("tone.ogg"), "instrument": "bass", "offset_ms": "0", "aligned_by_ear": "1"})
        self.bass = self.work.contributions.get(audio__instrument="bass")
        self.save_version()                                   # v2: guitar + bass

    def save_version(self):
        self.client.post(reverse("project-version-create", args=[self.work.slug]), {"message": ""})

    def restore(self, number):
        return self.client.post(reverse("project-version-restore", args=[self.work.slug, number]))

    def test_go_back_keeps_the_rest_as_alternatives(self):
        response = self.restore(1)
        self.assertRedirects(response, self.work.get_absolute_url(), fetch_redirect_response=False)
        self.assertEqual(list(self.work.parts()), [self.guitar])
        self.bass.refresh_from_db()
        self.assertEqual(self.bass.status, Contribution.ALTERNATIVE)
        self.restore(2)
        self.assertEqual(set(self.work.parts()), {self.guitar, self.bass})

    def test_withdrawn_parts_are_not_brought_back(self):
        self.restore(1)
        self.bass.set_status(Contribution.WITHDRAWN)
        self.restore(2)
        self.assertEqual(list(self.work.parts()), [self.guitar])

    def test_only_the_owner_goes_back(self):
        self.client.logout()
        self.client.login(username="tincho", password="pw")
        self.assertEqual(self.restore(1).status_code, 403)
        self.assertEqual(self.work.parts().count(), 2)

    def test_version_page_offers_going_back_only_when_it_changes_something(self):
        latest = self.client.get(reverse("project-version", args=[self.work.slug, 2]))
        self.assertTrue(latest.context["is_current"])
        self.assertNotContains(latest, reverse("project-version-restore", args=[self.work.slug, 2]))
        older = self.client.get(reverse("project-version", args=[self.work.slug, 1]))
        self.assertContains(older, reverse("project-version-restore", args=[self.work.slug, 1]))
        self.assertEqual(older.context["next"].number, 2)

    def test_download_the_mix(self):
        response = self.client.get(reverse("project-version-mix", args=[self.work.slug, 2]))
        self.assertEqual(response.status_code, 200)
        self.assertIn("lluvia-v2.mp3", response["Content-Disposition"])
        self.assertGreater(len(b"".join(response.streaming_content)), 0)

    def test_no_mix_when_downloads_are_off(self):
        self.work.allow_downloads = False
        self.work.save()
        self.client.logout()
        self.client.login(username="tincho", password="pw")
        self.assertIn(self.client.get(reverse("project-version-mix", args=[self.work.slug, 2])).status_code,
                      (403, 404))
        self.assertNotContains(self.client.get(reverse("project-version", args=[self.work.slug, 2])),
                               reverse("project-version-mix", args=[self.work.slug, 2]))
