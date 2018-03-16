from django.test import TestCase
from django.contrib.auth.models import User
from django.template import Template, Context

from taggit.models import Tag
from models import Message
from project.models import Project


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
        url = User.objects.get(username="owner").get_absolute_url()
        self.assertIn('<a href="%s">@owner</a>' % url, m.as_html())

    def test_mentioned_but_inexistant_user(self):
        msg = "@InEX here this #radioGaGa"
        m = Message.objects.create(user=self.user, msg=msg)
        self.assertFalse(m.mentioned_users.all())

    def test_tags(self):
        msg = "@owner here this #radioGaGa #Meith we are"
        m = Message.objects.create(user=self.user, msg=msg)
        self.assertEqual(map(lambda t: t.name, m.tags.all()), ["radioGaGa", "Meith"])

    def test_tag_html(self):
        msg = "@owner here this #radioGaGa #Meith we are"
        m = Message.objects.create(user=self.user, msg=msg)
        tag = Tag.objects.get(name="radioGaGa")
        self.assertIn('<a href="%s">#radioGaGa</a>' % tag.get_absolute_url(), m.as_html())

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
        t = Template('{% load social_tags %}{% message_form_for usr %}')
        form_html = t.render(Context({'usr': self.user}))

    def test_message_form_for_project(self):
        project = Project.objects.create(name="Project Zero", user=self.user,
                                         description="The proj 0")
        t = Template('{% load social_tags %}{% message_form_for project %}')
        form_html = t.render(Context({'project': project}))

    def test_strip_unwanted_tags(self):
        msg = "hey <script>$('body').remove()</script>"
        self.assertNotIn("<script>", Message.to_html(msg))

    def test_replace_project_links(self):
        from django.contrib.sites.models import Site
        project = Project.objects.create(name="Project Zero", user=self.user,
                                         description="The proj 0")

        domain = Site.objects.get_current().domain
        link = "http://%s%s" % (domain, project.get_absolute_url())
        msg = "Este es el link %s a mi proyecto" % link
        self.assertIn("Project Zero", Message.to_html(msg))

    def test_replace_urls(self):
        msg = "heyyy http://asd.com/wee/"
        self.assertIn('<a href="http://asd.com/wee/"', Message.to_html(msg))
