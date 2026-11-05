"""Hosted HTTP boundary: never parse uploads or reach providers before authorization."""
import importlib
import os
import secrets
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient


class HostedSecurityTests(unittest.TestCase):
    def setUp(self):
        # No media dependencies or external providers in HTTP boundary tests.
        self.app_module = importlib.import_module("app")
        self.env = patch.dict(os.environ, {
            "GENJUSTSU_HOSTED": "1", "GENJUSTSU_DEMO": "0",
            "GENJUSTSU_PASSWORD": "", "RAILWAY_ENVIRONMENT_ID": "",
        })
        self.env.start()
        self.password = secrets.token_urlsafe(32)
        self.client = TestClient(self.app_module.app)

    def tearDown(self):
        self.client.close()
        self.env.stop()

    def test_missing_password_fails_closed_for_every_private_route(self):
        for method, path in [
            ("POST", "/jobs"), ("GET", "/jobs/abc"), ("HEAD", "/runs/abc/file"),
            ("GET", "/runs/abc/file"), ("POST", "/jobs/abc/seedance"),
            ("POST", "/jobs/abc/finish"), ("POST", "/jobs/abc/hd"),
            ("POST", "/jobs/abc/mask-review"), ("GET", "/docs"),
            ("GET", "/openapi.json"), ("GET", "/redoc"),
        ]:
            with self.subTest(method=method, path=path):
                response = self.client.request(method, path)
                self.assertEqual(response.status_code, 503)
        self.assertEqual(self.app_module.jobs, {})

    def test_public_ui_health_and_static_are_available(self):
        for path in ["/", "/health", "/capabilities", "/static/companions/video.webp"]:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)

    def test_authentication_required_and_wrong_credentials_rejected(self):
        os.environ["GENJUSTSU_PASSWORD"] = self.password
        for auth in [None, ("genjustsu", secrets.token_urlsafe(32)), ("wrong", self.password)]:
            response = self.client.get("/jobs/missing", auth=auth)
            self.assertEqual(response.status_code, 401)
            self.assertIn("Basic", response.headers["www-authenticate"])

    def test_correct_credentials_reach_private_route_and_form_validation(self):
        os.environ["GENJUSTSU_PASSWORD"] = self.password
        auth = ("genjustsu", self.password)
        self.assertEqual(self.client.get("/jobs/missing", auth=auth).status_code, 404)
        self.assertEqual(self.client.post("/jobs", auth=auth).status_code, 422)

    def test_artifacts_require_auth_even_when_the_file_exists(self):
        with tempfile.TemporaryDirectory(dir=self.app_module.RUNS) as d:
            folder = Path(d)
            (folder / "private.txt").write_text("private media metadata")
            path = f"/runs/{folder.name}/private.txt"
            os.environ["GENJUSTSU_PASSWORD"] = self.password
            self.assertEqual(self.client.get(path).status_code, 401)
            response = self.client.get(path, auth=("genjustsu", self.password))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.text, "private media metadata")

    def test_demo_blocks_mutations_and_artifacts_even_with_auth(self):
        os.environ.update(GENJUSTSU_DEMO="1", GENJUSTSU_PASSWORD=self.password)
        auth = ("genjustsu", self.password)
        for method, path in [("POST", "/jobs"), ("POST", "/jobs/abc/hd"),
                             ("GET", "/jobs/abc"), ("GET", "/runs/abc/file")]:
            self.assertEqual(self.client.request(method, path, auth=auth).status_code, 403)
        self.assertEqual(self.app_module.jobs, {})
        self.assertFalse(self.client.get("/capabilities").json()["workflow_enabled"])

    def test_railway_detection_cannot_be_disabled_by_hosted_zero(self):
        os.environ.update(GENJUSTSU_HOSTED="0", RAILWAY_ENVIRONMENT_ID="test")
        self.assertEqual(self.client.post("/jobs").status_code, 503)

    def test_local_default_preserves_existing_behavior(self):
        os.environ.update(GENJUSTSU_HOSTED="0", RAILWAY_ENVIRONMENT_ID="")
        self.assertEqual(self.client.post("/jobs").status_code, 422)

    def test_hosted_startup_does_not_resume_saved_provider_requests(self):
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d) / ("a" * 32)
            folder.mkdir()
            (folder / "seedance-response.json").write_text('{"requestId":"saved-request"}')
            bridge = Mock()
            with patch.object(self.app_module, "RUNS", Path(d)), patch.dict(
                sys.modules, {"seedance_bridge": bridge}
            ), patch.object(self.app_module.threading, "Thread") as thread:
                self.app_module.resume_saved_generations()
                bridge.wait_and_finish.assert_not_called()
                thread.assert_not_called()

    def test_encoded_and_trailing_slash_private_paths_are_guarded(self):
        for path in ["/jobs/", "/%6aobs", "/runs%2Fprivate/file", "/docs/"]:
            self.assertEqual(self.client.get(path).status_code, 503)

    def test_malformed_basic_auth_is_rejected_not_a_server_error(self):
        os.environ["GENJUSTSU_PASSWORD"] = self.password
        response = self.client.get("/jobs/missing", headers={"Authorization": "Basic !"})
        self.assertEqual(response.status_code, 401)

