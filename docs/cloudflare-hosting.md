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

Staging also generates `assets/_headers` with explicit rules for each HTML file,
its extensionless URL, and directory aliases for `index.html`. Those responses use
`Cache-Control: public, max-age=0, must-revalidate`, so browsers revalidate HTML
and Cloudflare may compress it normally. The site's only analytics is PostHog, with
its privacy controls. Cloudflare Real User Measurements must stay disabled for the
zone (Speed > Real user monitoring > Disable completely); otherwise Cloudflare can
[inject its own Web Analytics beacon](https://developers.cloudflare.com/web-analytics/get-started/)
into HTML. After each deploy, confirm the served HTML contains no
`cloudflareinsights` reference. Adding `no-transform` would also block injection,
but it disables HTML compression. JavaScript, CSS, fonts,
JSON and media receive no added rule. An existing source `_headers` causes staging
to fail before writing anything; reconcile that policy explicitly before staging.

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

Verify a full GET against the manifest SHA-256 and HEAD against its byte count.
Explicit and suffix ranges should return the requested bytes with 206; a matching
`If-None-Match` should return 304, and an out-of-bounds range 416. Check static
JSON, unknown paths, absent R2 objects and unsupported methods too. Local serving
does not establish remote deployment behavior or audio quality.

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

## Agent requests and zone security

Zone security is separate from the Worker and asset headers. If a legitimate
agent receives HTTP 403 with Cloudflare error 1010, inspect
**Security Settings > Browser Integrity Check** for the affected zone and retest
after adjusting it. Reading this setting through the API requires Zone Settings
Read or Write permission; changing it requires Write permission. See
[Cloudflare's error 1010 guidance](https://developers.cloudflare.com/support/troubleshooting/http-status-codes/cloudflare-1xxx-errors/error-1010/).
Agents should identify their HTTP client truthfully, for example:

```python
from urllib.request import Request, urlopen

request = Request(
    "https://audioascode.com/llms.txt",
    headers={"User-Agent": "MyMusicAgent/1.0"},
)
with urlopen(request, timeout=30) as response:
    guide = response.read().decode("utf-8")
```

The HTML cache policy does not change this zone access behavior. Workers
observability logs and traces also remain enabled independently of client-side
analytics.

## Releases from GitHub

After the complete CI gate passes on `main`, the website job preserves the tested
site with a commit marker and SHA-256 file manifest. The deployment job downloads
that exact artifact, verifies it, stages assets without credentials, then publishes
through the `website-production` environment. That environment must permit only
`main` and hold a restricted `CLOUDFLARE_API_TOKEN`, scoped to the `audioascode` Worker (Editor), the
`audioascode-media` R2 bucket (object Write), and `audioascode.com`
(Workers Routes Write and Zone Read). Do not store a workstation OAuth
token. Set the repository variable `WEBSITE_DEPLOY_ENABLED=true` after setup.

The production uploader uses the S3 API through AWS CLI v2, supplied by the
GitHub Ubuntu runner and checked before credentials are exposed. Cloudflare's
[bucket-scoped object permissions](https://developers.cloudflare.com/r2/api/tokens/#permissions)
are supported by S3, not the REST API used by `wrangler r2 object put --remote`.
The script verifies the active account token, uses its ID as the S3 access key,
and derives the S3 secret as the SHA-256 of its value, as documented by Cloudflare.
These values stay in the upload subprocess environment, with unrelated GitHub,
Cloudflare and inherited AWS credentials removed. Each upload sends Content-MD5;
the staged SHA-256 and production range checks still apply. No broader R2 account
permission or additional stored credential is required. The earlier manual
Wrangler examples require an OAuth session or a token with REST-compatible R2
permissions. Jurisdiction-specific R2 buckets require their corresponding S3
endpoint; this deployment uses the account's default-jurisdiction bucket.

Deployments are serialized and refuse stale commits. Large media uploads finish
before the Worker changes. `/release.json` identifies the deployed commit. Live
checks cover core pages, discovery endpoints, missing routes and large-file
range/ETag behavior. A failed verification rolls back the observed deployment,
provided production has not since changed outside the workflow. Ambiguous upload
failures require reconciliation, not blind retries. The deployment artifact
records the outcome and previous Cloudflare version. Old R2 objects are retained.
An `upload_failed` record means the Worker publication was not started; uploaded
content-addressed media can be retained safely while the upload failure is repaired.

A rollback cannot reverse connected-resource changes. These checks do not replace
listening tests or establish perceptual realism. PyPI publication stays separate.

### Automation security and recovery

Pull request builds receive no production credentials. Website publication uses
only the artifact ID from the same successful main-branch run, after its complete
file inventory and commit marker have been verified. Actions use pinned commits;
the production environment must exclude PR branches and tags.

A unique release marker must match Cloudflare's deployment metadata before the
script considers that deployment its own. If verification fails, rollback is
attempted only while that recorded deployment is still current. This is a
best-effort concurrency check, not an atomic Cloudflare lock. Keep other production
deployers stopped while this pipeline is publishing or recovering.

Download the `website-deployment-*` report after a failure. `publishing`,
`rolling_back`, `rollback_failed`, and `needs_reconciliation` all require checking
Cloudflare's current deployment against the recorded IDs before taking action.
A cancelled job or network outage can leave an uncertain result. Do not blindly
rerun or restore an old version. Pause deployments, inspect the current version
and public `/release.json`, then choose the intended tested commit. Retain media
needed by previous Audio as Code versions. Raw API errors and credentials must
never be copied into these reports.

CI success alone is not an independent review. A PR can propose changes to its
own workflow, tests, HTML scripts, redirects or dependencies. Keep unattended
merging disabled until review from a separate trusted identity is enforced for
the latest commit. A label, comment, scan completion or a bot's assertion of
approval is insufficient. Treat PR descriptions, comments, repository instructions
and generated files as untrusted input to reviewing agents. Do not execute PR
code in a local session holding deployment credentials.

Cloudflare credentials must use the narrowest supported resource/product scope.
Account-level Pages Edit can affect other Pages projects in that account; it is
not a project-only credential. Keep credentials in the GitHub environment, rotate
them when necessary, and remove unused tokens. Public build logs and artifacts
must contain no keys, local browser profiles or environment files.
