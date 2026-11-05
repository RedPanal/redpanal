"""Visit statistics: off unless configured; when on, only public pages are counted and nobody is identified."""
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from project.models import Project

UMAMI = {"UMAMI_SCRIPT_URL": "https://stats.example.org/script.js", "UMAMI_WEBSITE_ID": "abc-123",
         "UMAMI_DOMAINS": "redpanal.org"}


class AnalyticsOffTestCase(TestCase):

    def test_nothing_is_loaded_without_configuration(self):
        html = self.client.get(reverse("explore")).content.decode()
        self.assertNotIn("data-website-id", html)
        self.assertNotIn('id="rp-analytics"', html)


@override_settings(**UMAMI)
class AnalyticsTestCase(TestCase):

    def setUp(self):
        self.lucia = User.objects.create_user("lucia", "l@example.com", "pw")
        self.work = Project.objects.create(user=self.lucia, name="Murga", slug="murga", visibility="public")

    def flag(self, url, **params):
        html = self.client.get(url, params).content.decode()
        start = html.index('id="rp-analytics"')
        return html[start:html.index(">", start)]

    def test_the_tracker_counts_nothing_by_itself_and_respects_do_not_track(self):
        html = self.client.get(reverse("explore")).content.decode()
        self.assertIn('src="https://stats.example.org/script.js" data-website-id="abc-123"', html)
        for attr in ('data-auto-track="false"', 'data-do-not-track="true"', 'data-exclude-search="true"',
                     'data-domains="redpanal.org"', "rp-analytics.js"):
            self.assertIn(attr, html)

    def test_public_pages_are_counted_private_ones_are_not(self):
        self.assertIn('data-track="1"', self.flag(self.work.get_absolute_url()))
        self.assertIn('data-track="1"', self.flag(reverse("explore")))
        self.assertIn('data-track="0"', self.flag(reverse("explore"), q="bajo"))  # what someone searched
        self.work.visibility = "link"
        self.work.save()
        self.client.login(username="lucia", password="pw")
        self.assertIn('data-track="0"', self.flag(self.work.get_absolute_url()))  # behind a secret link
        self.assertIn('data-track="0"', self.flag(reverse("my-stuff")))
        self.assertIn('data-track="0"', self.flag(reverse("user-profile")))

    def test_server_events_go_out_once_on_the_next_page_without_saying_who(self):
        User.objects.create_user("tincho", "t@example.com", "pw")
        self.client.login(username="lucia", password="pw")
        self.client.post(reverse("person-follow", args=["tincho"]))
        first = self.flag(reverse("explore"))
        self.assertIn('data-events="follow"', first)
        self.assertNotIn("lucia", first)
        self.assertIn('data-events=""', self.flag(reverse("explore")))
