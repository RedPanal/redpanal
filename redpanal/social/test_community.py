"""Comunidad, notifications and following."""
import io
import shutil
import tempfile

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from audio.models import Audio
from project.models import Project, Contribution, WorkGroup, GroupMember
from project.test_collaboration import tone
from social.models import Message, Notification

TEMP_MEDIA = tempfile.mkdtemp()


def picture(name="tapa.png"):
    from PIL import Image
    out = io.BytesIO()
    Image.new("RGB", (40, 40), (200, 80, 40)).save(out, format="PNG")
    return SimpleUploadedFile(name, out.getvalue(), content_type="image/png")


@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class CommunityTestCase(TestCase):

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA, ignore_errors=True)

    def setUp(self):
        self.lucia = User.objects.create_user("lucia", "l@example.com", "pw")
        self.tincho = User.objects.create_user("tincho", "t@example.com", "pw")
        self.client.login(username="lucia", password="pw")
        self.client.post(reverse("create"), {
            "audio": tone(), "name": "Lluvia", "status": "idea", "visibility": "public",
            "missing": ["bass"], "part_instrument": "guitar", "image": picture()})
        self.work = Project.objects.get(name="Lluvia")
        self.client.logout()

    def login(self, who):
        self.client.logout()
        self.client.login(username=who, password="pw")

    def contribute(self):
        self.login("tincho")
        self.client.post(reverse("project-contribute", args=[self.work.slug]), {
            "audio": tone("tone.ogg"), "instrument": "bass", "offset_ms": "0", "accept_terms": "1"})
        return self.work.contributions.get(contributor=self.tincho)

    # -- notifications -------------------------------------------------------------

    def test_a_contribution_notifies_the_owner_with_the_bell(self):
        self.contribute()
        self.login("lucia")
        home = self.client.get(reverse("index"))
        self.assertEqual(home.context["unread_notifications"], 1)
        self.assertContains(home, "rp-bell-count")
        page = self.client.get(reverse("notifications"))
        self.assertContains(page, "Lluvia")
        self.assertFalse(self.lucia.notifications.filter(read_at__isnull=True).exists())

    def test_the_decision_notifies_the_contributor(self):
        contribution = self.contribute()
        self.login("lucia")
        self.client.post(reverse("contribution-status", args=[self.work.slug, contribution.pk]), {"status": "included"})
        self.assertEqual(list(self.tincho.notifications.values_list("kind", flat=True)), ["included"])

    def test_a_comment_notifies_the_owner_and_mentions(self):
        third = User.objects.create_user("carla", "c@example.com", "pw")
        Message.objects.create(user=self.tincho, msg="qué lindo, mirá @carla", content_object=self.work)
        self.assertEqual(list(self.lucia.notifications.values_list("kind", flat=True)), ["commented"])
        self.assertEqual(list(third.notifications.values_list("kind", flat=True)), ["mentioned"])

    def test_mentions_link_and_notify_also_next_to_punctuation(self):
        carla = User.objects.create_user("carla", "c@example.com", "pw")
        m = Message.objects.create(user=self.tincho, msg="gracias @carla, y (@lucia).", content_object=self.work)
        self.assertIn('href="%s"' % carla.get_absolute_url(), m.as_html())
        self.assertIn('href="%s"' % self.lucia.get_absolute_url(), m.as_html())
        self.assertEqual(list(carla.notifications.values_list("kind", flat=True)), ["mentioned"])

    def test_a_mention_in_a_post_points_to_the_post(self):
        post = Message.objects.create(user=self.tincho, msg="ensayando con @lucia")
        n = self.lucia.notifications.get()
        self.assertEqual(n.kind, "mentioned")
        self.assertEqual(n.url, self.tincho.get_absolute_url() + "#c%d" % post.pk)
        self.assertEqual(n.target_name, "ensayando con @lucia")

    def test_no_mention_notice_about_a_project_you_cannot_hear(self):
        self.work.set_visibility("private")
        Message.objects.create(user=self.lucia, msg="mirá esto @tincho", content_object=self.work)
        self.assertFalse(self.tincho.notifications.exists())

    def test_a_comment_on_a_sound_notifies_its_author(self):
        sound = Audio.objects.create(user=self.lucia, name="Pad", audio=tone())
        comment = Message.objects.create(user=self.tincho, msg="qué lindo pad", content_object=sound)
        n = self.lucia.notifications.get()
        self.assertEqual((n.kind, n.target_name, n.url),
                         ("commented", "Pad", sound.get_absolute_url() + "#c%d" % comment.pk))  # lands on the comment

    def test_turned_off_kinds_are_not_created(self):
        self.login("lucia")
        self.client.post(reverse("user-profile"), {"realname": "Lucía", "notify": ["decided", "followed"]})
        self.lucia.userprofile.refresh_from_db()
        self.assertIn("contributed", self.lucia.userprofile.notify_off)
        self.contribute()
        self.assertFalse(Notification.objects.filter(recipient=self.lucia).exists())

    # -- following and Comunidad -------------------------------------------------------

    def test_follow_notifies_and_feeds_comunidad(self):
        self.login("tincho")
        self.client.post(reverse("person-follow", args=["lucia"]))
        self.assertEqual(list(self.lucia.notifications.values_list("kind", flat=True)), ["followed"])
        Audio.objects.create(user=self.lucia, name="Pad de Lucía", audio=tone())
        Message.objects.create(user=self.lucia, msg="gracias por escuchar", content_object=self.work)
        feed = self.client.get(reverse("index")).context["feed"]
        self.assertEqual({item["kind"] for item in feed}, {"project", "sound", "comment"})
        # Following again stops following.
        self.client.post(reverse("person-follow", args=["lucia"]))
        self.assertEqual(self.client.get(reverse("index")).context["feed"], [])

    def test_comunidad_leaves_out_my_own_things_and_private_projects(self):
        self.login("lucia")
        self.assertEqual(self.client.get(reverse("index")).context["feed"], [])
        self.login("tincho")
        self.client.post(reverse("person-follow", args=["lucia"]))
        self.work.set_visibility("private")
        kinds = [item["kind"] for item in self.client.get(reverse("index")).context["feed"]]
        self.assertNotIn("project", kinds)

    def test_comunidad_continues_with_content_linked_to_what_you_play_and_tag(self):
        self.tincho.userprofile.instruments = ["bass"]
        self.tincho.userprofile.save()
        self.work.tags.add("zamba")
        mine = Audio.objects.create(user=self.tincho, name="Mío", audio=tone())
        mine.tags.add("zamba")
        self.login("tincho")
        response = self.client.get(reverse("index"))
        related = [i for i in response.context["feed"] if i.get("reason")]
        self.assertEqual([i["work"] for i in related], [self.work])  # asks for bass, and shares #zamba
        self.assertNotContains(response, "From the people you follow")
        self.assertNotIn("suggestions", response.context)

    def test_the_card_does_not_repeat_who_is_named_above(self):
        self.login("tincho")
        self.client.post(reverse("person-follow", args=["lucia"]))
        html = self.client.get(reverse("index")).content.decode()
        card = html[html.find('class="rp-card rp-work-card"'):]
        card = card[:card.find("</article>")]
        self.assertNotIn(self.lucia.get_absolute_url(), card)

    # -- images --------------------------------------------------------------------

    def test_projects_and_sounds_have_images(self):
        self.assertTrue(self.work.image)
        self.assertIn("rp-cover", self.client.get(self.work.get_absolute_url()).content.decode())
        self.login("tincho")
        self.client.post(reverse("create-sound"), {"audio": tone(), "name": "Shaker", "use_type": "loop",
                                                   "image": picture("shaker.png")})
        sound = Audio.objects.get(name="Shaker")
        self.assertTrue(sound.image)
        self.assertNotIn("uploads/images/sounds/shaker.png", sound.image.name)  # random folder

    def test_only_the_author_edits_a_sound(self):
        sound = Audio.objects.create(user=self.lucia, name="Mío", audio=tone())
        self.login("tincho")
        self.assertEqual(self.client.get(reverse("audio-edit", args=[sound.slug])).status_code, 403)
        self.assertEqual(self.client.post(reverse("audio-edit", args=[sound.slug]), {"name": "Robado"}).status_code, 403)
        sound.refresh_from_db()
        self.assertEqual((sound.name, sound.user), ("Mío", self.lucia))

    def test_profile_pictures_up_to_ten(self):
        from users.models import ProfileImage
        self.login("lucia")
        self.client.post(reverse("user-profile"), {"realname": "Lucía", "gallery": [picture("a.png"), picture("b.png")]})
        self.assertEqual(ProfileImage.objects.filter(user=self.lucia).count(), 2)
        self.assertContains(self.client.get(self.lucia.get_absolute_url()), 'data-n="2"')
        first = ProfileImage.objects.filter(user=self.lucia).first()
        self.client.post(reverse("user-profile"), {"realname": "Lucía", "gallery-remove": [first.pk],
                                                   "gallery": [picture("%d.png" % i) for i in range(12)]})
        self.assertEqual(ProfileImage.objects.filter(user=self.lucia).count(), 10)  # never more than ten
        page = self.client.get(self.lucia.get_absolute_url())
        self.assertContains(page, 'data-n="5"')  # five on view, the rest one click away
        self.assertContains(page, "+5")
        self.assertContains(page, "data-lightbox")

    def test_profile_picture_from_the_profile(self):
        self.login("lucia")
        self.client.post(reverse("user-profile"), {"realname": "Lucía", "avatar": picture("yo.png")})
        from avatar.models import Avatar
        self.assertTrue(Avatar.objects.filter(user=self.lucia, primary=True).exists())

    # -- profile and my stuff ---------------------------------------------------------

    def test_profile_shows_comments_and_groups_only_to_members(self):
        Message.objects.create(user=self.lucia, msg="un comentario de Lucía", content_object=self.work)
        group = WorkGroup.objects.create(name="3° B", owner=self.lucia)
        self.login("tincho")
        page = self.client.get(self.lucia.get_absolute_url())
        self.assertContains(page, "un comentario de Lucía")
        self.assertNotContains(page, "3° B")
        GroupMember.objects.create(group=group, user=self.tincho)
        self.assertContains(self.client.get(self.lucia.get_absolute_url()), "3° B")

    def test_my_stuff_hides_empty_sections_and_groups(self):
        self.login("tincho")
        html = self.client.get(reverse("my-stuff")).content.decode()
        for anchor in ('href="#obras"', 'href="#sonidos"', 'href="#descargas"', 'id="grupos"'):
            self.assertNotIn(anchor, html)

    def test_footer_without_sponsor_logo_and_crear_without_question(self):
        self.login("lucia")
        self.assertNotContains(self.client.get(reverse("index")), "logo_mecenazgo")
        self.assertNotContains(self.client.get(reverse("create")), "Not a work")
