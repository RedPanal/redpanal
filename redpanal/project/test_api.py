"""Works API used by the studio sync tool."""
import json
import shutil
import tempfile

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from .models import Membership, Project
from .test_collaboration import tone
from .test_stems import session

TEMP_MEDIA = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class WorksApiTestCase(TestCase):

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA, ignore_errors=True)

    def setUp(self):
        self.owner = User.objects.create_user("autora", "a@example.com", "pw")
        self.member = User.objects.create_user("miembro", "m@example.com", "pw")
        self.stranger = User.objects.create_user("otro", "o@example.com", "pw")
        self.work = Project.objects.create(name="Estudio", user=self.owner, visibility="private")
        Membership.objects.create(project=self.work, user=self.member)

    def token(self, username):
        r = self.client.post("/api/auth/login/", json.dumps({"username": username, "password": "pw"}),
                             content_type="application/json")
        return {"HTTP_AUTHORIZATION": "Bearer " + r.json()["token"]}

    def test_requires_a_token(self):
        self.assertEqual(self.client.get("/api/works/").status_code, 401)

    def test_listing_and_detail_follow_access_rules(self):
        auth = self.token("otro")
        self.assertNotIn("estudio", [w["slug"] for w in self.client.get("/api/works/", **auth).json()])
        self.assertEqual(self.client.get("/api/works/estudio/", **auth).status_code, 404)
        auth = self.token("miembro")
        detail = self.client.get("/api/works/estudio/", **auth).json()
        self.assertTrue(detail["can_contribute"])
        self.assertIn("cpr", detail["accepted_extensions"]["attachments"])

    def test_push_stems_then_only_changes(self):
        auth = self.token("autora")
        r = self.client.post("/api/works/estudio/stems/", {"stems": [tone("tone.mp3", "Bajo.mp3"), session()]}, **auth)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["added"], ["Bajo.mp3"])
        self.assertEqual(r.json()["attachments"], ["cancion.cpr"])
        detail = self.client.get("/api/works/estudio/", **auth).json()
        self.assertEqual(len(detail["parts"]), 1)
        self.assertTrue(detail["parts"][0]["sha256"])
        r = self.client.post("/api/works/estudio/stems/", {"stems": [tone("tone.mp3", "Bajo.mp3")]}, **auth)
        self.assertEqual(r.json()["unchanged"], ["Bajo.mp3"])

    def test_converted_formats_are_recognised_on_the_next_push(self):
        auth = self.token("autora")
        self.client.post("/api/works/estudio/stems/", {"stems": [tone("tone.ogg", "nota de voz.m4a")]}, **auth)
        r = self.client.post("/api/works/estudio/stems/", {"stems": [tone("tone.ogg", "nota de voz.m4a")]}, **auth)
        self.assertEqual(r.json()["unchanged"], ["nota de voz.m4a"])

    def test_members_need_the_agreement_and_strangers_cannot_push(self):
        auth = self.token("miembro")
        r = self.client.post("/api/works/estudio/stems/", {"stems": [tone()]}, **auth)
        self.assertEqual(r.status_code, 400)
        r = self.client.post("/api/works/estudio/stems/", {"stems": [tone()], "accept_terms": "1"}, **auth)
        self.assertEqual(r.json()["added"], ["tone.mp3"])
        self.assertEqual(self.work.contributions.filter(status="versioned").count(), 1)
        auth = self.token("otro")
        self.assertEqual(self.client.post("/api/works/estudio/stems/", {"stems": [tone()]}, **auth).status_code, 404)

    def test_versions_only_by_the_owner(self):
        auth = self.token("miembro")
        self.assertEqual(self.client.post("/api/works/estudio/versions/", {"message": "x"}, **auth).status_code, 403)
        auth = self.token("autora")
        r = self.client.post("/api/works/estudio/versions/", json.dumps({"message": "Bajo nuevo"}),
                             content_type="application/json", **auth)
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json()["number"], 1)
