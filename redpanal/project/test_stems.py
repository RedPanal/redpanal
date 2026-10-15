"""Studio folders: stems as aligned parts, session files, dedup, new takes, quota."""
import os
import shutil
import tempfile

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from audio.models import Audio
from .models import Project, Contribution, Attachment, Membership
from .stems import guess_instrument
from .test_collaboration import tone

TEMP_MEDIA = tempfile.mkdtemp()


def session(name="cancion.cpr", content=b"cubase session bytes"):
    return SimpleUploadedFile(name, content)


@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class StemsTestCase(TestCase):

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA, ignore_errors=True)

    def setUp(self):
        self.lucia = User.objects.create_user("lucia", "l@example.com", "pw")
        self.tincho = User.objects.create_user("tincho", "t@example.com", "pw")
        self.project = Project.objects.create(name="Zamba", user=self.lucia, visibility="private")
        self.client.login(username="lucia", password="pw")

    def upload(self, files, **extra):
        data = {"stems": files}
        data.update(extra)
        return self.client.post(reverse("project-stems", args=[self.project.slug]), data)

    def test_guess_instrument_from_stem_names(self):
        self.assertEqual(guess_instrument("01_Bajo.wav"), "bass")
        self.assertEqual(guess_instrument("Kick In.wav"), "drums")
        self.assertEqual(guess_instrument("Lead Vox.flac"), "voice")
        self.assertEqual(guess_instrument("Gtr acustica L.wav"), "guitar")
        self.assertEqual(guess_instrument("FX riser.wav"), "other")

    def test_folder_becomes_aligned_parts_and_attachments(self):
        response = self.upload([tone("tone.mp3", "01 Bajo.mp3"), tone("tone.ogg", "02 Lead Vox.ogg"),
                                session(), session("idea.mid", b"MThd"), SimpleUploadedFile(".DS_Store", b"x")])
        self.assertEqual(response.status_code, 200)
        parts = self.project.parts()
        self.assertEqual(parts.count(), 2)
        self.assertEqual({p.audio.instrument for p in parts}, {"bass", "voice"})
        self.assertTrue(all(p.offset_ms == 0 for p in parts))
        self.assertEqual({a.kind for a in self.project.attachments.all()}, {"session", "midi"})
        self.assertIn(".DS_Store", " ".join(response.context["result"].errors))

    def test_chosen_instrument_wins_over_the_guess(self):
        self.upload([tone("tone.mp3", "pista3.mp3"), session()], instruments=["piano", ""])
        self.assertEqual(self.project.parts().get().audio.instrument, "piano")

    def test_identical_files_are_not_uploaded_again(self):
        self.upload([tone("tone.mp3", "01 Bajo.mp3"), session()])
        audios_before = Audio.objects.count()
        response = self.upload([tone("tone.mp3", "01 Bajo.mp3"), session()])
        result = response.context["result"]
        self.assertEqual(result.unchanged, ["01 Bajo.mp3"])
        self.assertEqual(result.attachments_unchanged, ["cancion.cpr"])
        self.assertEqual(Audio.objects.count(), audios_before)
        self.assertEqual(self.project.attachments.count(), 1)

    def test_a_new_take_replaces_the_part_and_keeps_the_old_one(self):
        self.upload([tone("tone.mp3", "01 Bajo.mp3"), session()])
        old = self.project.parts().get()
        response = self.upload([tone("tone.ogg", "01 Bajo.mp3"), session(content=b"newer session")])
        self.assertEqual(response.context["result"].replaced, ["01 Bajo.mp3"])
        new = self.project.parts().get()
        self.assertNotEqual(new.pk, old.pk)
        old.refresh_from_db()
        self.assertEqual(old.status, Contribution.ALTERNATIVE)
        current = self.project.attachments.filter(replaced=False)
        self.assertEqual(current.count(), 1)
        self.assertEqual(self.project.attachments.filter(replaced=True).count(), 1)

    def test_same_file_in_another_work_is_stored_once(self):
        self.upload([tone("tone.mp3", "01 Bajo.mp3")])
        other = Project.objects.create(name="Otra", user=self.lucia)
        self.client.post(reverse("project-stems", args=[other.slug]), {"stems": [tone("tone.mp3", "bajo.mp3")]})
        self.assertEqual(Audio.objects.filter(user=self.lucia).count(), 1)
        self.assertEqual(other.parts().get().audio, self.project.parts().get().audio)

    def test_version_keeps_the_session_files_of_the_moment(self):
        self.upload([tone("tone.mp3", "01 Bajo.mp3"), session()])
        v1 = self.project.save_version(self.lucia)
        self.upload([session(content=b"newer session")])
        v2 = self.project.save_version(self.lucia)
        self.assertNotEqual(list(v1.attachments.all()), list(v2.attachments.all()))
        self.assertEqual(v1.attachments.get().sha256, Attachment.objects.filter(replaced=True).get().sha256)

    def test_members_make_a_version_and_need_the_license_agreement(self):
        Membership.objects.create(project=self.project, user=self.tincho)
        self.client.logout()
        self.client.login(username="tincho", password="pw")
        response = self.upload([tone("tone.mp3", "bajo tincho.mp3")])
        self.assertFalse(self.project.contributions.exists())
        self.upload([tone("tone.mp3", "bajo tincho.mp3")], accept_terms="1")
        self.assertEqual(self.project.contributions.filter(status=Contribution.VERSIONED).count(), 1)
        self.assertEqual(self.project.latest_version().created_by, self.tincho)
        self.assertFalse(self.project.parts().exists())  # the author's version stays as it is

    def test_outsiders_cannot_upload_or_download(self):
        self.upload([session()])
        attachment = self.project.attachments.get()
        self.client.logout()
        self.client.login(username="tincho", password="pw")
        self.assertEqual(self.upload([tone()]).status_code, 404)
        self.assertEqual(self.client.get(attachment.get_absolute_url()).status_code, 404)
        self.client.logout()
        self.client.login(username="lucia", password="pw")
        response = self.client.get(attachment.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(b"".join(response.streaming_content), b"cubase session bytes")

    @override_settings(RP_USER_QUOTA_MB=0)
    def test_quota(self):
        response = self.upload([tone("tone.mp3", "01 Bajo.mp3")])
        self.assertFalse(self.project.contributions.exists())
        self.assertTrue(response.context["result"].errors)
