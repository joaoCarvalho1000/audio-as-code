"""Package, deploy and verify a tested website. Credentials are environment-only."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
ACCOUNT = "52b57879a0260045efcd7a51b2bbdfdb"
SITES = {
    "audio-as-code": ("audioascode.com", "web/cloudflare", "output/site"),
    "open-world-clock": ("openworldclock.com", "cloudflare", "site"),
}


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
    with urlopen(request, timeout=60) as response:
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
    with urlopen(request, timeout=30) as response:
        require(
            json.load(response)["object"]["sha"] == sha,
            "A newer main commit exists; refusing stale deployment",
        )


def wrangler(kind, *args):
    executable = ROOT / SITES[kind][1] / "node_modules/wrangler/bin/wrangler.js"
    subprocess.run(
        ["node", str(executable), *map(str, args)], cwd=ROOT / SITES[kind][1], check=True
    )


def prepare(kind, sha, target):
    verify(kind, sha, target)
    if kind == "audio-as-code":
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
            return response.status, response.headers, response.read()
    except HTTPError as error:
        return error.code, error.headers, error.read()


def smoke(kind, sha, target):
    origin = "https://" + SITES[kind][0]
    status, _, data = get(origin + "/release.json?commit=" + sha)
    require(
        status == 200 and json.loads(data) == {"repository": kind, "sha": sha},
        "Production commit marker differs",
    )
    routes = (
        ["/", "/source", "/instruments", "/electronic"]
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
    record = {"repository": kind, "sha": sha, "previous": before, "state": "prepared"}
    record_path = target / "deployment.json"
    write_json(record_path, record)
    if kind == "audio-as-code":
        report = json.loads((target / "stage/staging-report.json").read_text(encoding="utf-8"))
        for entry in report["large_files"]:
            source = target / "site" / entry["site_path"]
            require(digest(source) == entry["sha256"], "Media changed after staging")
            wrangler(
                kind,
                "r2",
                "object",
                "put",
                report["bucket"] + "/" + entry["key"],
                "--file",
                source,
                "--content-type",
                entry["content_type"],
                "--remote",
                "--config",
                target / "stage/wrangler.jsonc",
            )
    latest_main(kind, sha)  # Uploads can take time; check again before replacing production.
    require(
        current(kind)["id"] == before["id"],
        "Production changed outside this release; refusing to overwrite it",
    )
    try:
        if kind == "audio-as-code":
            wrangler(
                kind,
                "deploy",
                "--config",
                target / "stage/wrangler.jsonc",
                "--message",
                "GitHub " + sha,
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
            )
        after = current(kind)
        require(after["id"] != before["id"], "No new production deployment was observed")
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
        # Never undo a newer deployment made outside this serialized workflow.
        now = current(kind)
        if record.get("deployed", {}).get("id") == now["id"]:
            rollback(kind, before)
            record["state"] = "rolled_back"
        else:
            record["state"] = "needs_reconciliation"
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
