"""Uploading: only the file is needed; organize, complete and share afterwards."""
import shutil
import tempfile

from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase, override_settings
from django.urls import reverse
from actstream.models import Action

from audio.models import Audio, Download
from social.models import Notification
from .models import Contribution, GroupMember, Project, WorkGroup
from .test_collaboration import tone

TEMP_MEDIA = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class UploadTestCase(TestCase):

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA, ignore_errors=True)

    def setUp(self):
        self.lucia = User.objects.create_user("lucia", "l@example.com", "pw")
        self.tincho = User.objects.create_user("tincho", "t@example.com", "pw")
        self.client.login(username="lucia", password="pw")

    def upload(self, source="tone.ogg", name="02_bajo_final_v3.ogg"):
        r = self.client.post(reverse("upload-file"), {"audio": tone(source, name)})
        return r, (Audio.objects.get(pk=r.json()["id"]) if r.status_code == 200 else None)

    # -- one file in, private, with guesses -------------------------------------------------

    def test_a_file_comes_in_private_with_its_name_and_instrument_guessed(self):
        r, audio = self.upload()
        self.assertEqual(r.status_code, 200)
        self.assertEqual((audio.name, audio.instrument, audio.use_type), ("Bajo", "bass", "track"))
        self.assertTrue(audio.needs_details)
        self.assertNotIn(audio, Audio.objects.visible_to(None))
        self.assertNotIn(audio, Audio.objects.visible_to(self.tincho))
        self.assertIn(audio, Audio.objects.visible_to(self.lucia))
        self.assertFalse(Action.objects.filter(verb="audio_created", public=True).exists())  # not in feeds yet

    def test_the_same_file_twice_is_the_same_sound(self):
        _r, first = self.upload()
        _r, again = self.upload()
        self.assertEqual(first, again)

    def test_the_type_comes_from_the_name_too(self):
        _r, audio = self.upload("tone.ogg", "pad loop 90bpm.ogg")
        self.assertEqual(audio.use_type, "loop")

    def test_what_cannot_come_in_says_why(self):
        r = self.client.post(reverse("upload-file"), {"audio": tone("tone.ogg", "notas.txt")})
        self.assertEqual(r.status_code, 400)
        self.assertIn("error", r.json())
        with self.settings(RP_USER_QUOTA_MB=0):
            self.assertEqual(self.upload()[0].status_code, 400)

    # -- organize -------------------------------------------------------------------------

    def organize(self, audios, **data):
        data["ids"] = ",".join(str(a.pk) for a in audios)
        return self.client.post(reverse("upload-organize"), data).json()

    def test_files_of_one_project_become_a_private_work(self):
        _r, bass = self.upload("tone.ogg", "bajo.ogg")
        _r, drums = self.upload("tone.mp3", "bateria.mp3")
        res = self.organize([bass, drums], together="1", stems="1", name="Zamba")
        work = Project.objects.get(slug=res["project"])
        self.assertEqual((work.name, work.visibility, work.user), ("Zamba", "private", self.lucia))
        self.assertEqual(set(work.parts().values_list("audio_id", flat=True)), {bass.pk, drums.pk})
        self.assertEqual(work.parts().filter(alignment=Contribution.ALIGNED).count(), 2)
        self.assertIn(reverse("upload-complete"), res["next"])

    def test_files_that_are_not_stems_do_not_play_in_sync(self):
        _r, bass = self.upload("tone.ogg", "bajo.ogg")
        _r, idea = self.upload("tone.mp3", "idea.mp3")
        work = Project.objects.get(slug=self.organize([bass, idea], together="1", stems="0")["project"])
        self.assertFalse(work.parts().filter(alignment=Contribution.ALIGNED).exists())

    def test_separate_sounds_stay_on_their_own_and_credit_where_they_come_from(self):
        original = Audio.objects.create(user=self.tincho, name="Candombe", audio=tone())
        _r, sound = self.upload()
        res = self.organize([sound], together="0", sonido=original.pk)
        sound.refresh_from_db()
        self.assertIsNone(res["project"])
        self.assertFalse(sound.contributions.exists())
        self.assertEqual(sound.source_audio, original)

    def test_nobody_organizes_other_peoples_files(self):
        theirs = Audio.objects.create(user=self.tincho, name="De Tincho", audio=tone())
        r = self.client.post(reverse("upload-organize"), {"ids": str(theirs.pk), "together": "1"})
        self.assertEqual(r.status_code, 404)

    # -- complete -------------------------------------------------------------------------

    def test_completing_corrects_the_guesses_and_ends_the_reminder(self):
        _r, sound = self.upload()
        self.assertContains(self.client.get(reverse("my-stuff")), "?pendientes=1")
        theirs = Audio.objects.create(user=self.tincho, name="Pad de Tincho", audio=tone())
        Download.objects.create(user=self.lucia, audio=theirs)
        self.client.post(reverse("upload-complete"), {
            "ids": str(sound.pk), "f%d-name" % sound.pk: "Bajo de la zamba", "f%d-type" % sound.pk: "loop",
            "f%d-instrument" % sound.pk: "bass", "origin": "a:%d" % theirs.pk})
        sound.refresh_from_db()
        self.assertEqual((sound.name, sound.use_type, sound.needs_details), ("Bajo de la zamba", "loop", False))
        self.assertEqual(sound.source_audio, theirs)
        self.assertNotContains(self.client.get(reverse("my-stuff")), "?pendientes=1")

    def test_instrument_is_open_tags_are_added_and_types_are_explained(self):
        _r, sound = self.upload()
        page = self.client.get(reverse("upload-complete"), {"ids": sound.pk}).content.decode()
        self.assertIn('class="rp-info rp-info-list"', page)
        self.assertIn("un instrumento o una voz por separado", page)  # what "track" is
        self.assertIn('list="rp-instruments"', page)
        self.assertIn('name="f%d-tags"' % sound.pk, page)
        self.client.post(reverse("upload-complete"), {
            "ids": str(sound.pk), "f%d-instrument" % sound.pk: "Charango",
            "f%d-tags" % sound.pk: "#Candombe, lluvia campo"})
        sound.refresh_from_db()
        self.assertEqual(sound.instrument, "Charango")  # not in the list: kept as written
        self.assertEqual(sorted(sound.tags.names()), ["campo", "candombe", "lluvia"])
        self.client.post(reverse("upload-complete"), {"ids": str(sound.pk), "f%d-instrument" % sound.pk: "Bajo"})
        sound.refresh_from_db()
        self.assertEqual(sound.instrument, "bass")  # a known one, by its name: its code, to match requests

    # -- share ------------------------------------------------------------------------------

    def share(self, sound, **data):
        data["ids"] = str(sound.pk)
        return self.client.post(reverse("upload-share"), data)

    def test_publishing_needs_the_license_and_then_anyone_listens(self):
        _r, sound = self.upload()
        self.share(sound, how="public")
        self.assertNotIn(sound, Audio.objects.visible_to(None))
        self.share(sound, how="public", accept_license="1")
        self.assertIn(sound, Audio.objects.visible_to(None))
        ct = ContentType.objects.get_for_model(Audio)
        self.assertTrue(Action.objects.get(verb="audio_created", action_object_content_type=ct,
                                           action_object_object_id=str(sound.pk)).public)

    def test_sharing_with_a_group_or_a_person(self):
        carla = User.objects.create_user("carla", "c@example.com", "pw")
        group = WorkGroup.objects.create(name="Taller", owner=self.lucia)
        GroupMember.objects.create(group=group, user=self.tincho)
        _r, sound = self.upload()
        self.share(sound, how="group", group=group.pk)
        self.assertIn(sound, Audio.objects.visible_to(self.tincho))
        self.assertNotIn(sound, Audio.objects.visible_to(carla))
        self.share(sound, how="person", username="@carla")
        self.assertIn(sound, Audio.objects.visible_to(carla))
        self.assertEqual(Notification.objects.get(recipient=carla).kind, "shared")
        self.assertNotIn(sound, Audio.objects.visible_to(None))  # still not published

    def test_a_work_is_shared_the_same_way(self):
        _r, a = self.upload("tone.ogg", "bajo.ogg")
        _r, b = self.upload("tone.mp3", "voz.mp3")
        work = Project.objects.get(slug=self.organize([a, b], together="1")["project"])
        self.client.post(reverse("upload-share"), {"proyecto": work.slug, "how": "person", "username": "tincho"})
        self.assertTrue(work.can_listen(self.tincho))
        self.client.post(reverse("upload-share"), {"proyecto": work.slug, "how": "public", "accept_license": "1"})
        work.refresh_from_db()
        self.assertEqual(work.visibility, "public")

    def test_images_while_completing_take_the_place_of_the_icon(self):
        from social.test_community import picture
        _r, a = self.upload("tone.ogg", "bajo.ogg")
        _r, b = self.upload("tone.mp3", "voz.mp3")
        work = Project.objects.get(slug=self.organize([a, b], together="1")["project"])
        self.client.post(reverse("upload-complete"), {"proyecto": work.slug, "project_image": picture("tapa.png"),
                                                      "f%d-image" % a.pk: picture("bajo.png")})
        work.refresh_from_db()
        a.refresh_from_db()
        self.assertTrue(work.image)
        self.assertTrue(a.image)
        self.assertContains(self.client.get(reverse("my-stuff")), "rp-cover")

    def test_a_project_from_a_sound_can_start_with_just_a_name(self):
        original = Audio.objects.create(user=self.tincho, name="Candombe", audio=tone())
        page = self.client.get(reverse("create") + "?sonido=%d" % original.pk)
        self.assertContains(page, reverse("upload-new-project"))
        r = self.client.post(reverse("upload-new-project"), {"name": "Candombe nocturno", "sonido": original.pk})
        work = Project.objects.get(name="Candombe nocturno")
        self.assertRedirects(r, work.get_absolute_url(), fetch_redirect_response=False)
        self.assertEqual((work.user, work.visibility, work.parts().count()), (self.lucia, "private", 0))
        self.assertTrue(work.sources.filter(audio=original).exists())  # credited from the start

    def test_the_owner_finds_how_to_share_a_private_sound(self):
        _r, sound = self.upload()
        self.assertContains(self.client.get(sound.get_absolute_url()), "%s?ids=%d" % (reverse("upload-share"), sound.pk))
