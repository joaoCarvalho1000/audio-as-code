# Preparing a release

This workflow prepares the early prototype hosted in
[the source repository](https://github.com/joaoCarvalho1000/audio-as-code).
Local commands below build and verify artifacts without publishing them.
The separate `Publish to PyPI` workflow runs only when a maintainer explicitly
dispatches it from `main`; pushes and tags do not trigger publication.

## Decide the scope

Review `CHANGELOG.md`, the supported Python range and all compatibility changes.
The current package version is `0.1.0`, while the JSON score schema is version
`"1"`. Do not change the schema version solely because the package version changes.

For an actual future version change, update `pyproject.toml` and
`src/audio_as_code/__init__.py` together, then update the root package entry in
`uv.lock` using uv and review the lock diff. Do not incidentally upgrade dependencies.
Convert only the intended changelog entries into a dated release record when that
release actually exists.

## Run source checks

```sh
uv sync --locked
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run python .github/scripts/check_schema.py
```

Record the tested OS, Python and dependency versions. For synthesis changes, run
the relevant musical examples and audition the results; keep listening observations
separate from numerical measurements. Regenerate affected demos only when needed.

## Build and inspect both distributions

Choose an empty destination; the following directory should contain only the
artifacts for this candidate:

```sh
uv build --no-sources --out-dir output/release-candidate
uv run python .github/scripts/check_distribution.py output/release-candidate
uv run python .github/scripts/smoke_distribution.py output/release-candidate
```

The checker verifies expected metadata/version, the CLI entry point, license,
`py.typed`, required portable source files, and absence of private/generated paths.
The smoke script rebuilds a wheel from the sdist, compares its package payload with
the candidate wheel, and installs both into isolated environments. It exercises
imports, the new Pattern helpers, static inspection, score round-trip, WAV/MIDI
exports, both CLI entry points, and a structured invalid-score error.

The scripts use uv and the standard library plus the project's installed runtime
dependencies; they do not need a package-registry publishing token. Isolated builds
and installations may fetch dependencies. The checked-in lock makes source-checkout
setup reproducible; a package consumer resolves the declared runtime version ranges.

Keep wheel and sdist checks separate from the website's downloadable source ZIP:

| Artifact | Contents and contract |
| --- | --- |
| Wheel | Importable `audio_as_code`, `aac` CLI, type marker and package metadata/license. |
| Source distribution | Engine, examples, note/notation sources, tests, schemas, docs, portable agent instructions, site sources and project/build inputs. |
| Website source ZIP | A separately built portable checkout; its allowlist lives in `examples/build_site.py` and must include new contribution/release files. |
| Generated example bundles | Specific scores, audio and reproduction source; generated locally under `output/`, outside the package distributions. |

Inspect archive member lists and retain hashes with the candidate. Confirm that
examples and required data are included, and that local agent state, `.env` files,
keys, logs, caches, `%SystemDrive%`, and generated output are absent. Re-run the
checks after any change to the candidate inputs. Do not ship local render archives
merely because they exist beside the source.

## Before a release

Verify the target repository/registry, ownership and naming.
Confirm that the private vulnerability-reporting route in `SECURITY.md` still works.
Use only real URLs in package metadata, documentation and badges after those
destinations exist. Review source-score attribution and all distributed licenses.

Decide who authorizes publication, the version/tag, and which verified artifact
hashes are being published. Registry credentials and deployment configuration
belong outside source artifacts. This repository's CI only checks code; the
manual publishing workflow is separate.

After publication, verify installation from the actual destination, record release
links and hashes, and update the status text. Until then, describe downloads as local
source or development artifacts rather than an available registry release.

## Publish to PyPI

The workflow at `.github/workflows/publish.yml` uses PyPI Trusted Publishing.
It requires an authenticated PyPI account owner to configure the publisher once.
For the first release, add a GitHub pending publisher in
[PyPI account publishing settings](https://pypi.org/manage/account/publishing/):

| Field | Value |
| --- | --- |
| PyPI project name | `audio-as-code` |
| Owner | `joaoCarvalho1000` |
| Repository name | `audio-as-code` |
| Workflow name | `publish.yml` |
| Environment name | `pypi` |

Use the filename alone for the workflow field. A pending publisher creates the
project on its first successful upload; it does not reserve the name. For an
existing project, add the same publisher in that project's publishing settings.
See [PyPI's pending publisher documentation](https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/).

Configure the repository's GitHub environment named `pypi` to allow the `main`
branch. The workflow itself also refuses publication from other branches or
repositories. No PyPI API token or GitHub repository secret is needed.

Once the publisher is configured and the reviewed commit is on `main`, use
Actions → **Publish to PyPI** → **Run workflow**, choose `main`, and enter the exact
version in `pyproject.toml`, such as `0.1.0`. This dispatch authorizes a real PyPI
upload. Confirm the workflow run's commit matches the reviewed commit.
Confirm that the full CI matrix also passes on that exact commit; the publishing
workflow runs its own checks on Linux with Python 3.13.

The build job checks the version against both source declarations, runs tests,
lint, formatting and schema checks, then builds and inspects both distributions.
It installs the wheel and rebuilt sdist outside the checkout and runs
`twine check --strict`. The run summary records artifact SHA-256 hashes.
Only after these checks pass does the publishing job receive `id-token: write`;
it downloads those same artifacts and uploads them with the official PyPA action.
It neither checks out nor executes the project's build code with that permission.
The separate verification job compares the PyPI file hashes and installs the
exact version from PyPI outside the checkout, running the installed smoke checks.

After publication and verification succeed, record the publishing run's full commit
SHA and create an annotated version tag at that exact commit. For example, replace
`REVIEWED_COMMIT_SHA` below with the verified run's SHA before running the command:

```sh
git tag -a v0.1.0 REVIEWED_COMMIT_SHA -m "Audio as Code 0.1.0"
git push origin refs/tags/v0.1.0
```

Use the actual release version for future tags. Create the GitHub Release from that
tag, with the PyPI link, release notes and artifact hashes from the workflow summary.
The tag must identify the published source even if `main` has advanced. Update the
changelog and publication status once the release exists.

Do not rebuild or overwrite files for an already published version. If an upload
partly succeeds, inspect the registry's files and hashes before attempting recovery;
the workflow deliberately does not ignore duplicate uploads. If verification fails
after the upload succeeds, investigate the installed release before changing its
status. A failed verification job does not undo publication.

This follows [PyPI's Trusted Publishing guidance](https://docs.pypi.org/trusted-publishers/using-a-publisher/)
and the [PyPA publishing action](https://github.com/pypa/gh-action-pypi-publish).

Build behavior follows [uv's packaging guide](https://docs.astral.sh/uv/guides/package/);
file selection follows [Hatch's build configuration](https://hatch.pypa.io/latest/config/build/).
