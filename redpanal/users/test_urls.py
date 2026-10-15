"""Addresses: people at the root, pages in Spanish, and every old address still arriving."""
from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.urls import resolve, reverse
from io import StringIO

from project.models import Project, WorkGroup
from users.account_adapter import MyAccountAdapter
from users.reserved import is_reserved, route_names


class AddressesTestCase(TestCase):

    def setUp(self):
        self.lucia = User.objects.create_user("lucia", "l@example.com", "pw")

    def test_people_live_at_the_root(self):
        self.assertEqual(self.lucia.get_absolute_url(), "/lucia/")
        self.assertEqual(self.client.get("/lucia/").status_code, 200)
        self.assertEqual(self.client.get("/nadie-se-llama-asi/").status_code, 404)

    def test_old_addresses_of_people_move_permanently(self):
        for old, new in (("/u/lucia/", "/lucia/"), ("/u/people/", "/personas/"), ("/u/lucia/projects/", "/lucia/"),
                         ("/u/lucia/activities/", "/lucia/actividad/"), ("/accounts/profile/", "/ajustes/"),
                         ("/u/delete/", "/ajustes/borrar-cuenta/")):
            response = self.client.get(old)
            self.assertEqual((response.status_code, response["Location"]), (301, new), old)

    def test_a_post_to_an_old_address_stays_a_post(self):
        self.client.login(username="lucia", password="pw")
        User.objects.create_user("tincho", "t@example.com", "pw")
        response = self.client.post("/u/tincho/seguir/")
        self.assertEqual((response.status_code, response["Location"]), (308, "/tincho/seguir/"))

    def test_pages_win_over_people_and_their_names_are_reserved(self):
        self.assertEqual(resolve("/explorar/").url_name, "explore")
        for name in ("explorar", "Estudio", "grupos", "p", "u", "ajustes", "personas", "robots.txt", "sin-conexion"):
            self.assertTrue(is_reserved(name), name)
        self.assertFalse(is_reserved("lucia"))
        self.assertLessEqual({"explorar", "estudio", "crear", "avisos", "grupos", "p", "a", "u", "tag", "api"},
                             route_names())

    def test_signing_up_with_the_name_of_a_page_is_refused(self):
        from django import forms
        with self.assertRaises(forms.ValidationError):
            MyAccountAdapter().clean_username("explorar")
        self.assertEqual(MyAccountAdapter().clean_username("candombera"), "candombera")

    def test_check_usernames_finds_people_hidden_by_a_page(self):
        User.objects.create_user("explorar", "e@example.com", "pw")
        out = StringIO()
        call_command("check_usernames", stdout=out)
        self.assertIn("Hidden by a page: explorar", out.getvalue())

    def test_works_and_sounds_in_spanish_with_the_old_ones_moving(self):
        work = Project.objects.create(user=self.lucia, name="Murga", slug="murga")
        self.assertEqual(reverse("project-edit", args=["murga"]), "/p/murga/editar/")
        self.assertEqual(reverse("audio-delete", args=["pad"]), "/a/pad/borrar/")
        self.assertEqual(self.client.get("/p/murga/edit/")["Location"], "/p/murga/editar/")
        self.assertEqual(self.client.get("/p/create/?from=murga")["Location"], "/crear/?from=murga")
        self.assertEqual(self.client.get("/p/list/")["Location"], "/explorar/")
        self.assertEqual(self.client.get("/a/upload/")["Location"], "/crear/sonido/")
        self.assertTrue(work)

    def test_groups_by_name_and_the_old_numbers_moving(self):
        group = WorkGroup.objects.create(name="Taller de los jueves", owner=self.lucia)
        twin = WorkGroup.objects.create(name="Taller de los jueves", owner=self.lucia)
        digits = WorkGroup.objects.create(name="2024", owner=self.lucia)
        self.assertEqual(group.get_absolute_url(), "/grupos/taller-de-los-jueves/")
        self.assertEqual(twin.slug, "taller-de-los-jueves-2")
        self.assertEqual(digits.slug, "grupo-2024")
        self.client.login(username="lucia", password="pw")
        self.assertEqual(self.client.get("/grupos/%d/" % group.pk)["Location"], "/grupos/taller-de-los-jueves/")
        self.assertEqual(self.client.get(group.get_absolute_url()).status_code, 200)

    def test_robots_keep_each_persons_own_pages_out_of_search(self):
        text = self.client.get("/robots.txt").content.decode()
        self.assertIn("Disallow: /estudio/", text)
        self.assertIn("Disallow: /ajustes/", text)
