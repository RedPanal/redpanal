"""The four palettes: "Moderna" by default, the others chosen in the settings. Only colors change."""
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from users.models import UserProfile


class PaletteTestCase(TestCase):

    def setUp(self):
        self.lucia = User.objects.create_user("lucia", "l@example.com", "pw")

    def html(self):
        return self.client.get(reverse("explore")).content.decode()

    def test_moderna_by_default_also_without_an_account(self):
        html = self.html()
        self.assertIn('data-palette="moderna"', html)
        self.assertNotIn('data-bs-theme="dark"', html)
        self.assertIn("rp-palettes.css", html)

    def test_choosing_another_palette_in_the_settings(self):
        self.client.login(username="lucia", password="pw")
        settings_page = self.client.get(reverse("user-profile")).content.decode()
        for key in ("moderna", "neon", "calida", "lavanda"):
            self.assertIn('name="palette" value="%s"' % key, settings_page)
        self.client.post(reverse("user-profile"), {"realname": "Lucía", "palette": "calida"})
        self.assertEqual(UserProfile.objects.get(user=self.lucia).palette, "calida")
        self.assertIn('data-palette="calida"', self.html())

    def test_the_dark_palette_turns_bootstrap_dark_too(self):
        self.client.login(username="lucia", password="pw")
        self.client.post(reverse("user-profile"), {"realname": "Lucía", "palette": "neon"})
        html = self.html()
        self.assertIn('data-palette="neon" data-bs-theme="dark"', html)
        self.assertIn('<meta name="theme-color" content="#12181e">', html)

    def test_an_unknown_palette_changes_nothing(self):
        self.client.login(username="lucia", password="pw")
        self.client.post(reverse("user-profile"), {"realname": "Lucía", "palette": "rosa-chicle"})
        self.assertEqual(UserProfile.objects.get(user=self.lucia).palette, "moderna")
