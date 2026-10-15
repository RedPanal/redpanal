"""Account pages: look like the rest of the site, and lead where people want to go."""
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse


class AccountTestCase(TestCase):

    def setUp(self):
        self.lucia = User.objects.create_user("lucia", "l@example.com", "pw")

    def test_sign_in_goes_home(self):
        response = self.client.post(reverse("account_login"), {"login": "lucia", "password": "pw"})
        self.assertRedirects(response, "/", fetch_redirect_response=False)

    def test_login_page_uses_the_site_layout(self):
        html = self.client.get(reverse("account_login")).content.decode()
        self.assertIn('class="rp-narrow rp-auth"', html)
        self.assertIn('class="rp-nav rp-tabbar', html)
        self.assertNotIn("Username:", html)

    def test_edit_profile_puts_instruments_right_after_the_name(self):
        self.client.login(username="lucia", password="pw")
        html = self.client.get(reverse("user-profile")).content.decode()
        self.assertLess(html.find('name="realname"'), html.find('name="instruments"'))
        self.assertLess(html.find('name="instruments"'), html.find('name="about"'))
        response = self.client.post(reverse("user-profile"), {"realname": "Lucía", "instruments": ["guitar", "voice"]})
        self.assertRedirects(response, self.lucia.get_absolute_url(), fetch_redirect_response=False)
        self.lucia.userprofile.refresh_from_db()
        self.assertEqual(self.lucia.userprofile.instruments, ["guitar", "voice"])

    def test_old_activity_pages_go_home(self):
        for url in ("/actividad/", "/live/", "/landing-page/"):
            self.assertRedirects(self.client.get(url), "/", fetch_redirect_response=False)

    def test_menu_has_no_activity_and_logs_out_directly(self):
        self.client.login(username="lucia", password="pw")
        html = self.client.get("/").content.decode()
        self.assertNotIn(reverse("activity-feed"), html)
        self.assertIn('<form method="post" action="%s">' % reverse("account_logout"), html)
