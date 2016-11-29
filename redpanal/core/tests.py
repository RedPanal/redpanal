# -*- coding: utf-8 -*-
import unittest
from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth.models import User
from django.utils.translation import ugettext_lazy as _
from django.core.urlresolvers import reverse
from django.test.simple import DjangoTestSuiteRunner
from django.conf import settings

from ..audio.models import Audio
from ..utils.test import InstanceTestMixin
from forms import tags_to_editable_string, parse_tags, TagParseError

class RedPanalTestSuiteRunner(DjangoTestSuiteRunner):
    """
    This TestSuiteRunner if fed without app labels runs all the redpanal's apps
    tests. Eg redpanal.core.collection, cyclope.apps.articles, etc.
    """

    project_name = "redpanal"

    def run_tests(self, test_labels, extra_tests=None, **kwargs):
        if not test_labels:
            test_labels = [c.split(".")[-1] for c in settings.INSTALLED_APPS if \
                           self.project_name + "." in c]
        super(RedPanalTestSuiteRunner, self).run_tests(test_labels, extra_tests,
                                                       **kwargs)


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
