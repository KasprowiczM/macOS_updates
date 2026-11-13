"""Consent-bound file operations for optional local setup (no tool execution)."""
import hashlib
import json
import os
import stat
import tempfile
from pathlib import Path

LIMIT = 1024 * 1024


def _metadata(value):
    return [value.st_dev, value.st_ino, value.st_mtime_ns, value.st_size, value.st_mode]


def _read_regular(path):
    before = os.lstat(path)
    if not stat.S_ISREG(before.st_mode):
        raise ValueError('Target must be a regular file, not a link or device')
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, 'rb') as stream:
        opened = os.fstat(stream.fileno())
        if _metadata(before) != _metadata(opened):
            raise ValueError('Target changed while being inspected')
        data = stream.read(LIMIT + 1)
        if len(data) > LIMIT or _metadata(opened) != _metadata(os.fstat(stream.fileno())):
            raise ValueError('Target is too large or changed while being inspected')
    return opened, data


def fingerprint(path):
    """Return an opaque preview token; a dangling link is never absence."""
    try:
        metadata, data = _read_regular(path)
    except FileNotFoundError:
        # lstat alone identifies absence; an unlinked opened file is not a new
        # approval for absence, so repeat to fail closed on a surviving link.
        if os.path.lexists(path):
            raise ValueError('Target changed while being inspected')
        return 'null'
    return json.dumps([_metadata(metadata), hashlib.sha256(data).hexdigest()])


def _unchanged(path, expected):
    if fingerprint(path) != expected:
        raise ValueError('Target changed since preview; run setup again')


def append_profile(path, line, expected):
    """Append to the previewed inode, or exclusively create a missing profile."""
    path = Path(path)
    if '\n' in line or '\r' in line:
        raise ValueError('Expected one shell profile line')
    _unchanged(path, expected)
    flags = os.O_WRONLY | os.O_APPEND | os.O_NOFOLLOW | os.O_NONBLOCK
    if expected == 'null':
        flags |= os.O_CREAT | os.O_EXCL
        data = b''
        wanted = None
    else:
        wanted, data = _read_regular(path)
        if json.dumps([_metadata(wanted), hashlib.sha256(data).hexdigest()]) != expected:
            raise ValueError('Profile changed since preview')
        if line.encode() in data.splitlines():
            return
    descriptor = os.open(path, flags, 0o600)
    with os.fdopen(descriptor, 'ab') as stream:
        opened = os.fstat(stream.fileno())
        if not stat.S_ISREG(opened.st_mode):
            raise ValueError('Profile is not a regular file')
        if wanted is not None and _metadata(wanted) != _metadata(opened):
            raise ValueError('Profile changed since preview')
        if _metadata(os.lstat(path)) != _metadata(opened):
            raise ValueError('Profile path changed since preview')
        prefix = b'\n' if data and not data.endswith(b'\n') else b''
        stream.write(prefix + line.encode() + b'\n')
        stream.flush()
        os.fsync(stream.fileno())


def _backup(source, target):
    metadata, data = _read_regular(source)
    descriptor, name = tempfile.mkstemp(prefix=target.name + '.backup.', dir=target.parent)
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
            os.fchmod(stream.fileno(), stat.S_IMODE(metadata.st_mode))
    except BaseException:
        os.unlink(name)
        raise
    return name


def apply_pam(target, sudo_file, mode, expected, desired):
    """Run after sudo: revalidate, back up, then create exclusively or remove.

    The PAM directory is administrator-owned. Another root process can always
    modify it; checks are not an authorization boundary against root itself.
    """
    target = Path(target)
    if mode not in ('install', 'uninstall'):
        raise ValueError('Unknown PAM operation')
    _unchanged(target, expected)
    if mode == 'install' and expected != 'null':
        raise ValueError('PAM installation requires an absent target')
    if mode == 'uninstall':
        if expected == 'null' or _read_regular(target)[1] != desired.encode():
            raise ValueError('PAM content is not the approved managed configuration')
    backup = _backup(sudo_file if mode == 'install' else target, target)
    _unchanged(target, expected)
    if mode == 'uninstall':
        os.unlink(target)
        return backup
    descriptor, stage = tempfile.mkstemp(prefix=target.name + '.stage.', dir=target.parent)
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(desired.encode())
            stream.flush()
            os.fsync(stream.fileno())
            os.fchmod(stream.fileno(), 0o444)
        # link() fails if ANY target exists, including a directory or a dangling
        # symlink. Completed content becomes visible in one filesystem operation.
        os.link(stage, target)
    finally:
        os.unlink(stage)
    return backup
