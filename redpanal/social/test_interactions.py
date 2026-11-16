"""Posts from the profile, and replying, favoriting and amplifying from Comunidad."""
import shutil
import tempfile

from actstream.models import Action
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from audio.models import Audio
from project.models import Project
from project.test_collaboration import tone
from social.models import Message, Reaction

TEMP_MEDIA = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class InteractionsTestCase(TestCase):

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA, ignore_errors=True)

    def setUp(self):
        self.lucia = User.objects.create_user("lucia", "l@example.com", "pw")
        self.tincho = User.objects.create_user("tincho", "t@example.com", "pw")
        self.carla = User.objects.create_user("carla", "c@example.com", "pw")
        self.work = Project.objects.create(user=self.lucia, name="Lluvia", slug="lluvia", visibility="public")
        self.secret = Project.objects.create(user=self.lucia, name="Secreta", slug="secreta", visibility="private")
        self.sound = Audio.objects.create(user=self.lucia, name="Pad", audio=tone())

    def login(self, who):
        self.client.logout()
        self.client.login(username=who, password="pw")

    def follow(self, who, whom):
        self.login(who)
        self.client.post(reverse("person-follow", args=[whom]))

    # -- posts ---------------------------------------------------------------------

    def test_post_from_any_page_reaches_followers(self):
        self.login("lucia")
        # "+ Crear" opens, on every page, a panel with writing on top and uploading or recording below.
        for url in (reverse("index"), reverse("explore"), self.work.get_absolute_url()):
            html = self.client.get(url).content.decode()
            self.assertIn("data-create-open", html)
            sheet = html[html.find('id="post-dialog"'):html.find("</dialog>", html.find('id="post-dialog"'))]
            self.assertLess(sheet.find('name="msg"'), sheet.find('href="%s"' % reverse("create")))
            self.assertIn("%s?grabar=1" % reverse("create"), sheet)
            self.assertNotIn("rp-fab", html)  # no floating pen
        self.assertNotContains(self.client.get(self.lucia.get_absolute_url()), 'class="rp-composer mb-4"')
        response = self.client.post(reverse("message-create"), {"msg": "ensayando una zamba nueva"},
                                    HTTP_REFERER=reverse("explore"), follow=True)
        self.assertContains(response, "alert-success")
        post = Message.objects.get(msg="ensayando una zamba nueva")
        self.assertIsNone(post.content_object)
        self.assertContains(self.client.get(self.lucia.get_absolute_url()), "ensayando una zamba nueva")
        self.follow("tincho", "lucia")
        feed = self.client.get(reverse("index")).context["feed"]
        self.assertIn(("post", post.pk), [(i["kind"], i["object"].pk) for i in feed])

    def test_posting_needs_an_account(self):
        self.assertNotContains(self.client.get(reverse("explore")), 'id="post-dialog"')
        response = self.client.post(reverse("message-create"), {"msg": "anónimo"})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Message.objects.filter(msg="anónimo").exists())

    # -- reactions -------------------------------------------------------------------

    def test_favorite_toggles_notifies_and_lists_in_my_stuff(self):
        self.login("tincho")
        url = reverse("react", args=["favorite", "proyecto", self.work.pk])
        self.client.post(url)
        self.assertTrue(Reaction.objects.filter(user=self.tincho, kind="favorite", object_id=self.work.pk).exists())
        self.assertEqual(list(self.lucia.notifications.values_list("kind", flat=True)), ["favorited"])
        self.assertIn(self.work, self.client.get(reverse("my-favorites")).context["works"])
        self.client.post(url)
        self.assertFalse(Reaction.objects.filter(user=self.tincho, kind="favorite").exists())

    def test_amplify_republishes_for_followers_and_can_be_undone(self):
        self.follow("carla", "tincho")
        self.login("tincho")
        url = reverse("react", args=["amplify", "sonido", self.sound.pk])
        self.client.post(url)
        self.assertEqual(list(self.lucia.notifications.values_list("kind", flat=True)), ["amplified"])
        self.login("carla")
        feed = self.client.get(reverse("index")).context["feed"]
        self.assertEqual([(i["kind"], i["amplified"]) for i in feed], [("sound", True)])
        self.login("tincho")
        self.client.post(url)
        self.assertFalse(Action.objects.filter(verb="amplified").exists())

    def test_what_is_not_public_can_be_amplified_for_followers_who_can_see_it(self):
        from project.models import Membership
        Membership.objects.create(project=self.secret, user=self.tincho)
        Membership.objects.create(project=self.secret, user=self.carla)
        self.follow("carla", "tincho")
        stranger = User.objects.create_user("otro", "o@example.com", "pw")
        self.follow("otro", "tincho")
        self.login("tincho")
        self.client.post(reverse("react", args=["amplify", "proyecto", self.secret.pk]))
        self.assertFalse(Action.objects.get(verb="amplified").public)  # never in the open feeds
        self.login("carla")
        self.assertIn(self.secret, [i["work"] for i in self.client.get(reverse("index")).context["feed"]])
        self.login("otro")
        self.assertNotIn(self.secret, [i["work"] for i in self.client.get(reverse("index")).context["feed"]])

    def test_private_things_cannot_be_amplified_or_seen(self):
        self.login("tincho")
        self.assertEqual(self.client.post(reverse("react", args=["amplify", "proyecto", self.secret.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("react", args=["favorite", "proyecto", self.secret.pk])).status_code, 404)
        self.assertFalse(Reaction.objects.exists())

    def test_reply_from_the_feed(self):
        comment = Message.objects.create(user=self.lucia, msg="¿les gusta?", content_object=self.work)
        self.login("tincho")
        self.client.post(reverse("reply", args=["comentario", comment.pk]), {"msg": "¡mucho!"})
        reply = Message.objects.get(msg="¡mucho!")
        self.assertEqual((reply.parent, reply.content_object), (comment, self.work))
        # Replying to a reply hangs from the same comment (one level).
        self.login("carla")
        self.client.post(reverse("reply", args=["comentario", reply.pk]), {"msg": "a mí también"})
        self.assertEqual(Message.objects.get(msg="a mí también").parent, comment)
        self.assertIn("replied", list(self.tincho.notifications.values_list("kind", flat=True)))

    def test_reply_to_a_project_is_a_comment_on_it(self):
        self.login("tincho")
        self.client.post(reverse("reply", args=["proyecto", self.work.pk]), {"msg": "qué lindo"})
        self.assertEqual(Message.objects.get(msg="qué lindo").content_object, self.work)
        self.assertEqual(self.client.post(reverse("reply", args=["proyecto", self.secret.pk]), {"msg": "x"}).status_code,
                         404)

    def test_feed_items_show_the_interaction_bar(self):
        Audio.objects.create(user=self.lucia, name="Shaker", audio=tone())
        self.follow("tincho", "lucia")
        html = self.client.get(reverse("index")).content.decode()
        self.assertIn("rp-interactions", html)
        self.assertIn(reverse("react", args=["favorite", "sonido", Audio.objects.get(name="Shaker").pk]), html)
