"""Stage the verified website for Workers + R2; never publishes or deletes files."""

from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSET_LIMIT = 25 * 1024 * 1024


def prepare(
    site: Path,
    output: Path,
    *,
    account_id: str,
    name: str = "audioascode",
    bucket: str = "audioascode-media",
    domains: tuple[str, ...] = (),
) -> dict:
    site, output = site.resolve(), output.resolve()
    if not re.fullmatch(r"[0-9a-f]{32}", account_id):
        raise ValueError("account_id must be a Cloudflare account ID")
    if not re.fullmatch(r"[a-z][a-z0-9-]{2,62}", name):
        raise ValueError("name must be a lowercase Worker name")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,61}[a-z0-9]", bucket):
        raise ValueError("bucket must be an R2 bucket name")
    if any(not re.fullmatch(r"[a-z0-9]+(?:[.-][a-z0-9]+)+", domain) for domain in domains):
        raise ValueError("domains must be explicit lowercase hostnames")
    if not (site / "index.html").is_file() or not (site / "music/manifest.json").is_file():
        raise ValueError("site must be a complete built Audio as Code website")
    if output == site or output.is_relative_to(site) or site.is_relative_to(output):
        raise ValueError("staging directory and website must not overlap")
    if output.exists():
        raise ValueError("staging directory already exists; select a fresh --output directory")
    paths = sorted(site.rglob("*"))
    if any(path.is_symlink() for path in paths):
        raise ValueError("website must not contain symlinks")
    files = [path for path in paths if path.is_file()]
    media, uploads = {}, []
    for source in files:
        size = source.stat().st_size
        if size <= ASSET_LIMIT:
            continue
        relative = source.relative_to(site).as_posix()
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        entry = {
            "key": f"sha256/{digest}/{source.name}",
            "bytes": size,
            "sha256": digest,
            "content_type": "audio/wav"
            if source.suffix == ".wav"
            else (mimetypes.guess_type(source.name)[0] or "application/octet-stream"),
        }
        media["/" + relative] = entry
        uploads.append({"site_path": relative, **entry})
    output.mkdir(parents=True)
    for source in files:
        relative = source.relative_to(site)
        if "/" + relative.as_posix() in media:
            continue
        target = output / "assets" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    for filename in ("worker.js", "media-handler.js"):
        shutil.copy2(ROOT / "web/cloudflare" / filename, output / filename)
    config = {
        "$schema": "https://raw.githubusercontent.com/cloudflare/workers-sdk/main/packages/wrangler/config-schema.json",
        "name": name,
        "account_id": account_id,
        "main": "worker.js",
        "compatibility_date": "2026-10-02",
        "workers_dev": True,
        "assets": {"directory": "./assets", "binding": "ASSETS"},
        "r2_buckets": [{"binding": "MEDIA", "bucket_name": bucket}],
        "observability": {
            "enabled": True,
            "head_sampling_rate": 0.01,
            "traces": {"enabled": True, "head_sampling_rate": 0.01},
        },
    }
    if domains:
        config["routes"] = [{"pattern": domain, "custom_domain": True} for domain in domains]
    report = {
        "site": str(site),
        "output": str(output),
        "worker": name,
        "bucket": bucket,
        "domains": domains,
        "static_files": len(files) - len(media),
        "static_bytes": sum(path.stat().st_size for path in files)
        - sum(entry["bytes"] for entry in media.values()),
        "large_files": uploads,
    }
    for filename, data in (
        ("wrangler.jsonc", config),
        ("media-manifest.json", media),
        ("staging-report.json", report),
    ):
        (output / filename).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", type=Path, default=ROOT / "output/site")
    parser.add_argument("--output", type=Path, default=ROOT / "output/cloudflare")
    parser.add_argument("--account-id", required=True)
    parser.add_argument("--name", default="audioascode")
    parser.add_argument("--bucket", default="audioascode-media")
    parser.add_argument("--domain", action="append", default=[])
    args = parser.parse_args()
    print(
        json.dumps(
            prepare(
                args.site,
                args.output,
                account_id=args.account_id,
                name=args.name,
                bucket=args.bucket,
                domains=tuple(args.domain),
            ),
            indent=2,
        )
    )
