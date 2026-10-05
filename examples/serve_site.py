"""Preview the static listening site with byte ranges and compressed text.

Run from the checkout: python examples/serve_site.py --directory output/site
This localhost development helper does not render audio or deploy the site.
"""

from __future__ import annotations

import argparse
import functools
import gzip
import io
import re
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit


class SiteHandler(SimpleHTTPRequestHandler):
    """Serve files inside one directory, including single HTTP byte ranges."""

    def send_head(self):
        self.remaining = None
        root = Path(self.directory).resolve()
        path = Path(self.translate_path(self.path)).resolve()
        if not path.is_relative_to(root):
            self.send_error(403, "Path is outside the preview directory")
            return None
        # Match the extensionless HTML routes used by the production host.
        if (
            not path.is_file()
            and not (path / "index.html").is_file()
            and not path.suffix
            and not urlsplit(self.path).path.endswith("/")
        ):
            html_path = path.with_suffix(".html").resolve()
            if not html_path.is_relative_to(root):
                self.send_error(403, "Path is outside the preview directory")
                return None
            if html_path.is_file():
                path = html_path
        if path.is_dir():
            parts = urlsplit(self.path)
            if not parts.path.endswith("/"):
                self.send_response(301)
                self.send_header(
                    "Location", urlunsplit(("", "", parts.path + "/", parts.query, ""))
                )
                self.send_header("Content-Length", "0")
                self.end_headers()
                return None
            path = (path / "index.html").resolve()
            if not path.is_relative_to(root):
                self.send_error(403, "Path is outside the preview directory")
                return None
        try:
            source = path.open("rb")
        except OSError:
            self.send_error(404, "File not found")
            return None
        try:
            stat = path.stat()
            size = stat.st_size
            modified = self.date_time_string(stat.st_mtime)
            compressible = (
                path.suffix.lower()
                in {
                    ".html",
                    ".css",
                    ".js",
                    ".json",
                    ".svg",
                    ".txt",
                    ".xml",
                    ".md",
                }
                and size <= 2 * 1024 * 1024
            )
            encodings = {}
            for entry in self.headers.get("Accept-Encoding", "").split(","):
                name, _, params = entry.strip().partition(";")
                try:
                    encodings[name.lower()] = (
                        float(params.strip().removeprefix("q=")) if params else 1
                    )
                except ValueError:
                    encodings[name.lower()] = 0
            compressed = compressible and encodings.get("gzip", encodings.get("*", 0)) > 0
            # Ranges are over identity bytes; browsers use them for uncompressed media.
            requested_range = self.headers.get("Range") if self.command == "GET" else None
            if requested_range:
                compressed = False
            tag = f'"{stat.st_mtime_ns:x}-{size:x}-{"gz" if compressed else "id"}"'
            headers = {
                "Content-Type": self.guess_type(str(path)),
                "Last-Modified": modified,
                "ETag": tag,
                "Cache-Control": "no-cache",
                "Accept-Ranges": "bytes",
            }
            if compressible:
                headers["Vary"] = "Accept-Encoding"
            matches = self.headers.get("If-None-Match")
            unchanged = (
                matches is not None
                and any(t.strip().removeprefix("W/") in {tag, "*"} for t in matches.split(","))
            ) or (matches is None and self.headers.get("If-Modified-Since") == modified)
            if unchanged:
                self.send_response(304)
                for name, value in headers.items():
                    self.send_header(name, value)
                self.end_headers()
                source.close()
                return None
            status = 200
            if_range = self.headers.get("If-Range")
            if requested_range and (if_range is None or if_range in {tag, modified}):
                match = re.fullmatch(r"bytes=(\d*)-(\d*)", requested_range.strip())
                # Unknown units, malformed ranges and multipart ranges are ignored.
                if match and any(match.groups()):
                    first, last = match.groups()
                    start = int(first) if first else max(0, size - int(last))
                    end = min(size - 1, int(last)) if first and last else size - 1
                    if start > end or start >= size or (not first and int(last) == 0):
                        self.send_response(416)
                        self.send_header("Content-Range", f"bytes */{size}")
                        self.send_header("Content-Length", "0")
                        self.end_headers()
                        source.close()
                        return None
                    headers["Content-Range"] = f"bytes {start}-{end}/{size}"
                    source.seek(start)
                    size = end - start + 1
                    status = 206
            if compressed:
                payload = gzip.compress(source.read(), compresslevel=6, mtime=0)
                source.close()
                source = io.BytesIO(payload)
                size = len(payload)
                headers["Content-Encoding"] = "gzip"
            self.remaining = size
            headers["Content-Length"] = str(size)
            self.send_response(status)
            for name, value in headers.items():
                self.send_header(name, value)
            self.end_headers()
            return source
        except Exception:
            source.close()
            raise

    def copyfile(self, source, outputfile):
        # Never read an entire WAV/MP3 into memory, including range responses.
        remaining = self.remaining
        try:
            while remaining:
                chunk = source.read(min(64 * 1024, remaining))
                if not chunk:
                    break
                outputfile.write(chunk)
                remaining -= len(chunk)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass  # Normal when the listener seeks or switches pieces.


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=Path("output/site"))
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    directory = args.directory.resolve()
    if not directory.is_dir() or not (directory / "index.html").is_file():
        parser.error("--directory must contain the built site's index.html")
    if not 0 <= args.port <= 65535:
        parser.error("--port must be between 0 and 65535")
    handler = functools.partial(SiteHandler, directory=str(directory))
    with ThreadingHTTPServer(("127.0.0.1", args.port), handler) as server:
        print(f"Preview: http://127.0.0.1:{server.server_port}/ ({directory})", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
