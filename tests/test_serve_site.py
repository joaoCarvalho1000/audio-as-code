"""Protocol checks for seekable local listening previews."""

import functools
import gzip
import http.client
import threading
from contextlib import closing
from http.server import ThreadingHTTPServer

import pytest

from examples.serve_site import SiteHandler


@pytest.fixture
def site(tmp_path):
    root = tmp_path / "site"
    root.mkdir()
    (root / "index.html").write_text("<p>Audio as Code</p>" * 200)
    (root / "clip.mp3").write_bytes(bytes(range(256)) * 100)
    handler = functools.partial(SiteHandler, directory=str(root))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()

    def request(path="/clip.mp3", headers=None, method="GET"):
        with closing(http.client.HTTPConnection("127.0.0.1", server.server_port)) as client:
            client.request(method, path, headers=headers or {})
            response = client.getresponse()
            return response.status, dict(response.getheaders()), response.read()

    yield request, root
    server.shutdown()
    server.server_close()
    worker.join()


@pytest.mark.parametrize(
    ("range_header", "expected", "content_range"),
    [
        ("bytes=2-9", bytes(range(2, 10)), "bytes 2-9/25600"),
        ("bytes=-3", bytes([253, 254, 255]), "bytes 25597-25599/25600"),
        ("bytes=25598-", bytes([254, 255]), "bytes 25598-25599/25600"),
        ("bytes=25598-99999", bytes([254, 255]), "bytes 25598-25599/25600"),
    ],
)
def test_media_ranges(site, range_header, expected, content_range):
    request, _ = site
    status, headers, body = request(headers={"Range": range_header})
    assert status == 206
    assert headers["Content-Range"] == content_range
    assert int(headers["Content-Length"]) == len(expected)
    assert body == expected
    assert "Content-Encoding" not in headers


@pytest.mark.parametrize("value", ["bytes=25600-", "bytes=-0", "bytes=8-2"])
def test_unsatisfiable_ranges(site, value):
    status, headers, body = site[0](headers={"Range": value})
    assert (status, body) == (416, b"")
    assert headers["Content-Range"] == "bytes */25600"


def test_head_and_if_range(site):
    request, _ = site
    status, headers, body = request(method="HEAD", headers={"Range": "bytes=2-3"})
    assert status == 200 and body == b""
    assert headers["Content-Length"] == "25600"
    for validator in [headers["ETag"], headers["Last-Modified"]]:
        assert request(headers={"Range": "bytes=2-3", "If-Range": validator})[0] == 206
    assert request(headers={"Range": "bytes=2-3", "If-Range": '"stale"'})[0] == 200
    assert request(headers={"Range": "bytes=1-2,5-6"})[0] == 200


def test_text_compression_revalidation_and_rebuild(site):
    request, root = site
    plain_status, plain_headers, plain = request("/")
    status, headers, body = request("/", {"Accept-Encoding": "gzip"})
    assert plain_status == status == 200
    assert gzip.decompress(body) == plain
    assert len(body) < len(plain) / 2
    assert headers["Vary"] == "Accept-Encoding"
    assert headers["Cache-Control"] == "no-cache"
    assert headers["ETag"] != plain_headers["ETag"]
    assert request("/", {"Accept-Encoding": "gzip;q=0"})[2] == plain
    conditional = {"If-None-Match": headers["ETag"], "Accept-Encoding": "gzip"}
    assert request("/", conditional)[0] == 304
    assert request("/", {"If-Modified-Since": plain_headers["Last-Modified"]})[0] == 304
    (root / "index.html").write_text("Rebuilt site")
    status, _, body = request("/", conditional)
    assert status == 200 and gzip.decompress(body) == b"Rebuilt site"


def test_missing_directory_and_outside_symlink(site, tmp_path):
    request, root = site
    assert request("/missing")[0] == 404
    (root / "empty").mkdir()
    assert request("/empty")[0] == 301
    assert request("/empty/")[0] == 404
    secret = tmp_path / "outside.txt"
    secret.write_text("outside")
    assert request("/../outside.txt")[0] == 404
    try:
        (root / "link.txt").symlink_to(secret)
    except OSError:
        pytest.skip("OS does not permit symlink creation")
    assert request("/link.txt")[0] == 403
