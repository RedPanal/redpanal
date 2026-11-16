"""Download control per work, and the sound mark on previews."""
import shutil
import tempfile

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from pydub import AudioSegment

from audio.models import Audio
from .models import Contribution, Membership, Project, Attachment
from .preview import add_sound_mark, build_preview
from .test_collaboration import tone
from .test_stems import session

TEMP_MEDIA = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class DownloadsTestCase(TestCase):

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA, ignore_errors=True)

    def setUp(self):
        self.owner = User.objects.create_user("autora", "a@example.com", "pw")
        self.member = User.objects.create_user("miembro", "m@example.com", "pw")
        self.work = Project.objects.create(name="Obra", user=self.owner, visibility="private")
        Membership.objects.create(project=self.work, user=self.member)
        self.audio = Audio.objects.create(user=self.owner, name="guitarra", audio=tone())
        Contribution.objects.create(project=self.work, audio=self.audio, contributor=self.owner, status="included")
        self.client.login(username="autora", password="pw")
        self.client.post(reverse("project-stems", args=[self.work.slug]), {"stems": [session()]})
        self.attachment = Attachment.objects.get()

    def statuses(self):
        return [self.client.get(u).status_code for u in (
            reverse("project-parts-zip", args=[self.work.slug]),
            reverse("audio-download", args=[self.audio.pk]),
            self.attachment.get_absolute_url())]

    def test_downloads_allowed_by_default(self):
        self.client.logout()
        self.client.login(username="miembro", password="pw")
        self.assertEqual(self.statuses(), [200, 200, 200])

    def test_turning_downloads_off(self):
        self.client.post(reverse("project-visibility", args=[self.work.slug]), {"visibility": "private"})
        self.work.refresh_from_db()
        self.assertFalse(self.work.allow_downloads)
        self.assertEqual(self.statuses(), [200, 200, 200])  # the author keeps access
        self.client.logout()
        self.client.login(username="miembro", password="pw")
        self.assertEqual(self.statuses(), [403, 403, 403])
        # Listening still works, and the page doesn't offer the buttons.
        self.assertEqual(self.client.get(reverse("audio-stream", args=[self.audio.pk])).status_code, 302)
        page = self.client.get(self.work.get_absolute_url())
        self.assertNotContains(page, reverse("project-parts-zip", args=[self.work.slug]))

    def test_public_work_settings_save_without_reconfirming(self):
        self.work.visibility = "public"
        self.work.save()
        self.client.post(reverse("project-visibility", args=[self.work.slug]),
                         {"visibility": "public", "allow_downloads": ""})
        self.work.refresh_from_db()
        self.assertEqual(self.work.visibility, "public")
        self.assertFalse(self.work.allow_downloads)

    def test_people_always_download_their_own_files(self):
        self.work.allow_downloads = False
        self.work.save()
        own = Audio.objects.create(user=self.member, name="mi bajo", audio=tone("tone.ogg"))
        Contribution.objects.create(project=self.work, audio=own, contributor=self.member)
        self.client.logout()
        self.client.login(username="miembro", password="pw")
        self.assertEqual(self.client.get(reverse("audio-download", args=[own.pk])).status_code, 200)

    def test_sound_mark(self):
        silence = AudioSegment.silent(duration=30000, frame_rate=44100).set_channels(1)
        marked = add_sound_mark(silence)
        self.assertEqual(len(marked), len(silence))
        self.assertGreater(marked[5000:5300].max, 0)
        self.assertEqual(marked[1000:4000].max, 0)

    def test_preview_with_and_without_mark_differ(self):
        import io
        from django.core.files.uploadedfile import SimpleUploadedFile
        buf = io.BytesIO()
        AudioSegment.silent(duration=12000, frame_rate=44100).export(buf, format="wav")
        long_part = Audio.objects.create(user=self.owner, name="larga", audio=SimpleUploadedFile("larga.wav", buf.getvalue()))
        Contribution.objects.create(project=self.work, audio=long_part, contributor=self.owner, status="included")
        self.work.visibility = "open_call"
        plain = build_preview(self.work).read()
        self.work.preview_watermark = True
        marked = build_preview(self.work).read()
        self.assertNotEqual(plain, marked)
