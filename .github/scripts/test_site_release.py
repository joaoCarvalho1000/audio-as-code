"""Release boundary tests. No external service is contacted."""

import base64
import hashlib
import io
import json
import os
import subprocess
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
        self.ownership_patch = patch.object(release, "owns_deployment", return_value=True)
        self.ownership_patch.start()
        self.addCleanup(self.ownership_patch.stop)

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
                "api_urlopen",
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

    def test_unproven_deployment_is_not_rolled_back(self):
        self.packaged()
        with (
            patch.object(release, "latest_main"),
            patch.object(release, "wrangler"),
            patch.object(release, "owns_deployment", return_value=False),
            patch.object(
                release,
                "current",
                side_effect=[
                    {"id": "before"},
                    {"id": "before"},
                    {"id": "external"},
                    {"id": "external"},
                ],
            ),
            patch.object(release, "rollback") as rollback,
            patch.object(release, "smoke") as smoke,
        ):
            with self.assertRaisesRegex(RuntimeError, "not proven"):
                release.deploy("open-world-clock", self.sha, self.target)
            rollback.assert_not_called()
            smoke.assert_not_called()
        self.assertEqual(
            json.loads((self.target / "deployment.json").read_text())["state"],
            "needs_reconciliation",
        )

    def test_failure_during_recovery_preserves_evidence_and_original_error(self):
        for failure, state in [("status", "needs_reconciliation"), ("rollback", "rollback_failed")]:
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as temp:
                target = Path(temp) / "release"
                release.package("open-world-clock", self.sha, target)
                observations = [{"id": "before"}, {"id": "before"}, {"id": "ours"}]
                observations.append(
                    OSError("sensitive response") if failure == "status" else {"id": "ours"}
                )
                with (
                    patch.object(release, "latest_main"),
                    patch.object(release, "wrangler"),
                    patch.object(release, "current", side_effect=observations),
                    patch.object(release, "smoke", side_effect=RuntimeError("unhealthy")),
                    patch.object(release.time, "sleep"),
                    patch.object(release, "rollback", side_effect=OSError("sensitive response")),
                ):
                    with self.assertRaisesRegex(RuntimeError, "unhealthy"):
                        release.deploy("open-world-clock", self.sha, target)
                evidence = (target / "deployment.json").read_text()
                self.assertEqual(json.loads(evidence)["state"], state)
                self.assertNotIn("sensitive response", evidence)

    def test_publish_failure_requires_reconciliation_without_blind_rollback(self):
        self.packaged()
        with (
            patch.object(release, "latest_main"),
            patch.object(release, "wrangler", side_effect=OSError("connection lost")),
            patch.object(release, "current", return_value={"id": "before"}),
            patch.object(release, "rollback") as rollback,
        ):
            with self.assertRaisesRegex(OSError, "connection lost"):
                release.deploy("open-world-clock", self.sha, self.target)
            rollback.assert_not_called()
        self.assertEqual(
            json.loads((self.target / "deployment.json").read_text())["state"],
            "needs_reconciliation",
        )

    def test_ownership_requires_unique_invocation_marker_and_commit(self):
        self.ownership_patch.stop()
        marker = "unique-release-marker"
        with patch.object(
            release,
            "api",
            return_value={
                "deployment_trigger": {
                    "metadata": {
                        "commit_hash": self.sha,
                        "commit_message": marker,
                    }
                }
            },
        ):
            self.assertTrue(
                release.owns_deployment("open-world-clock", {"id": "ours"}, self.sha, marker)
            )
            self.assertFalse(
                release.owns_deployment("open-world-clock", {"id": "ours"}, "b" * 40, marker)
            )
            self.assertFalse(
                release.owns_deployment("open-world-clock", {"id": "ours"}, self.sha, "other")
            )
        deployed = {"versions": [{"version_id": "our-version", "percentage": 100}]}
        with patch.object(
            release, "api", return_value={"annotations": {"workers/message": marker}}
        ):
            self.assertTrue(release.owns_deployment("audio-as-code", deployed, self.sha, marker))
            self.assertFalse(release.owns_deployment("audio-as-code", deployed, self.sha, "other"))
            deployed["versions"][0]["percentage"] = 50
            self.assertFalse(release.owns_deployment("audio-as-code", deployed, self.sha, marker))

    def test_verified_release_records_owned_deployment(self):
        self.packaged()
        with (
            patch.object(release, "latest_main"),
            patch.object(release, "wrangler") as wrangler,
            patch.object(
                release, "current", side_effect=[{"id": "before"}, {"id": "before"}, {"id": "ours"}]
            ),
            patch.object(release, "smoke"),
        ):
            release.deploy("open-world-clock", self.sha, self.target)
        record = json.loads((self.target / "deployment.json").read_text())
        self.assertEqual(record["state"], "verified")
        self.assertIn(record["marker"], wrangler.call_args.args)
        self.assertIn("--no-bundle", wrangler.call_args.args)

    def test_missing_page_and_wrong_marker_fail_smoke(self):
        with patch.object(release, "get", return_value=(200, {}, b'{"sha":"wrong"}')):
            with self.assertRaisesRegex(RuntimeError, "marker"):
                release.smoke("open-world-clock", self.sha, self.target)
        marker = json.dumps({"repository": "open-world-clock", "sha": self.sha}).encode()
        with patch.object(release, "get", side_effect=[(200, {}, marker), (404, {}, b"missing")]):
            with self.assertRaisesRegex(RuntimeError, "Page failed"):
                release.smoke("open-world-clock", self.sha, self.target)

    def test_authenticated_redirects_cannot_forward_credentials(self):
        handler = release.NoCredentialRedirect()
        with self.assertRaisesRegex(RuntimeError, "redirects are refused"):
            handler.redirect_request(None, None, 302, "Found", {}, "https://attacker.example/")

    def test_wrangler_does_not_inherit_github_credentials(self):
        with (
            patch.dict(os.environ, {"GH_TOKEN": "not-for-wrangler"}),
            patch.object(release.subprocess, "run") as run,
        ):
            release.wrangler("open-world-clock", "--version")
        self.assertNotIn("GH_TOKEN", run.call_args.kwargs["env"])

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

    def test_r2_s3_credentials_use_the_existing_token_without_inherited_credentials(self):
        original = {
            "CLOUDFLARE_API_TOKEN": "bucket-scoped-fixture",
            "CLOUDFLARE_API_KEY": "unrelated",
            "GH_TOKEN": "owner-token",
            "GITHUB_TOKEN": "workflow-token",
            "AWS_SESSION_TOKEN": "old-session",
            "AWS_PROFILE": "unrelated-profile",
            "AWS_ENDPOINT_URL": "https://untrusted.example",
        }
        with (
            patch.dict(os.environ, original),
            patch.object(release, "api", return_value={"id": "b" * 32, "status": "active"}) as api,
        ):
            environment = release.r2_environment()
            self.assertEqual(os.environ["AWS_SESSION_TOKEN"], "old-session")
        api.assert_called_once_with("/tokens/verify")
        for key in original:
            self.assertNotIn(key, environment)
        self.assertEqual(environment["AWS_ACCESS_KEY_ID"], "b" * 32)
        self.assertEqual(
            environment["AWS_SECRET_ACCESS_KEY"],
            hashlib.sha256(b"bucket-scoped-fixture").hexdigest(),
        )
        self.assertEqual(environment["AWS_CONFIG_FILE"], os.devnull)
        self.assertEqual(environment["AWS_SHARED_CREDENTIALS_FILE"], os.devnull)

    def test_r2_rejects_inactive_tokens_and_invalid_ids(self):
        for token in ({"status": "disabled", "id": "b" * 32}, {"status": "active", "id": None}):
            with patch.object(release, "api", return_value=token), self.assertRaises(RuntimeError):
                release.r2_environment()

    def test_s3_upload_has_fixed_endpoint_integrity_header_and_no_credentials_in_argv(self):
        source = self.source / "audio file.wav"
        source.write_bytes(b"procedural-audio")
        entry = {"key": "sha256/hash/audio.wav", "content_type": "audio/wav"}
        environment = {"AWS_SECRET_ACCESS_KEY": "private-fixture"}
        with patch.object(
            release.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)
        ) as run:
            release.upload_r2("audioascode-media", entry, source, environment)
        command = run.call_args.args[0]
        self.assertEqual(command[:3], ["aws", "s3api", "put-object"])
        self.assertEqual(
            command[command.index("--endpoint-url") + 1],
            f"https://{release.ACCOUNT}.r2.cloudflarestorage.com",
        )
        self.assertEqual(command[command.index("--body") + 1], str(source))
        self.assertEqual(command[command.index("--bucket") + 1], "audioascode-media")
        self.assertEqual(
            command[command.index("--content-md5") + 1],
            base64.b64encode(
                hashlib.md5(source.read_bytes(), usedforsecurity=False).digest()
            ).decode(),
        )
        self.assertNotIn("private-fixture", command)
        self.assertIs(run.call_args.kwargs["env"], environment)
        with (
            patch.object(
                release.subprocess,
                "run",
                return_value=subprocess.CompletedProcess([], 1, stderr=b"private-fixture"),
            ),
            self.assertRaisesRegex(RuntimeError, "S3 upload failed") as error,
        ):
            release.upload_r2("audioascode-media", entry, source, environment)
        self.assertNotIn("private-fixture", str(error.exception))

    def test_failed_media_upload_never_starts_worker_publication(self):
        with patch.dict(
            release.SITES, {"audio-as-code": ("audioascode.com", "web/cloudflare", "site")}
        ):
            release.package("audio-as-code", self.sha, self.target)
        source = self.target / "site/index.html"
        release.write_json(
            self.target / "stage/staging-report.json",
            {
                "bucket": "audioascode-media",
                "large_files": [{"site_path": "index.html", "sha256": release.digest(source)}],
            },
        )
        with (
            patch.object(release, "latest_main"),
            patch.object(release, "current", return_value={"id": "original"}),
            patch.object(release, "r2_environment", return_value={}),
            patch.object(release, "upload_r2", side_effect=RuntimeError("upload rejected")),
            patch.object(release, "wrangler") as wrangler,
            patch.object(release, "rollback") as rollback,
            self.assertRaisesRegex(RuntimeError, "upload rejected"),
        ):
            release.deploy("audio-as-code", self.sha, self.target)
        wrangler.assert_not_called()
        rollback.assert_not_called()
        self.assertEqual(
            json.loads((self.target / "deployment.json").read_text())["state"], "upload_failed"
        )


if __name__ == "__main__":
    unittest.main()
