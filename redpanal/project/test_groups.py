"""Groups for classes: join with a code, share works, see who took part."""
import shutil
import tempfile

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from audio.models import Audio
from .models import Project, WorkGroup, GroupMember, Contribution
from .test_collaboration import tone

TEMP_MEDIA = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class GroupsTestCase(TestCase):

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA, ignore_errors=True)

    def setUp(self):
        self.carla = User.objects.create_user("carla", "c@example.com", "pw")
        self.ana = User.objects.create_user("ana", "a@example.com", "pw")
        self.outsider = User.objects.create_user("otro", "o@example.com", "pw")
        self.client.login(username="carla", password="pw")
        self.client.post(reverse("groups"), {"name": "Música 3° B"})
        self.group = WorkGroup.objects.get(name="Música 3° B")

    def as_user(self, username):
        self.client.logout()
        self.client.login(username=username, password="pw")

    def test_code_is_easy_to_dictate(self):
        self.assertEqual(len(self.group.code), 6)
        self.assertFalse(set(self.group.code) & set("01OI"))

    def test_inviting_people_by_their_username(self):
        from social.models import Notification
        # When creating a group…
        self.client.post(reverse("groups"), {"name": "Taller de canción", "people": "@ana, @nadie"})
        taller = WorkGroup.objects.get(name="Taller de canción")
        self.assertTrue(GroupMember.objects.filter(group=taller, user=self.ana).exists())
        self.assertEqual(Notification.objects.get(recipient=self.ana).kind, "member_added")
        # …and from inside it, only the coordinator.
        self.assertContains(self.client.get(self.group.get_absolute_url()), reverse("group-invite", args=[self.group.slug]))
        self.client.post(reverse("group-invite", args=[self.group.slug]), {"people": "@Otro"})
        self.assertTrue(GroupMember.objects.filter(group=self.group, user=self.outsider).exists())
        self.as_user("otro")
        self.assertEqual(self.client.post(reverse("group-invite", args=[self.group.slug]), {"people": "@ana"}).status_code, 403)

    def test_joining_with_a_code(self):
        self.as_user("ana")
        self.client.post(reverse("group-join"), {"code": " %s " % self.group.code.lower()})
        self.assertTrue(GroupMember.objects.filter(group=self.group, user=self.ana).exists())
        self.client.post(reverse("group-join"), {"code": "NOPE99"})
        self.assertEqual(GroupMember.objects.filter(user=self.ana).count(), 1)

    def test_work_for_the_group_is_private_and_shared(self):
        GroupMember.objects.create(group=self.group, user=self.ana)
        response = self.client.get(reverse("create") + "?grupo=%d" % self.group.pk)
        self.assertEqual(response.context["group"], self.group)
        self.assertContains(response, 'name="grupo" value="%d"' % self.group.pk)
        self.client.post(reverse("create"), {
            "audio": tone(), "name": "Canción del curso", "status": "idea", "visibility": "private",
            "grupo": self.group.pk})
        work = Project.objects.get(name="Canción del curso")
        self.assertIn(self.group, work.shared_groups.all())

        self.as_user("ana")
        self.assertEqual(self.client.get(work.get_absolute_url()).status_code, 200)
        self.assertTrue(work.can_contribute(self.ana))
        audio = work.parts().get().audio
        self.assertEqual(self.client.get(reverse("audio-stream", args=[audio.pk])).status_code, 302)
        self.as_user("otro")
        self.assertEqual(self.client.get(work.get_absolute_url()).status_code, 404)

    def test_people_who_join_later_get_access(self):
        work = Project.objects.create(name="Obra", user=self.carla, visibility="private")
        self.client.post(reverse("project-share-group", args=[work.slug]), {"group": self.group.pk})
        self.assertFalse(work.is_member(self.ana))
        GroupMember.objects.create(group=self.group, user=self.ana)
        self.assertTrue(work.is_member(self.ana))
        self.assertIn(work, Project.objects.visible_to(self.ana))

    def test_teacher_sees_who_took_part(self):
        GroupMember.objects.create(group=self.group, user=self.ana)
        work = Project.objects.create(name="Obra", user=self.carla, visibility="private")
        work.shared_groups.add(self.group)
        a = Audio.objects.create(user=self.ana, name="percusión", audio=tone())
        Contribution.objects.create(project=work, audio=a, contributor=self.ana)
        rows = dict((m.user, n) for m, n in self.client.get(self.group.get_absolute_url()).context["rows"])
        self.assertEqual(rows[self.ana], 1)

    def test_only_members_see_the_group_and_only_the_author_shares(self):
        self.as_user("otro")
        self.assertEqual(self.client.get(self.group.get_absolute_url()).status_code, 404)
        work = Project.objects.create(name="Ajena", user=self.ana, visibility="private")
        self.assertEqual(self.client.post(reverse("project-share-group", args=[work.slug]),
                                          {"group": self.group.pk}).status_code, 403)

    def test_leaving_removes_access(self):
        member = GroupMember.objects.create(group=self.group, user=self.ana)
        work = Project.objects.create(name="Obra", user=self.carla, visibility="private")
        work.shared_groups.add(self.group)
        self.as_user("ana")
        self.client.post(reverse("group-member-remove", args=[self.group.slug, member.pk]))
        self.assertFalse(work.is_member(self.ana))
