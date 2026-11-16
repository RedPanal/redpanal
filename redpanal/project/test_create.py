"""Crear: every way to start, from one place."""
import shutil
import tempfile

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from audio.models import Audio
from .models import Project, Contribution
from .test_collaboration import tone

TEMP_MEDIA = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class CreateTestCase(TestCase):

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA, ignore_errors=True)

    def setUp(self):
        self.lucia = User.objects.create_user("lucia", "l@example.com", "pw")
        self.tincho = User.objects.create_user("tincho", "t@example.com", "pw")
        self.client.login(username="lucia", password="pw")

    def test_create_is_upload_or_record(self):
        html = self.client.get(reverse("create")).content.decode()
        for marker in ("data-drop", "webkitdirectory", "multiple", "data-rec-start", reverse("upload-file")):
            self.assertIn(marker, html)
        # No categories to choose before uploading.
        for gone in (reverse("create-folder"), reverse("create-sound")):
            self.assertNotIn(gone, html)

    def test_where_it_comes_from_is_shown_before_uploading(self):
        Project.objects.create(user=self.tincho, name="Pública de Tincho", slug="publica", visibility="public")
        Project.objects.create(user=self.tincho, name="Privada de Tincho", slug="privada", visibility="private")
        self.assertContains(self.client.get(reverse("create") + "?from=publica"), "Pública de Tincho")
        response = self.client.get(reverse("create") + "?from=privada")
        self.assertIsNone(response.context["source"])
        self.assertNotContains(response, "Privada de Tincho")

    # -- studio folder -----------------------------------------------------------

    def test_new_work_from_a_folder(self):
        response = self.client.post(reverse("create-folder"), {
            "name": "Zamba del puerto", "status": "in_progress", "visibility": "private",
            "missing": ["voice"], "missing_text": "una voz grave",
            "stems": [tone("tone.mp3", "01 Bajo.mp3"), tone("tone.flac", "02 Kick.flac"),
                      tone("tone.ogg", "Zamba.cpr")],
            "instruments": ["", "", ""]})
        work = Project.objects.get(name="Zamba del puerto")
        self.assertRedirects(response, work.get_absolute_url(), fetch_redirect_response=False)
        self.assertEqual(work.user, self.lucia)
        self.assertEqual(work.visibility, "private")
        self.assertEqual(work.parts().count(), 2)
        self.assertEqual(set(work.parts().values_list("audio__instrument", flat=True)), {"bass", "drums"})
        self.assertEqual(work.attachments.count(), 1)
        self.assertEqual(work.requests.get().description, "una voz grave")

    def test_a_folder_without_audio_creates_nothing(self):
        response = self.client.post(reverse("create-folder"), {
            "name": "Vacía", "status": "idea", "visibility": "private", "stems": [tone("tone.ogg", "Zamba.cpr")]})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Project.objects.filter(name="Vacía").exists())

    # -- sound to share ------------------------------------------------------------

    def test_share_a_sound(self):
        response = self.client.post(reverse("create-sound"), {
            "audio": tone(), "name": "Candombe chico", "use_type": "field", "instrument": "drums",
            "tempo": "100", "musical_key": "La menor", "description": ""})
        sound = Audio.objects.get(name="Candombe chico")
        self.assertRedirects(response, sound.get_absolute_url(), fetch_redirect_response=False)
        self.assertEqual((sound.use_type, sound.tempo, sound.musical_key), ("field", 100, "La menor"))
        self.assertFalse(Contribution.objects.filter(audio=sound).exists())
        self.assertIn(sound, Audio.objects.visible_to(None))

    def test_old_upload_address_leads_to_sharing_a_sound(self):
        self.assertTemplateUsed(self.client.get(reverse("create-sound")), "project/sound_create.html")

    # -- my stuff ----------------------------------------------------------------

    def test_my_stuff_shows_only_what_exists_and_no_groups(self):
        from .models import WorkGroup
        self.client.post(reverse("create-sound"), {"audio": tone(), "name": "Pad en La", "use_type": "loop"})
        WorkGroup.objects.create(name="Música 3° B", owner=self.lucia)
        html = self.client.get(reverse("my-stuff")).content.decode()
        self.assertIn('id="sonidos"', html)
        self.assertIn("Pad en La", html)
        for absent in ('id="obras"', 'id="aportes"', 'id="descargas"', 'id="grupos"', "Música 3° B"):
            self.assertNotIn(absent, html)  # groups live in the profile now

    def test_pending_contributions_come_first(self):
        work = Project.objects.create(user=self.tincho, name="De Tincho", slug="de-tincho", visibility="public")
        older = Audio.objects.create(user=self.lucia, name="toma vieja", audio=tone())
        newer = Audio.objects.create(user=self.lucia, name="toma nueva", audio=tone())
        Contribution.objects.create(project=work, audio=newer, contributor=self.lucia, status=Contribution.INCLUDED)
        pending = Contribution.objects.create(project=work, audio=older, contributor=self.lucia,
                                              status=Contribution.PROPOSED)
        response = self.client.get(reverse("my-stuff"))
        self.assertEqual(list(response.context["contributions"])[0], pending)

    def test_creating_needs_an_account(self):
        self.client.logout()
        for name in ("create-folder", "create-sound"):
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 302)
            self.assertIn(reverse("account_login"), response["Location"])
