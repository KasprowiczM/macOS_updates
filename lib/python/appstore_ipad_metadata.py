"""Read one installed iPad app's store identity without contacting the store."""
import os
import plistlib
import re
import stat
from xml.parsers.expat import ExpatError


def observe_ipad_metadata(app_path):
    """Return absent, partial, or exact ID evidence for a single app bundle.

    Missing metadata is normal for native Mac apps. Inaccessible, malformed or
    symlinked metadata is partial and cannot authorize a Track 2 action.
    """
    if not isinstance(app_path, str) or not os.path.isabs(app_path):
        return {'status': 'partial', 'reason_code': 'invalid_path'}
    wrapper = os.path.join(os.path.realpath(app_path), 'Wrapper')
    try:
        mode = os.lstat(wrapper).st_mode
    except FileNotFoundError:
        return {'status': 'absent'}
    except OSError:
        return {'status': 'partial', 'reason_code': 'metadata_inaccessible'}
    if not stat.S_ISDIR(mode):
        return {'status': 'partial', 'reason_code': 'unsafe_wrapper'}
    directory = None
    fd = None
    try:
        directory = os.open(wrapper, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            fd = os.open('iTunesMetadata.plist', os.O_RDONLY | os.O_NOFOLLOW, dir_fd=directory)
        except FileNotFoundError:
            return {'status': 'absent'}
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            return {'status': 'partial', 'reason_code': 'unsafe_metadata'}
        with os.fdopen(fd, 'rb') as stream:
            fd = None
            raw = stream.read(1024 * 1024 + 1)
        if len(raw) > 1024 * 1024:
            raise ValueError('oversize')
        data = plistlib.loads(raw)
        item = data.get('itemId') if isinstance(data, dict) else None
        item_id = str(item) if type(item) in (int, str) else ''
        if not re.fullmatch(r'[0-9]{1,30}', item_id):
            raise ValueError('invalid id')
        name = data.get('itemName') or data.get('bundleDisplayName') or ''
        if not isinstance(name, str) or len(name) > 512:
            raise ValueError('invalid name')
        return {'status': 'ok', 'evidence': dict(kind='app_store_ipad', store_id=item_id,
                                                   path=os.path.realpath(app_path), name=name)}
    except (OSError, ValueError, TypeError, plistlib.InvalidFileException, ExpatError, OverflowError):
        return {'status': 'partial', 'reason_code': 'metadata_unavailable'}
    finally:
        if fd is not None:
            os.close(fd)
        if directory is not None:
            os.close(directory)
