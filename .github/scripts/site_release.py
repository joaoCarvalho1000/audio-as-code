"""Package, deploy and verify a tested website. Credentials are environment-only."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request, build_opener, urlopen

ROOT = Path(__file__).resolve().parents[2]
ACCOUNT = "52b57879a0260045efcd7a51b2bbdfdb"
SITES = {
    "audio-as-code": ("audioascode.com", "web/cloudflare", "output/site"),
    "open-world-clock": ("openworldclock.com", "cloudflare", "site"),
}


class NoCredentialRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RuntimeError("Authenticated API redirects are refused")


api_urlopen = build_opener(NoCredentialRedirect()).open


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def digest(path):
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def files(directory):
    paths = list(directory.rglob("*"))
    require(not any(p.is_symlink() for p in paths), "Symlinks are not release inputs")
    return {p.relative_to(directory).as_posix(): digest(p) for p in paths if p.is_file()}


def package(kind, sha, target):
    require(re.fullmatch(r"[a-f0-9]{40}", sha), "Expected a full commit SHA")
    source = ROOT / SITES[kind][2]
    target = target.resolve()
    require(not target.exists(), "Choose a fresh release directory")
    require(not target.is_relative_to(source.resolve()), "Release cannot be inside source")
    require((source / "index.html").is_file(), "Website build is missing")
    files(source)  # Reject symlinks before copytree follows them.
    shutil.copytree(source, target / "site")
    write_json(target / "site/release.json", {"repository": kind, "sha": sha})
    write_json(
        target / "manifest.json", {"repository": kind, "sha": sha, "files": files(target / "site")}
    )
    verify(kind, sha, target)


def verify(kind, sha, target):
    manifest = json.loads((target / "manifest.json").read_text(encoding="utf-8"))
    require(manifest["sha"] == sha and manifest["repository"] == kind, "Wrong release provenance")
    require(
        manifest["files"] == files(target / "site"), "Release contents differ from tested artifact"
    )
    require(
        json.loads((target / "site/release.json").read_text(encoding="utf-8"))
        == {"repository": kind, "sha": sha},
        "Wrong public release marker",
    )


def api(path, data=None):
    request = Request(
        "https://api.cloudflare.com/client/v4/accounts/" + ACCOUNT + path,
        data=None if data is None else json.dumps(data).encode(),
        headers={
            "Authorization": "Bearer " + os.environ["CLOUDFLARE_API_TOKEN"],
            "Content-Type": "application/json",
        },
        method="GET" if data is None else "POST",
    )
    with api_urlopen(request, timeout=60) as response:
        result = json.load(response)
    require(result.get("success"), "Cloudflare API did not report success")
    return result["result"]


def current(kind):
    if kind == "audio-as-code":
        deployed = api("/workers/scripts/audioascode/deployments")["deployments"][0]
        return {"id": deployed["id"], "versions": deployed["versions"]}
    deployed = api("/pages/projects/open-world-clock")["canonical_deployment"]
    return {
        "id": deployed["id"],
        "commit": deployed["deployment_trigger"]["metadata"].get("commit_hash"),
    }


def owns_deployment(kind, deployed, sha, marker):
    """Match this invocation, not just whichever deployment became current last."""
    if kind == "audio-as-code":
        versions = deployed["versions"]
        if len(versions) != 1 or versions[0].get("percentage") != 100:
            return False
        version = api("/workers/scripts/audioascode/versions/" + versions[0]["version_id"])
        return version.get("annotations", {}).get("workers/message") == marker
    metadata = api("/pages/projects/open-world-clock/deployments/" + deployed["id"])[
        "deployment_trigger"
    ]["metadata"]
    return metadata.get("commit_hash") == sha and metadata.get("commit_message") == marker


def latest_main(kind, sha):
    require(os.environ.get("GITHUB_REF") == "refs/heads/main", "Production only accepts main")
    require(
        os.environ.get("GITHUB_REPOSITORY") == "joaoCarvalho1000/" + kind, "Unexpected repository"
    )
    request = Request(
        f"https://api.github.com/repos/joaoCarvalho1000/{kind}/git/ref/heads/main",
        headers={
            "Authorization": "Bearer " + os.environ["GH_TOKEN"],
            "User-Agent": "website-release",
            "Accept": "application/vnd.github+json",
        },
    )
    with api_urlopen(request, timeout=30) as response:
        require(
            json.load(response)["object"]["sha"] == sha,
            "A newer main commit exists; refusing stale deployment",
        )


def wrangler(kind, *args):
    executable = ROOT / SITES[kind][1] / "node_modules/wrangler/bin/wrangler.js"
    child_env = dict(os.environ)
    child_env.pop("GH_TOKEN", None)
    child_env.pop("GITHUB_TOKEN", None)
    subprocess.run(
        ["node", str(executable), *map(str, args)],
        cwd=ROOT / SITES[kind][1],
        check=True,
        env=child_env,
    )


def r2_environment():
    """Derive S3 credentials for the existing bucket-scoped account token."""
    token = api("/tokens/verify")
    require(token.get("status") == "active", "R2 account token is not active")
    token_id = token.get("id")
    require(
        isinstance(token_id, str) and re.fullmatch(r"[a-f0-9]{32}", token_id),
        "Invalid R2 token ID",
    )
    child_env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("AWS_", "CLOUDFLARE_")) and key not in {"GH_TOKEN", "GITHUB_TOKEN"}
    }
    child_env.update(
        AWS_ACCESS_KEY_ID=token["id"],
        AWS_SECRET_ACCESS_KEY=hashlib.sha256(
            os.environ["CLOUDFLARE_API_TOKEN"].encode()
        ).hexdigest(),
        AWS_CONFIG_FILE=os.devnull,
        AWS_SHARED_CREDENTIALS_FILE=os.devnull,
        AWS_EC2_METADATA_DISABLED="true",
        AWS_CLI_AUTO_PROMPT="off",
        AWS_PAGER="",
        # R2 accepts Content-MD5; do not add the CLI's optional CRC64 checksum.
        AWS_REQUEST_CHECKSUM_CALCULATION="when_required",
        AWS_RESPONSE_CHECKSUM_VALIDATION="when_required",
    )
    return child_env


def upload_r2(bucket, entry, source, environment):
    """Use S3: bucket object permissions are not accepted by the REST uploader."""
    checksum = hashlib.md5(usedforsecurity=False)
    with source.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            checksum.update(block)
    try:
        result = subprocess.run(
            [
                "aws",
                "s3api",
                "put-object",
                "--endpoint-url",
                f"https://{ACCOUNT}.r2.cloudflarestorage.com",
                "--region",
                "auto",
                "--bucket",
                bucket,
                "--key",
                entry["key"],
                "--body",
                str(source),
                "--content-type",
                entry["content_type"],
                "--content-md5",
                base64.b64encode(checksum.digest()).decode("ascii"),
            ],
            env=environment,
            capture_output=True,
            timeout=300,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise RuntimeError(
            "R2 S3 upload could not complete; Worker publication was not started"
        ) from None
    require(result.returncode == 0, "R2 S3 upload failed; Worker publication was not started")


def prepare(kind, sha, target):
    verify(kind, sha, target)
    if kind == "audio-as-code":
        # Provided by the GitHub Ubuntu runner; fail before exposing credentials.
        subprocess.run(["aws", "--version"], check=True)
        subprocess.run(
            [
                sys.executable,
                str(ROOT / "examples/prepare_cloudflare.py"),
                "--site",
                str(target / "site"),
                "--output",
                str(target / "stage"),
                "--account-id",
                ACCOUNT,
                "--name",
                "audioascode",
                "--bucket",
                "audioascode-media",
                "--domain",
                "audioascode.com",
                "--domain",
                "www.audioascode.com",
            ],
            check=True,
            stdout=subprocess.DEVNULL,
        )
        wrangler(kind, "deploy", "--config", target / "stage/wrangler.jsonc", "--dry-run")
    else:
        wrangler(
            kind,
            "pages",
            "functions",
            "build",
            "functions",
            "--outfile",
            target / "site/_worker.js",
        )
        # Compiled Functions are produced without deployment credentials from this same commit.
        write_json(
            target / "manifest.json",
            {"repository": kind, "sha": sha, "files": files(target / "site")},
        )


def get(url, *, headers=None, method="GET"):
    request = Request(
        url,
        method=method,
        headers={
            "User-Agent": "WebsiteReleaseCheck/1.0",
            "Cache-Control": "no-cache",
            **(headers or {}),
        },
    )
    try:
        with urlopen(request, timeout=45) as response:
            body = response.read(1024 * 1024 + 1)
            require(len(body) <= 1024 * 1024, "Unexpectedly large smoke-test response")
            return response.status, response.headers, body
    except HTTPError as error:
        return error.code, error.headers, error.read(1024 * 1024)


def smoke(kind, sha, target):
    origin = "https://" + SITES[kind][0]
    status, _, data = get(origin + "/release.json?commit=" + sha)
    require(
        status == 200 and json.loads(data) == {"repository": kind, "sha": sha},
        "Production commit marker differs",
    )
    routes = (
        ["/", "/source", "/instruments/", "/electronic/"]
        if kind == "audio-as-code"
        else [
            "/",
            "/meeting-planner",
            "/london-to-new-york-time",
            "/world-time-now",
            "/utc-time",
            "/pt/",
            "/es/",
        ]
    )
    for route in routes:
        status, headers, data = get(origin + route)
        require(
            status == 200 and "text/html" in headers.get("Content-Type", ""),
            "Page failed: " + route,
        )
        require(b"<title>" in data and origin.encode() in data, "Invalid HTML: " + route)
        require(b"cloudflareinsights" not in data, "Unexpected Cloudflare analytics injection")
    for route, content in [
        ("/robots.txt", b"Sitemap:"),
        ("/sitemap.xml", origin.encode()),
        ("/llms.txt", b"#"),
    ]:
        status, _, data = get(origin + route)
        require(status == 200 and content in data, "Discovery endpoint failed: " + route)
    status, _, _ = get(origin + "/__release_missing_" + sha)
    require(status == 404, "Missing routes must return 404")
    if kind == "audio-as-code":
        report = json.loads((target / "stage/staging-report.json").read_text(encoding="utf-8"))
        for entry in report["large_files"]:
            url = origin + "/" + entry["site_path"]
            status, headers, _ = get(url, method="HEAD")
            require(
                status == 200 and int(headers.get("Content-Length", 0)) == entry["bytes"],
                "Media size differs",
            )
            etag = headers.get("ETag")
            status, _, data = get(url, headers={"Range": "bytes=0-63"})
            with (target / "site" / entry["site_path"]).open("rb") as source:
                require(status == 206 and data == source.read(64), "Media range differs")
            require(bool(etag), "Media ETag missing")
            require(get(url, headers={"If-None-Match": etag})[0] == 304, "Media validation failed")


def rollback(kind, previous):
    if kind == "audio-as-code":
        api(
            "/workers/scripts/audioascode/deployments",
            {
                "strategy": "percentage",
                "versions": previous["versions"],
                "annotations": {
                    "workers/message": "Automatic rollback after failed website verification"
                },
            },
        )
    else:
        api("/pages/projects/open-world-clock/deployments/" + previous["id"] + "/rollback", {})
    restored = current(kind)
    key = "versions" if kind == "audio-as-code" else "id"
    require(restored[key] == previous[key], "Rollback was not confirmed by Cloudflare")


def deploy(kind, sha, target):
    verify(kind, sha, target)
    latest_main(kind, sha)
    before = current(kind)
    marker = "GitHub " + sha + " release " + uuid.uuid4().hex
    record = {
        "repository": kind,
        "sha": sha,
        "previous": before,
        "state": "prepared",
        "marker": marker,
    }
    record_path = target / "deployment.json"
    write_json(record_path, record)
    if kind == "audio-as-code":
        report = json.loads((target / "stage/staging-report.json").read_text(encoding="utf-8"))
        record["state"] = "uploading"
        write_json(record_path, record)
        try:
            environment = r2_environment() if report["large_files"] else None
            for entry in report["large_files"]:
                source = target / "site" / entry["site_path"]
                require(digest(source) == entry["sha256"], "Media changed after staging")
                upload_r2(report["bucket"], entry, source, environment)
        except Exception:
            # Uploads use content-addressed keys. The production Worker is untouched.
            record["state"] = "upload_failed"
            write_json(record_path, record)
            raise
        record["state"] = "uploaded"
        write_json(record_path, record)
    latest_main(kind, sha)  # Uploads can take time; check again before replacing production.
    require(
        current(kind)["id"] == before["id"],
        "Production changed outside this release; refusing to overwrite it",
    )
    try:
        record["state"] = "publishing"
        write_json(record_path, record)
        if kind == "audio-as-code":
            wrangler(
                kind,
                "deploy",
                "--config",
                target / "stage/wrangler.jsonc",
                "--message",
                marker,
            )
        else:
            wrangler(
                kind,
                "pages",
                "deploy",
                target / "site",
                "--project-name",
                "open-world-clock",
                "--branch",
                "main",
                "--commit-hash",
                sha,
                "--commit-dirty=false",
                "--commit-message",
                marker,
                "--no-bundle",
            )
        after = current(kind)
        require(after["id"] != before["id"], "No new production deployment was observed")
        require(
            owns_deployment(kind, after, sha, marker),
            "Observed deployment is not proven to belong to this release",
        )
        record.update(state="deployed", deployed=after)
        write_json(record_path, record)
        for attempt in range(6):
            try:
                smoke(kind, sha, target)
                break
            except (RuntimeError, OSError, ValueError):
                if attempt == 5:
                    raise
                time.sleep(10)
        record["state"] = "verified"
        write_json(record_path, record)
    except Exception:
        # Record uncertainty before another network request can fail. Never save
        # raw exceptions: response bodies and subprocess errors may contain secrets.
        record["state"] = "needs_reconciliation"
        write_json(record_path, record)
        try:
            now = current(kind)
            if record.get("deployed", {}).get("id") == now["id"]:
                # This check is not an atomic lock against outside deployers.
                record["state"] = "rolling_back"
                write_json(record_path, record)
                rollback(kind, before)
                record["state"] = "rolled_back"
        except Exception:
            if record["state"] == "rolling_back":
                record["state"] = "rollback_failed"
        write_json(record_path, record)
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["package", "verify", "prepare", "deploy", "smoke"])
    parser.add_argument("--site", choices=SITES, required=True)
    parser.add_argument("--sha", required=True)
    parser.add_argument("--directory", type=Path, required=True)
    args = parser.parse_args()
    globals()[args.command](args.site, args.sha, args.directory.resolve())
