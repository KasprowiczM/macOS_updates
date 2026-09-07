"""HTTPS fetch adapter: reject http, empty, and oversized bodies."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "lib" / "python"))

from http_fetch import FetchError, fetch_url  # noqa: E402


class _Resp:
    def __init__(self, payload: bytes):
        self._payload = payload

    def read(self, n: int = -1) -> bytes:
        return self._payload[:n] if n >= 0 else self._payload

    def __enter__(self) -> "_Resp":
        return self

    def __exit__(self, *args) -> bool:
        return False


class HttpFetchTests(unittest.TestCase):
    def test_http_url_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "out.bin"
            with self.assertRaises(FetchError):
                fetch_url("http://example.test/x", dest)
            self.assertFalse(dest.exists())

    def test_empty_body_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "out.bin"
            with mock.patch("http_fetch.urllib.request.urlopen", return_value=_Resp(b"")):
                with self.assertRaises(FetchError):
                    fetch_url("https://example.test/x", dest)
            self.assertFalse(dest.exists())

    def test_https_body_is_written(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "out.bin"
            with mock.patch("http_fetch.urllib.request.urlopen", return_value=_Resp(b"ok-body")):
                written = fetch_url("https://example.test/x", dest)
            self.assertEqual(written.read_bytes(), b"ok-body")
            self.assertEqual(written.stat().st_mode & 0o777, 0o600)


if __name__ == "__main__":
    unittest.main()
