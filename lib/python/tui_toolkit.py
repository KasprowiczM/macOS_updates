"""Leave curses before offering a separately confirmed toolkit update."""
import json
import os
import subprocess
import tempfile
from pathlib import Path
from inventory_store import _root


def finish_update(repo, receipt, language):
    root = _root(None, True)
    data = json.dumps(receipt, ensure_ascii=True).encode('utf-8')
    if len(data) > 65536:
        raise ValueError('invalid_receipt')
    script = Path(repo).resolve(strict=True) / 'scripts' / 'update_toolkit.sh'
    if script.is_symlink() or script.resolve(strict=True) != script:
        raise ValueError('unsafe_toolkit_script')
    fd, path = tempfile.mkstemp(prefix='.toolkit-review-', suffix='.json', dir=root)
    try:
        with os.fdopen(fd, 'wb') as handle:
            os.fchmod(handle.fileno(), 0o600)
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        env = dict(os.environ, MAC_UPDATE_LANG=language, MAC_LANG=language)
        env.pop('MAC_UPDATE_TUI_CHILD', None)
        # Inherit the original terminal. The helper asks for the full pinned SHA;
        # no confirmation or approval flag is supplied by the interface.
        return subprocess.call(['/bin/bash', str(script), '--apply', path], env=env)
    finally:
        os.unlink(path)
