"""The persistent player: what comes next, collections, playlists, and what pages hand to it."""
import shutil
import tempfile

from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase, override_settings
from django.urls import reverse

from audio.models import Audio, Download, Playlist
from project.models import Project, Contribution
from project.test_collaboration import tone
from social.models import Reaction

TEMP_MEDIA = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class PlayerTestCase(TestCase):

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA, ignore_errors=True)

    def setUp(self):
        self.lucia = User.objects.create_user("lucia", "l@example.com", "pw")
        self.tincho = User.objects.create_user("tincho", "t@example.com", "pw")
        self.seed = Audio.objects.create(user=self.lucia, name="Candombe", audio=tone(), instrument="drums")
        self.seed.tags.add("candombe")
        self.tagged = Audio.objects.create(user=self.tincho, name="Otro candombe", audio=tone())
        self.tagged.tags.add("candombe")
        self.same_instrument = Audio.objects.create(user=self.tincho, name="Tambor", audio=tone(), instrument="drums")
        self.other = Audio.objects.create(user=self.tincho, name="Pad", audio=tone())

    def next_titles(self, audio, exclude=""):
        r = self.client.get(reverse("player-next", args=[audio.pk]), {"excluir": exclude})
        return [t["title"] for t in r.json()["tracks"]]

    def test_next_brings_similar_sounds_first(self):
        titles = self.next_titles(self.seed)
        self.assertEqual(titles[:2], ["Otro candombe", "Tambor"])  # shared hashtag first, then instrument
        self.assertIn("Pad", titles)  # the newest fill the rest
        self.assertNotIn("Candombe", titles)

    def test_next_leaves_out_what_was_played_parts_and_private_sounds(self):
        secret = Project.objects.create(user=self.tincho, name="Secreto", slug="secreto", visibility="private")
        part = Audio.objects.create(user=self.tincho, name="Parte privada", audio=tone(), instrument="drums")
        Contribution.objects.create(project=secret, audio=part, contributor=self.tincho, status=Contribution.INCLUDED)
        titles = self.next_titles(self.seed, exclude="%d" % self.tagged.pk)
        self.assertNotIn("Otro candombe", titles)
        self.assertNotIn("Parte privada", titles)

    def test_a_track_carries_what_the_player_shows(self):
        track = self.client.get(reverse("player-next", args=[self.other.pk])).json()["tracks"][0]
        self.assertEqual(set(track), {"id", "title", "artist", "url", "src", "peaks", "duration", "cover"})
        self.assertTrue(track["src"].endswith("/escuchar/"))

    def test_the_expanded_player_shows_the_work_labels_and_what_you_can_do(self):
        work = Project.objects.create(user=self.lucia, name="Murga", slug="murga")
        Contribution.objects.create(project=work, audio=self.seed, contributor=self.lucia, status=Contribution.INCLUDED)
        url = reverse("player-track", args=[self.seed.pk])
        anon = self.client.get(url).json()
        self.assertEqual(anon["project"]["name"], "Murga")
        self.assertFalse(anon["can_react"])
        self.client.login(username="tincho", password="pw")
        Reaction.objects.create(user=self.tincho, kind=Reaction.FAVORITE, content_object=self.seed)
        mine = self.client.get(url).json()
        self.assertTrue(mine["can_react"])
        self.assertTrue(mine["favorite"])
        self.assertFalse(mine["amplified"])
        self.client.login(username="lucia", password="pw")
        self.assertFalse(self.client.get(url).json()["can_react"])  # not on your own sound

    def test_the_expanded_player_keeps_private_sounds_private(self):
        secret = Audio.objects.create(user=self.lucia, name="Boceto", audio=tone(), visibility="private")
        self.assertEqual(self.client.get(reverse("player-track", args=[secret.pk])).status_code, 404)

    def test_favorites_and_downloads_are_your_own(self):
        self.assertEqual(self.client.get(reverse("player-favorites")).status_code, 302)
        Reaction.objects.create(user=self.tincho, kind=Reaction.FAVORITE,
                                content_type=ContentType.objects.get_for_model(Audio), object_id=self.seed.pk)
        Download.objects.create(user=self.tincho, audio=self.other)
        self.client.login(username="lucia", password="pw")
        self.assertEqual(self.client.get(reverse("player-favorites")).json()["tracks"], [])
        self.client.login(username="tincho", password="pw")
        self.assertEqual([t["title"] for t in self.client.get(reverse("player-favorites")).json()["tracks"]], ["Candombe"])
        self.assertEqual([t["title"] for t in self.client.get(reverse("player-downloads")).json()["tracks"]], ["Pad"])

    def test_playlists_belong_to_their_owner(self):
        self.client.login(username="tincho", password="pw")
        r = self.client.post(reverse("player-playlist-create"), {"name": "Para ensayar", "audio": self.seed.pk})
        playlist = Playlist.objects.get(pk=r.json()["id"])
        self.client.post(reverse("player-playlist-add", args=[playlist.pk]), {"audio": self.other.pk})
        tracks = self.client.get(reverse("player-playlist", args=[playlist.pk])).json()["tracks"]
        self.assertEqual([t["title"] for t in tracks], ["Candombe", "Pad"])
        self.client.post(reverse("player-playlist-remove", args=[playlist.pk]), {"audio": self.seed.pk})
        self.assertEqual(playlist.items.count(), 1)
        self.client.login(username="lucia", password="pw")
        self.assertEqual(self.client.get(reverse("player-playlist", args=[playlist.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("player-playlist-add", args=[playlist.pk]),
                                          {"audio": self.seed.pk}).status_code, 404)
        self.assertEqual(self.client.post(reverse("player-playlist-delete", args=[playlist.pk])).status_code, 404)

    def test_a_playlist_cannot_take_a_sound_you_cannot_hear(self):
        hidden = Audio.objects.create(user=self.lucia, name="Oculto", audio=tone(), moderation_hidden=True)
        self.client.login(username="tincho", password="pw")
        r = self.client.post(reverse("player-playlist-create"), {"name": "Lista", "audio": hidden.pk})
        self.assertEqual(r.status_code, 404)

    def test_pages_carry_the_player_and_hand_it_their_files(self):
        self.client.login(username="tincho", password="pw")
        html = self.client.get(reverse("explore")).content.decode()
        self.assertIn('id="rp-dock"', html)
        self.assertIn("rp-dock.js", html)
        self.assertNotIn("mediaelement-and-player", html)
        self.assertIn('data-item-id="%d"' % self.other.pk, html)
        for region in ('id="header"', 'id="rp-toasts-slot"', 'id="main"', 'id="rp-tabbar"', 'id="rp-page-scripts"'):
            self.assertIn(region, html)
