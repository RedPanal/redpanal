"""Spanish, English and Portuguese: the browser's by default, chosen at the bottom of any page or in the settings."""
from django.conf import settings
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from users.models import UserProfile


class LanguageTestCase(TestCase):

    def page(self, **headers):
        return self.client.get(reverse("explore"), **headers).content.decode()

    def test_the_browsers_language_by_default(self):
        self.assertIn('lang="pt"', self.page(HTTP_ACCEPT_LANGUAGE="pt-BR,pt;q=0.9"))
        self.assertIn("Buscar projetos, sons ou pessoas", self.page(HTTP_ACCEPT_LANGUAGE="pt-BR,pt;q=0.9"))
        self.assertIn("Search projects, sounds or people", self.page(HTTP_ACCEPT_LANGUAGE="en-US,en;q=0.9"))
        self.assertIn("Buscar proyectos, sonidos o personas", self.page(HTTP_ACCEPT_LANGUAGE="es-AR,es;q=0.9"))

    def test_every_page_offers_the_three_languages(self):
        html = self.page()
        for code, name in (("es", "Español"), ("en", "English"), ("pt", "Português")):
            self.assertIn('value="%s" lang="%s"' % (code, code), html)
            self.assertIn(name, html)

    def test_choosing_at_the_bottom_of_the_page_sticks_and_goes_back(self):
        response = self.client.post(reverse("set-language"), {"language": "en", "next": "/explorar/?q=bajo"})
        self.assertEqual(response["Location"], "/explorar/?q=bajo")
        self.assertEqual(response.cookies[settings.LANGUAGE_COOKIE_NAME].value, "en")
        self.assertIn('lang="en"', self.page(HTTP_ACCEPT_LANGUAGE="pt"))

    def test_it_never_sends_you_to_another_site(self):
        response = self.client.post(reverse("set-language"), {"language": "pt", "next": "https://example.com/"})
        self.assertEqual(response["Location"], "/")

    def test_with_an_account_the_choice_follows_you_to_every_device(self):
        lucia = User.objects.create_user("lucia", "l@example.com", "pw")
        self.client.login(username="lucia", password="pw")
        self.client.post(reverse("user-profile"), {"realname": "Lucía", "language": "pt"})
        self.assertEqual(UserProfile.objects.get(user=lucia).language, "pt")
        other_device = self.client_class()
        other_device.login(username="lucia", password="pw")
        response = other_device.get(reverse("explore"), HTTP_ACCEPT_LANGUAGE="es")
        self.assertIn('lang="pt"', response.content.decode())
        self.assertEqual(response.cookies[settings.LANGUAGE_COOKIE_NAME].value, "pt")

    def test_back_to_the_browsers_language(self):
        lucia = User.objects.create_user("lucia", "l@example.com", "pw")
        self.client.login(username="lucia", password="pw")
        self.client.post(reverse("set-language"), {"language": "en", "next": "/"})
        self.client.post(reverse("user-profile"), {"realname": "Lucía", "language": ""})
        self.assertEqual(UserProfile.objects.get(user=lucia).language, "")
        self.assertIn('lang="es"', self.page(HTTP_ACCEPT_LANGUAGE="es"))
