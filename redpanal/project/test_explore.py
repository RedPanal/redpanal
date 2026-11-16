"""Explore: everything at once in sections, one search box, and an advanced search for the rest."""
import shutil
import tempfile

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from audio.models import Audio
from social.models import Message
from .models import Project, PartRequest
from .test_collaboration import tone

TEMP_MEDIA = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class ExploreTestCase(TestCase):

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA, ignore_errors=True)

    def setUp(self):
        self.lucia = User.objects.create_user("lucia", "l@example.com", "pw")
        self.tincho = User.objects.create_user("tincho", "t@example.com", "pw")
        self.tincho.userprofile.instruments = ["bass"]
        self.tincho.userprofile.realname = "Tincho Acosta"
        self.tincho.userprofile.save()
        self.idea = Project.objects.create(user=self.lucia, name="Zamba del puerto", slug="zamba", status="idea",
                                           visibility="public")
        self.done = Project.objects.create(user=self.lucia, name="Chacarera terminada", slug="chacarera",
                                           status="finished", visibility="public")
        self.secret = Project.objects.create(user=self.lucia, name="Zamba secreta", slug="secreta", visibility="private")
        PartRequest.objects.create(project=self.idea, instrument="bass")
        Audio.objects.create(user=self.tincho, name="Zamba en loop", audio=tone(), use_type="loop")
        Message.objects.create(user=self.tincho, msg="qué linda zamba", content_object=self.idea)
        Message.objects.create(user=self.tincho, msg="zamba privada", content_object=self.secret)

    def get(self, **params):
        return self.client.get(reverse("explore"), params)

    def items(self, response, section):
        return list(response.context["sections"][section]["items"])

    def test_everything_at_once_in_sections(self):
        response = self.get()
        self.assertEqual(response.context["tab"], "")
        self.assertEqual(self.items(response, "pedidos")[0].project, self.idea)
        self.assertIn(self.idea, self.items(response, "obras"))
        self.assertEqual([m.msg for m in self.items(response, "comentarios")], ["qué linda zamba"])
        self.assertEqual(len(self.items(response, "sonidos")), 1)
        self.assertIn(self.tincho, self.items(response, "personas"))
        self.assertNotContains(response, "Zamba secreta")
        self.assertNotContains(response, "zamba privada")

    def test_instrument_lives_in_the_advanced_search(self):
        html = self.get().content.decode()
        advanced = html[html.find('id="advanced"'):]
        self.assertIn('name="instrumento"', advanced)
        self.assertEqual(html.count('name="instrumento"'), 1)

    def test_asking_filter_and_no_status_filter(self):
        # Idea / in progress / finished isn't shown nor filtered: almost everything is in progress.
        self.assertNotIn('name="estado"', self.client.get(reverse("explore")).content.decode())
        self.assertEqual(self.items(self.get(ver="obras", pide="1"), "obras"), [self.idea])

    def test_one_search_counts_every_section(self):
        response = self.get(q="zamba")
        sections = response.context["sections"]
        self.assertEqual(sections["obras"]["count"], 1)
        self.assertEqual(sections["sonidos"]["count"], 1)
        self.assertEqual(sections["pedidos"]["count"], 1)
        self.assertEqual(sections["comentarios"]["count"], 1)

    def test_people_by_name_and_instrument(self):
        self.assertEqual(self.items(self.get(ver="personas", q="tincho"), "personas"), [self.tincho])
        self.assertEqual(self.items(self.get(ver="personas", instrumento="bass"), "personas"), [self.tincho])
        self.assertEqual(self.items(self.get(ver="personas", instrumento="drums"), "personas"), [])

    def test_header_search_and_old_search_page_land_in_explore(self):
        response = self.client.get("/search/?q=zamba")
        self.assertRedirects(response, reverse("explore") + "?q=zamba", fetch_redirect_response=False)
        self.assertContains(self.client.get("/"), 'action="%s"' % reverse("explore"))

    def test_see_more_keeps_the_search(self):
        for i in range(8):
            Project.objects.create(user=self.lucia, name="Zamba %d" % i, slug="zamba-%d" % i, visibility="public")
        html = self.get(q="zamba").content.decode()
        self.assertIn("?ver=obras&amp;q=zamba", html)
