"""Release boundary tests. No external service is contacted."""

import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import site_release as release


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.target = self.root / "release"
        self.source = self.root / "site"
        self.source.mkdir()
        (self.source / "index.html").write_text("<title>Test</title>")
        self.sha = "a" * 40
        self.root_patch = patch.object(release, "ROOT", self.root)
        self.root_patch.start()
        self.addCleanup(self.root_patch.stop)

    def packaged(self):
        release.package("open-world-clock", self.sha, self.target)

    def test_content_mutation_extra_files_and_wrong_commit_are_rejected(self):
        self.packaged()
        release.verify("open-world-clock", self.sha, self.target)
        with self.assertRaisesRegex(RuntimeError, "provenance"):
            release.verify("open-world-clock", "b" * 40, self.target)
        extra = self.target / "site/extra.txt"
        extra.write_text("unexpected")
        with self.assertRaisesRegex(RuntimeError, "contents"):
            release.verify("open-world-clock", self.sha, self.target)
        extra.unlink()
        (self.target / "site/index.html").write_text("changed")
        with self.assertRaisesRegex(RuntimeError, "contents"):
            release.verify("open-world-clock", self.sha, self.target)

    def test_packaging_rejects_overlap_and_overwrites(self):
        with self.assertRaisesRegex(RuntimeError, "inside source"):
            release.package("open-world-clock", self.sha, self.source / "nested")
        self.packaged()
        with self.assertRaisesRegex(RuntimeError, "fresh"):
            self.packaged()

    def test_main_check_rejects_pull_requests_and_stale_commits(self):
        env = {
            "GITHUB_REF": "refs/pull/1/merge",
            "GITHUB_REPOSITORY": "joaoCarvalho1000/open-world-clock",
            "GH_TOKEN": "fixture",
        }
        with patch.dict(os.environ, env), self.assertRaisesRegex(RuntimeError, "only accepts main"):
            release.latest_main("open-world-clock", self.sha)
        env["GITHUB_REF"] = "refs/heads/main"
        with (
            patch.dict(os.environ, env),
            patch.object(
                release,
                "urlopen",
                return_value=io.BytesIO(json.dumps({"object": {"sha": "b" * 40}}).encode()),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "stale"):
                release.latest_main("open-world-clock", self.sha)

    def test_failed_smoke_rolls_back_only_our_deployment(self):
        self.packaged()
        before, after = {"id": "before"}, {"id": "after"}
        with (
            patch.object(release, "latest_main"),
            patch.object(release, "wrangler"),
            patch.object(release, "current", side_effect=[before, before, after, after]),
            patch.object(release, "smoke", side_effect=RuntimeError("unhealthy")),
            patch.object(release.time, "sleep"),
            patch.object(release, "rollback") as rollback,
        ):
            with self.assertRaisesRegex(RuntimeError, "unhealthy"):
                release.deploy("open-world-clock", self.sha, self.target)
            rollback.assert_called_once_with("open-world-clock", before)
        self.assertEqual(
            json.loads((self.target / "deployment.json").read_text())["state"], "rolled_back"
        )

    def test_new_external_deployment_is_never_rolled_back(self):
        self.packaged()
        with (
            patch.object(release, "latest_main"),
            patch.object(release, "wrangler"),
            patch.object(
                release,
                "current",
                side_effect=[
                    {"id": "before"},
                    {"id": "before"},
                    {"id": "ours"},
                    {"id": "someone-else"},
                ],
            ),
            patch.object(release, "smoke", side_effect=RuntimeError("unhealthy")),
            patch.object(release.time, "sleep"),
            patch.object(release, "rollback") as rollback,
        ):
            with self.assertRaises(RuntimeError):
                release.deploy("open-world-clock", self.sha, self.target)
            rollback.assert_not_called()
        self.assertEqual(
            json.loads((self.target / "deployment.json").read_text())["state"],
            "needs_reconciliation",
        )

    def test_missing_page_and_wrong_marker_fail_smoke(self):
        with patch.object(release, "get", return_value=(200, {}, b'{"sha":"wrong"}')):
            with self.assertRaisesRegex(RuntimeError, "marker"):
                release.smoke("open-world-clock", self.sha, self.target)
        marker = json.dumps({"repository": "open-world-clock", "sha": self.sha}).encode()
        with patch.object(release, "get", side_effect=[(200, {}, marker), (404, {}, b"missing")]):
            with self.assertRaisesRegex(RuntimeError, "Page failed"):
                release.smoke("open-world-clock", self.sha, self.target)

    def test_deployment_evidence_excludes_cloudflare_environment_values(self):
        remote = {
            "canonical_deployment": {
                "id": "abc",
                "env_vars": {"PRIVATE": "secret"},
                "deployment_trigger": {"metadata": {"commit_hash": self.sha}},
            }
        }
        with patch.object(release, "api", return_value=remote):
            self.assertEqual(release.current("open-world-clock"), {"id": "abc", "commit": self.sha})


if __name__ == "__main__":
    unittest.main()
