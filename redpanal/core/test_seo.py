"""What search engines see: titles with the content first, descriptions, canonical, schema.org, the sitemap —
and that nothing private, behind a secret link or filtered ends up indexed."""
import json
import re
import shutil
import tempfile

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from audio.models import Audio
from project.models import Project
from project.test_collaboration import tone

TEMP_MEDIA = tempfile.mkdtemp()


def json_ld(html):
    return [json.loads(m) for m in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)]


@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class SeoTestCase(TestCase):

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA, ignore_errors=True)

    def setUp(self):
        self.tincho = User.objects.create_user("tincho", "t@example.com", "pw")
        self.pad = Audio.objects.create(user=self.tincho, name="Pad en La menor", audio=tone(), use_type="loop",
                                        instrument="sinthesizer", tempo=92, musical_key="Am", visibility="public")
        self.work = Project.objects.create(user=self.tincho, name="Lluvia en Pichincha", slug="lluvia",
                                           visibility="public")

    def html(self, url, **params):
        return self.client.get(url, params, HTTP_ACCEPT_LANGUAGE="es").content.decode()

    def test_a_sound_says_what_it_is_in_title_description_and_schema(self):
        html = self.html(self.pad.get_absolute_url())
        self.assertIn("<title>Pad en La menor · loop de sintetizador, 92 BPM, Am · RedPanal</title>", html)
        self.assertIn('<meta name="description" content="Loop de sintetizador, 92 BPM, Am, de tincho.', html)
        self.assertIn('<link rel="canonical" href="http://testserver%s">' % self.pad.get_absolute_url(), html)
        self.assertIn('<meta property="og:type" content="music.song">', html)
        data = json_ld(html)[0]
        self.assertEqual((data["@type"], data["name"]), ("MusicRecording", "Pad en La menor"))
        self.assertEqual(data["license"], "https://creativecommons.org/licenses/by-sa/4.0/")
        self.assertNotIn("noindex", html)

    def test_private_sounds_and_secret_link_projects_are_never_indexed(self):
        self.pad.visibility = "private"
        self.pad.save()
        self.client.login(username="tincho", password="pw")
        html = self.html(self.pad.get_absolute_url())
        self.assertIn('<meta name="robots" content="noindex, follow">', html)
        self.assertEqual(json_ld(html), [])
        self.work.visibility = "link"
        self.work.save()
        html = self.html(self.work.get_absolute_url())
        self.assertIn('<meta name="robots" content="noindex, follow">', html)
        self.assertEqual(json_ld(html), [])

    def test_a_public_project_and_a_profile_have_their_schema(self):
        self.assertEqual(json_ld(self.html(self.work.get_absolute_url()))[0]["@type"], "MusicComposition")
        profile = json_ld(self.html(self.tincho.get_absolute_url()))[0]
        self.assertEqual((profile["@type"], profile["mainEntity"]["alternateName"]), ("ProfilePage", "@tincho"))

    def test_explore_is_indexed_but_its_filters_are_not(self):
        plain = self.html(reverse("explore"))
        self.assertNotIn("noindex", plain)
        filtered = self.html(reverse("explore"), q="bajo")
        self.assertIn('<meta name="robots" content="noindex, follow">', filtered)
        self.assertIn('<link rel="canonical" href="http://testserver/explorar/">', filtered)

    def test_the_home_page_describes_the_site(self):
        html = self.html("/")
        self.assertIn("<title>RedPanal · Música libre multitrack</title>", html)
        self.assertEqual([d["@type"] for d in json_ld(html)], ["WebSite", "Organization"])

    def test_the_sitemap_lists_only_what_is_public(self):
        secret = Project.objects.create(user=self.tincho, name="Secreto", slug="secreto", visibility="link")
        hidden = Audio.objects.create(user=self.tincho, name="Boceto", audio=tone(), visibility="private")
        xml = self.client.get("/sitemap.xml").content.decode()
        self.assertIn("http://testserver%s" % self.work.get_absolute_url(), xml)
        self.assertIn("http://testserver%s" % self.pad.get_absolute_url(), xml)
        self.assertIn("http://testserver/tincho/", xml)
        self.assertNotIn(secret.get_absolute_url(), xml)
        self.assertNotIn(hidden.get_absolute_url(), xml)
        self.assertIn("Sitemap: http://testserver/sitemap.xml", self.client.get("/robots.txt").content.decode())

    def test_schema_can_not_break_out_of_its_script(self):
        self.pad.name = "</script><script>alert(1)</script>"
        self.pad.save()
        html = self.html(self.pad.get_absolute_url())
        self.assertNotIn("</script><script>alert(1)", html)
        self.assertEqual(json_ld(html)[0]["name"], "</script><script>alert(1)</script>")
