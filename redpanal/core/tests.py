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
        self.assertEqual(302, response.status_code)

        response = self.client.get("/", follow=True)
        self.assertEqual(200, response.status_code)

    def test_index_view(self):
        self.login()

        response = self.client.get("/", follow=True)
        self.assertEqual(200, response.status_code)


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
