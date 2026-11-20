"""stdlib HTTPS fetch with timeout, size limit, and retries."""

from __future__ import annotations

import ssl
import time
import urllib.error
import urllib.request
from pathlib import Path


class FetchError(RuntimeError):
    pass


def fetch_url(
    url: str,
    dest: str | Path,
    *,
    timeout: int = 30,
    max_bytes: int = 10_485_760,
    retries: int = 2,
) -> Path:
    if not url.startswith("https://"):
        raise FetchError("Only https:// URLs are allowed")
    target = Path(dest)
    last_error: Exception | None = None
    attempts = max(1, retries + 1)
    context = ssl.create_default_context()
    for _ in range(attempts):
        try:
            request = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
                data = response.read(max_bytes + 1)
            if len(data) > max_bytes:
                raise FetchError(f"Response exceeded {max_bytes} bytes")
            if not data:
                raise FetchError("Empty response")
            target.parent.mkdir(parents=True, exist_ok=True)
            tmp = target.with_suffix(target.suffix + ".part")
            tmp.write_bytes(data)
            tmp.replace(target)
            try:
                target.chmod(0o600)
            except OSError:
                pass
            return target
        except urllib.error.HTTPError as exc:
            last_error = exc
            if exc.code == 429:
                retry_after = exc.headers.get("Retry-After", "1") if exc.headers else "1"
                try:
                    time.sleep(min(int(retry_after), 10))
                except ValueError:
                    time.sleep(1)
                continue
            if exc.code in {404, 410, 401, 403}:
                break
        except (urllib.error.URLError, TimeoutError, FetchError, OSError) as exc:
            last_error = exc
    raise FetchError(str(last_error) if last_error else "fetch failed")
