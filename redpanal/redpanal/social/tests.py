from django.test import TestCase
from django.contrib.auth.models import User
from django.template import Template, Context

from models import Message

class MessageTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("owner", "e@a.com", "password")

    def test_basic_comment_creation(self):
        msg = "this is the message"
        m = Message.objects.create(user=self.user, msg=msg)
        self.assertEqual(m.msg, msg)

    def test_mentioned_users(self):
        msg = "@owner here this #radioGaGa"
        m = Message.objects.create(user=self.user, msg=msg)
        self.assertEqual(list(m.mentioned_users.all()), [self.user])

    def test_mentioned_but_inexistant_user(self):
        msg = "@InEX here this #radioGaGa"
        m = Message.objects.create(user=self.user, msg=msg)
        self.assertFalse(m.mentioned_users.all())

    def test_tags(self):
        msg = "@owner here this #radioGaGa #Meith we are"
        m = Message.objects.create(user=self.user, msg=msg)
        self.assertEqual(map(lambda t: t.name, m.tags.all()), ["radioGaGa", "Meith"])

    def test_extract_tags_with_ended_symbols(self):
        msg = "#foo #bar, #baz, #f1;#f2 #f3."
        tags = Message.extract_hashtags(msg)
        self.assertEqual(tags, ["foo", "bar", "baz", "f1", "f2", "f3"])

    def test_to_html(self):
        msg = "@owner here this #radioGaGa"
        m = Message.objects.create(user=self.user, msg=msg)
        html = Message.to_html(msg)
        self.assertEqual(m.as_html(), html)

    def test_meessage_form_for(self):
        t = Template('{% load social %}{% message_form_for usr %}')
        c = Context({'usr': self.user})
        form_html = t.render(c)


