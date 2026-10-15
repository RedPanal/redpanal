"""Where favorites are: Estudio › Favorites, posts and comments apart, each one linking to where it was written."""
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from project.models import Project
from social.models import Message


class FavoritesTestCase(TestCase):

    def setUp(self):
        self.lucia = User.objects.create_user("lucia", "l@example.com", "pw")
        self.tincho = User.objects.create_user("tincho", "t@example.com", "pw")
        self.work = Project.objects.create(user=self.tincho, name="Murga", slug="murga")
        self.client.login(username="lucia", password="pw")

    def favorite(self, target, obj):
        return self.client.post(reverse("react", args=["favorite", target, obj.pk]), {"next": "/"}, follow=True)

    def test_a_favorite_comment_shows_in_estudio_with_where_it_was_written(self):
        comment = Message.objects.create(user=self.tincho, msg="falta el redoblante", content_object=self.work)
        post = Message.objects.create(user=self.tincho, msg="ensayo el jueves")
        self.favorite("comentario", comment)
        self.favorite("comentario", post)
        self.assertIn('href="%s"' % reverse("my-favorites"), self.client.get(reverse("my-stuff")).content.decode())
        html = self.client.get(reverse("my-favorites")).content.decode()
        self.assertIn('id="fav-posts"', html)
        self.assertIn("falta el redoblante", html)
        self.assertIn("«Murga»", html)
        self.assertIn('href="/p/murga/#c%d"' % comment.pk, html)
        self.assertIn('href="/tincho/#c%d"' % post.pk, html)

    def test_the_link_lands_on_the_comment(self):
        comment = Message.objects.create(user=self.tincho, msg="falta el redoblante", content_object=self.work)
        reply = Message.objects.create(user=self.lucia, msg="lo grabo yo", parent=comment)
        self.assertEqual(reply.get_absolute_url(), "/p/murga/#c%d" % comment.pk)
        self.assertIn('id="c%d"' % comment.pk, self.client.get(self.work.get_absolute_url()).content.decode())

    def test_favoriting_says_where_to_find_it(self):
        comment = Message.objects.create(user=self.tincho, msg="falta el redoblante", content_object=self.work)
        response = self.favorite("comentario", comment)
        self.assertContains(response, "Estudio")

    def test_favorites_filter_by_kind_and_the_header_menu_stays_for_the_account(self):
        from audio.models import Audio
        from project.test_collaboration import tone
        sound = Audio.objects.create(user=self.tincho, name="Pad", audio=tone())
        comment = Message.objects.create(user=self.tincho, msg="falta el redoblante", content_object=self.work)
        self.favorite("sonido", sound)
        self.favorite("comentario", comment)
        everything = self.client.get(reverse("my-favorites")).content.decode()
        self.assertIn("Pad", everything)
        self.assertIn("falta el redoblante", everything)
        self.assertIn('href="?ver=sonidos"', everything)
        self.assertNotIn('href="?ver=proyectos"', everything)  # no favorite projects: no filter for them
        only_sounds = self.client.get(reverse("my-favorites"), {"ver": "sonidos"}).content.decode()
        self.assertIn("Pad", only_sounds)
        self.assertNotIn("falta el redoblante", only_sounds)
        self.assertNotIn("fa-heart fa-fw", everything)  # not in the ⋯ menu anymore

    def test_downloads_have_their_own_tab(self):
        html = self.client.get(reverse("my-downloads")).content.decode()
        self.assertIn('aria-current="page"', html)
        self.assertIn('href="%s"' % reverse("my-favorites"), html)

    def test_the_player_pill_has_previous_and_close(self):
        html = self.client.get(reverse("explore")).content.decode()
        pill = html.split("data-dock-pill", 1)[1].split("data-dock-sheet", 1)[0]
        for attr in ("data-dock-prev", "data-dock-play", "data-dock-next", "data-dock-close"):
            self.assertIn(attr, pill)

    def test_the_logo_is_the_mark_and_the_name(self):
        html = self.client.get(reverse("explore")).content.decode()
        self.assertIn('class="rp-logo"', html)
        self.assertIn('fill="url(#rp-logo-grad)"', html)  # the hexagons with their gradient
        self.assertEqual(html.split('class="rp-logo-name"', 1)[1].split("</g>", 1)[0].count("<path"), 8)  # R-e-d-P-a-n-a-l
        self.assertIn('aria-label="RedPanal"', html)
        self.assertNotIn("redpanal-50.png", html)
