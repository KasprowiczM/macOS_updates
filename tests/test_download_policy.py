import io
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib/python"))
import download_policy as dp


class Response:
    def __init__(self, status=200, headers=None, data=b"good"):
        self.status, self.headers, self.data = status, headers or {}, io.BytesIO(data)

    def getheader(self, key):
        return self.headers.get(key)

    def read(self, size):
        return self.data.read(size)

    def read1(self, size):
        return self.data.read(size)

    def close(self):
        pass


class DownloadPolicyTests(unittest.TestCase):
    def test_header_read_is_aborted_by_absolute_deadline(self):
        import threading

        ended = threading.Event()

        class Socket:
            def shutdown(self, mode):
                ended.set()

        class Connection:
            sock = Socket()

            def request(self, *args, **kwargs):
                pass

            def getresponse(self):
                if not ended.wait(1):
                    raise AssertionError("header read had no deadline")
                return Response()

            def close(self):
                pass

        with patch.object(dp, "_PinnedHTTPS", return_value=Connection()):
            with self.assertRaisesRegex(ValueError, "download_timeout"):
                dp._request("https://vendor.test/a", ["93.184.216.34"], 0.01)

    def test_truncated_content_length_does_not_replace_previous_file(self):
        with tempfile.TemporaryDirectory() as root, patch.object(
            dp, "resolve_public_addresses", return_value=["93.184.216.34"]
        ):
            dest = pathlib.Path(root) / "out"
            dest.write_bytes(b"previous")
            with self.assertRaisesRegex(ValueError, "download_incomplete"):
                dp.download(
                    "https://vendor.test/a",
                    str(dest),
                    ["vendor.test"],
                    request=lambda *a: Response(
                        headers={"Content-Length": "99"}, data=b"partial"
                    ),
                )
            self.assertEqual(dest.read_bytes(), b"previous")

    def test_url_rejections(self):
        for url in [
            "http://vendor.test/a",
            "https://u:p@vendor.test/a",
            "https://vendor.test:444/a",
            "https://vendor.test.evil/a",
            "https://vendor.test./a",
            "https://vеndor.test/a",
            "https://localhost/a",
            "https://127.0.0.1/a",
            "https://[::1]/a",
            "https://vendor.test/a#fragment",
            "https://vendor.test/a\nX: bad",
        ]:
            with self.subTest(url=url), self.assertRaises(ValueError):
                dp.validate_download_url(url, ["vendor.test"])

    def test_signed_url_not_rewritten(self):
        url = "https://vendor.test/a?X-Signature=secret%2Fabc&expires=1"
        self.assertEqual(dp.validate_download_url(url, ["vendor.test"]), url)

    def test_redirect_exact_allowlist(self):
        self.assertTrue(
            dp.validate_redirect_chain(
                ["https://vendor.test/a", "https://cdn.test/a"],
                ["vendor.test", "cdn.test"],
            )
        )
        self.assertFalse(
            dp.validate_redirect_chain(
                ["https://vendor.test/a", "https://evil.test/a"], ["vendor.test"]
            )
        )

    def test_dns_all_answers_public(self):
        for values in [
            ["127.0.0.1"],
            ["10.0.0.1"],
            ["93.184.216.34", "192.168.1.1"],
            ["::1"],
            ["169.254.169.254"],
            ["224.0.0.1"],
            ["ff02::1"],
            ["64:ff9b::a00:1"],
            ["2002:a00:1::"],
        ]:
            with self.subTest(values=values), patch.object(
                dp.socket,
                "getaddrinfo",
                return_value=[(2, 1, 6, "", (v, 443)) for v in values],
            ):
                with self.assertRaises(ValueError):
                    dp.resolve_public_addresses("vendor.test")

    def test_redirect_rejected_before_second_request(self):
        calls = []

        def request(url, addresses, timeout):
            calls.append(url)
            return Response(302, {"Location": "https://evil.test/private"})

        with tempfile.TemporaryDirectory() as root, patch.object(
            dp, "resolve_public_addresses", return_value=["93.184.216.34"]
        ):
            with self.assertRaises(ValueError):
                dp.download(
                    "https://vendor.test/a",
                    root + "/out",
                    ["vendor.test"],
                    request=request,
                )
        self.assertEqual(calls, ["https://vendor.test/a"])

    def test_stream_limit_preserves_previous_file(self):
        with tempfile.TemporaryDirectory() as root, patch.object(
            dp, "resolve_public_addresses", return_value=["93.184.216.34"]
        ):
            dest = pathlib.Path(root) / "out"
            dest.write_bytes(b"previous")
            with self.assertRaises(ValueError):
                dp.download(
                    "https://vendor.test/a",
                    str(dest),
                    ["vendor.test"],
                    max_bytes=3,
                    request=lambda *args: Response(data=b"large"),
                )
            self.assertEqual(dest.read_bytes(), b"previous")
            self.assertEqual(list(pathlib.Path(root).iterdir()), [dest])

    def test_success_pins_resolved_address_on_every_hop(self):
        calls = []

        def request(url, addresses, timeout):
            calls.append((url, addresses))
            return (
                Response(302, {"Location": "https://cdn.test/file"})
                if len(calls) == 1
                else Response(data=b"ok")
            )

        with tempfile.TemporaryDirectory() as root, patch.object(
            dp, "resolve_public_addresses", side_effect=[["93.184.216.34"], ["1.1.1.1"]]
        ):
            dp.download(
                "https://vendor.test/a",
                root + "/out",
                ["vendor.test", "cdn.test"],
                request=request,
            )
            self.assertEqual(pathlib.Path(root + "/out").read_bytes(), b"ok")
        self.assertEqual(calls[1][1], ["1.1.1.1"])

    def test_dns_resolution_has_deadline(self):
        import time

        with patch.object(
            dp.socket, "getaddrinfo", side_effect=lambda *a, **k: time.sleep(0.1)
        ):
            with self.assertRaises(ValueError):
                dp.resolve_public_addresses("vendor.test", timeout=0.001)

    def test_slow_drip_uses_single_read_and_checks_absolute_deadline(self):
        clock = [0.0]

        class Slow(Response):
            def read(self, size):
                raise AssertionError("multi-read buffering bypasses total deadline")

            def read1(self, size):
                clock[0] += 0.4
                return b"x"

        with tempfile.TemporaryDirectory() as root, patch.object(
            dp, "resolve_public_addresses", return_value=["93.184.216.34"]
        ), patch.object(dp.time, "monotonic", side_effect=lambda: clock[0]):
            with self.assertRaisesRegex(ValueError, "download_timeout"):
                dp.download(
                    "https://vendor.test/a",
                    root + "/out",
                    ["vendor.test"],
                    timeout=1,
                    request=lambda *args: Slow(),
                )
            self.assertLessEqual(clock[0], 1.2 + 0.001)
            self.assertFalse(pathlib.Path(root + "/out").exists())

    def test_reviewed_recipe_host_binding_and_sparkle_refusal(self):
        action = {
            "action_scope": "direct_update",
            "target": {"kind": "app", "id": "i"},
            "adapter_id": "github_dmg",
            "expected_target": {
                "bundle_id": "org.example",
                "team_id": "TEAM",
                "channel": "stable",
            },
            "expected_resolution": {
                "source": "vendor",
                "capability": "reviewed_direct",
            },
        }
        recipe = {
            "adapter_id": "github_dmg",
            "bundle_ids": ["org.example"],
            "team_ids": ["TEAM"],
            "channels": ["stable"],
            "architectures": ["arm64"],
            "minimum_os": "13",
            "download_hosts": ["vendor.test", "cdn.test"],
            "allowed_artifacts": ["dmg"],
        }
        self.assertEqual(
            dp.reviewed_artifact_hosts(action, {"recipes": [recipe]}, "dmg"),
            ["vendor.test", "cdn.test"],
        )
        for changed in [
            dict(action, adapter_id="sparkle_appcast"),
            dict(action, action_scope="network_check"),
            dict(
                action,
                expected_target={
                    "bundle_id": "org.example",
                    "team_id": "EVIL",
                    "channel": "stable",
                },
            ),
        ]:
            with self.assertRaises(ValueError):
                dp.reviewed_artifact_hosts(changed, {"recipes": [recipe]}, "dmg")
        with self.assertRaises(ValueError):
            dp.reviewed_artifact_hosts(action, {"recipes": []}, "dmg")
        with self.assertRaises(ValueError):
            dp.reviewed_artifact_hosts(action, {"recipes": [recipe, recipe]}, "dmg")
