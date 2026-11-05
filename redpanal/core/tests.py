# -*- coding: utf-8 -*-
import unittest
from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _
from django.urls import reverse
from django.conf import settings

from audio.models import Audio
from redpanal.utils.test import InstanceTestMixin
from .forms import tags_to_editable_string, parse_tags, TagParseError


class CoreTestCase(TestCase):

    def setUp(self):
        self.user = User.objects.create_user("john", "lenon@beatles.com", "yoko")

    def login(self):
        self.client.login(username="john", password="yoko")

    def test_anonymous_index_view(self):
        response = self.client.get("/")
        self.assertEqual(200, response.status_code)

    def test_index_view(self):
        self.login()

        response = self.client.get("/", follow=True)
        self.assertEqual(200, response.status_code)


class InstallableAppTest(TestCase):

    def test_service_worker_served_from_the_root(self):
        response = self.client.get("/sw.js")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"].split(";")[0], "application/javascript")
        self.assertContains(response, reverse("offline"))

    def test_offline_page_and_manifest(self):
        self.assertEqual(self.client.get(reverse("offline")).status_code, 200)
        from django.contrib.staticfiles import finders
        self.assertIsNotNone(finders.find("manifest.webmanifest"))
        self.assertIsNotNone(finders.find("img/icon-512.png"))
        self.assertContains(self.client.get("/"), "manifest.webmanifest")

    def test_upload_queue_only_for_people_signed_in(self):
        self.assertNotContains(self.client.get("/"), "upload-queue.js")
        User.objects.create_user("q", "", "pw")
        self.client.login(username="q", password="pw")
        self.assertContains(self.client.get("/"), "upload-queue.js")


class NavigationTest(TestCase):
    """The header (desktop) and the bottom bar (phones) offer the same places, in the same order."""

    def nav_links(self, response):
        import re
        html = response.content.decode()
        navs = re.findall(r'<nav class="rp-nav [^"]*"[^>]*>(.*?)</nav>', html, re.S)
        self.assertEqual(len(navs), 2)
        return [re.findall(r'href="([^"]+)"', nav) for nav in navs]

    def test_same_items_for_visitors(self):
        top, bottom = self.nav_links(self.client.get("/"))
        self.assertEqual(top, bottom)
        self.assertIn(reverse("explore"), top)

    def test_same_items_and_profile_at_hand_when_signed_in(self):
        user = User.objects.create_user("nav", "", "pw")
        self.client.login(username="nav", password="pw")
        top, bottom = self.nav_links(self.client.get(reverse("explore")))
        self.assertEqual(top, bottom)
        self.assertEqual(top, [reverse("index"), reverse("explore"), reverse("create"),
                               reverse("my-stuff"), user.get_absolute_url()])


class StudioTest(TestCase):
    """Mis cosas is now Estudio: same place, new name and address; the old address still works."""

    def test_studio_address_and_label(self):
        User.objects.create_user("st", "", "pw")
        self.client.login(username="st", password="pw")
        self.assertEqual(reverse("my-stuff"), "/estudio/")
        self.assertRedirects(self.client.get("/mis-cosas/"), "/estudio/", status_code=301)
        html = self.client.get("/").content.decode()
        self.assertIn('href="/estudio/"', html)
        self.assertIn("fa-sliders-h", html)
        self.assertIn("Estudio", html)


class TagsTest(unittest.TestCase):
    def test_tags_to_editable_string_some_tags(self):
        s = tags_to_editable_string(['foo', 'bar'])
        self.assertEqual(s, u'#foo #bar')

    def test_tags_to_editable_string_empty(self):
        s = tags_to_editable_string([])
        self.assertEqual(s, u'')

    def test_parse_tags_some_tags(self):
        self.assertEqual(parse_tags('#foo #bar'), ['foo', 'bar'])

    def test_parse_tags_empty(self):
        self.assertEqual(parse_tags(''), [])

    def test_parse_tag_without_numeral(self):
        self.assertRaises(TagParseError, parse_tags, '#foo bar')

    def test_parse_tags_minimum_length(self):
        self.assertEqual(parse_tags('# #foo #'), ['foo'])
