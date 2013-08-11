import unittest
from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth.models import User
from django.utils.translation import ugettext_lazy as _
from django.core.urlresolvers import reverse

from models import Project
from ..audio.models import Audio
from ..utils.test import InstanceTestMixin
from forms import tags_to_editable_string, parse_tags, TagParseError

class CoreTestCase(TestCase):

    def test_index_view(self):
        response = self.client.get("/")
        self.assertEqual(200, response.status_code)


class ProjectTestCase(TestCase, InstanceTestMixin):
    def setUp(self):
        self.user = User.objects.create_user("owner", "e@a.com", "password")

    def login(self):
        self.client.login(username="owner", password="password")

    def create_instance(self):
        instance = Project.objects.create(name="THE project", user=self.user,
                                          description="This is THE project")
        return instance

    def get_model_name(self):
        return 'project'

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
