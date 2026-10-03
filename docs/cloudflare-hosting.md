# Host the website on Cloudflare

The repository includes a Workers Static Assets + R2 hosting adapter. Python
builds the website and audio locally; production serves finished files with a
small JavaScript Worker and no Python backend or synthesis API. This guide
describes the maintainer workflow, not the current deployment status.

Cloudflare limits each static asset to **25 MiB**. The staging helper copies files
at or below that size into `assets/` and maps larger files to private R2 objects.
Visitors keep the same site URLs. Normal assets use Cloudflare's asset binding;
the Worker streams large files listed in its generated media manifest. See the
[platform limits](https://developers.cloudflare.com/workers/platform/limits/) and
[asset routing documentation](https://developers.cloudflare.com/workers/static-assets/routing/worker-script/).

## Prepare a release locally

Finish the [website build](website.md), including a successful strict build.
Install Node.js 22 or later and npm. The hosting package pins Wrangler 4.147.0;
use its lockfile. Examples below use PowerShell from the repository root.
Replace the account ID and choose a fresh staging directory for every release.
Omit `--domain` options to deploy only to `workers.dev` initially.

```powershell
npm ci --prefix web/cloudflare
npm test --prefix web/cloudflare
$accountId = 'YOUR_32_CHARACTER_CLOUDFLARE_ACCOUNT_ID'
uv run python examples/prepare_cloudflare.py --site output/site --output output/cloudflare-release --account-id $accountId --name audioascode --bucket audioascode-media --domain audioascode.com --domain www.audioascode.com
$releaseStage = (Resolve-Path output/cloudflare-release).Path
$releaseConfig = Join-Path $releaseStage 'wrangler.jsonc'
$releaseReport = Get-Content (Join-Path $releaseStage 'staging-report.json') -Raw | ConvertFrom-Json
npm exec --prefix web/cloudflare -- wrangler deploy --config $releaseConfig --dry-run
```

The helper refuses an existing staging directory and never publishes. Review
`wrangler.jsonc` for the account, Worker, bucket and domains. It binds `ASSETS`
and `MEDIA`, uses the tested compatibility date `2026-10-02`, and enables sampled
logs and traces. `media-manifest.json` maps paths to content-addressed R2 keys,
sizes, content types and SHA-256 hashes. `staging-report.json` lists uploads.
A dry run checks bundling and configuration; it does not verify remote resources.

Keep `output/site/` unchanged until uploads finish: the report refers to those
files. Build and stage again after any source, audio or documentation change.
Do not hand-edit the manifest or mix files from different releases.

## Verify local storage and serving

Use the same explicit persistence directory for upload and dev. This uploads the
first large entry to local R2; repeat for additional entries if needed. A site
without large files needs only the dev command. These commands require no real
bucket creation and access only local bindings. See
[Wrangler local data](https://developers.cloudflare.com/workers/local-development/local-data/).

```powershell
$localState = Join-Path (Get-Location) 'output/cloudflare-local-state'
$entry = $releaseReport.large_files[0]
$objectPath = $releaseReport.bucket + '/' + $entry.key
$sourceFile = Join-Path $releaseReport.site $entry.site_path
npm exec --prefix web/cloudflare -- wrangler r2 object put $objectPath --file $sourceFile --content-type $entry.content_type --local --persist-to $localState --config $releaseConfig
npm exec --prefix web/cloudflare -- wrangler dev --config $releaseConfig --local --persist-to $localState --ip 127.0.0.1 --port 8789
```

Open `http://127.0.0.1:8789/` and the uploaded entry's `site_path`. Stop with
Ctrl+C. An entry not uploaded to local R2 returns 404.

The release review tested a 27,599,292-byte WAV through this local runtime. Full
GET matched its manifest SHA-256; HEAD returned its size without a body; explicit
and suffix ranges returned the correct bytes with 206; conditional GET returned
304; an out-of-bounds range returned 416. Static JSON, unknown paths, absent R2
objects and unsupported methods returned the expected 200/404/404/405. These are
local runtime checks, not verification of remote deployment or audio quality.

## Upload and deploy

These commands change the selected Cloudflare account. The maintainer needs R2
enabled, access to the Worker and bucket, and control of configured custom
domains. Authenticate and confirm the account:

```powershell
npm exec --prefix web/cloudflare -- wrangler login
npm exec --prefix web/cloudflare -- wrangler whoami
```

Create the selected bucket once if it does not already exist:

```powershell
npm exec --prefix web/cloudflare -- wrangler r2 bucket create $releaseReport.bucket --config $releaseConfig
```

Keep the bucket private. The Worker needs no public R2 hostname or bucket listing;
its binding serves manifest-selected objects. Upload all large files before
deploying the Worker and assets:

```powershell
foreach ($entry in $releaseReport.large_files) {
    $sourceFile = Join-Path $releaseReport.site $entry.site_path
    $actualHash = (Get-FileHash -LiteralPath $sourceFile -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actualHash -ne $entry.sha256) { throw "Staged source changed: $sourceFile" }
    $objectPath = $releaseReport.bucket + '/' + $entry.key
    npm exec --prefix web/cloudflare -- wrangler r2 object put $objectPath --file $sourceFile --content-type $entry.content_type --remote --config $releaseConfig
    if ($LASTEXITCODE -ne 0) { throw "Upload failed: $objectPath" }
}
npm exec --prefix web/cloudflare -- wrangler deploy --config $releaseConfig
```

Do not deploy after an upload failure. Content-addressed keys preserve previous
media; retain old keys for rollback. Rolling back Worker code does not restore
deleted R2 objects. Consult the
[Wrangler R2 commands](https://developers.cloudflare.com/workers/wrangler/commands/r2/)
for alternate upload tooling or larger future objects.

After deployment, verify the actual hostname, static pages and every large
download. Compare full-download hashes with the report and repeat HEAD, Range,
conditional GET and 404 checks. Check playback and seeking in a browser. Record
the deployed Worker version and staging report with the release.

## Download behavior

The handler streams [R2 object bodies](https://developers.cloudflare.com/r2/api/workers/workers-api-reference/)
without buffering entire downloads. It supports GET and HEAD, single byte ranges
including suffix ranges, SHA-256 ETags, `If-None-Match`, and exact ETag
`If-Range`. Invalid or multiple range syntax falls back to a full response;
valid unsatisfiable ranges return 416. Multipart ranges and date-based
`If-Range` are not implemented.

Large-file responses use `Cache-Control: public, max-age=0, must-revalidate` so
stable URLs revalidate after a release. Missing objects return 404 and size
mismatches return 503. Verify upload hashes before release: equal size alone
does not establish content integrity. Ordinary files retain the static asset
service's behavior.
