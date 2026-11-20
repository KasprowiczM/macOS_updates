"""Requirements of the toolkit as the engine reports them (``update_all.sh --requirements --tsv``).

One tab-separated line per requirement: id, status, level, groups, name, hint. Status is one of
present, missing, wrong_arch, too_old, shim, manual; level is required or optional; groups is a
comma-separated list of group ids or ``core``. Name and hint are already localised. Reading is a plain
subprocess (no terminal) with a time limit; importing this module does nothing.
"""
import subprocess

STATUSES = ('present', 'missing', 'wrong_arch', 'too_old', 'shim', 'manual')
INSTALLABLE = ('missing', 'too_old', 'shim', 'wrong_arch')     # `manual` rows are shown but not installable
# `prepare` installs required rows only (lib/requirements.sh _req_installable); optional rows are listed with
# their hint but never offered for install.
READ_TIMEOUT = 60


class Requirement:
    __slots__ = ('ident', 'status', 'level', 'groups', 'name', 'hint')

    def __init__(self, ident, status, level, groups, name, hint):
        self.ident, self.status, self.level, self.groups, self.name, self.hint = ident, status, level, groups, name, hint

    @property
    def present(self):
        return self.status == 'present'

    @property
    def installable(self):
        return self.level == 'required' and self.status in INSTALLABLE


def parse_tsv(text):
    """Requirements from the engine's output; malformed lines and unknown statuses are skipped."""
    rows = []
    for line in str(text or '').splitlines():
        parts = line.rstrip('\r\n').split('\t')
        if len(parts) < 5:
            continue
        ident, status, level, groups, name = (p.strip() for p in parts[:5])
        hint = parts[5].strip() if len(parts) > 5 else ''
        if not ident or status not in STATUSES or level not in ('required', 'optional') or not name:
            continue
        group_list = [g for g in groups.split(',') if g] or ['core']
        rows.append(Requirement(ident[:80], status, level, group_list, name[:120], hint[:300]))
    return rows


def missing_required(rows):
    return [r for r in rows or [] if r.level == 'required' and not r.present]


def installable(rows):
    return [r for r in rows or [] if r.installable]


def read_requirements(repo, language='en'):
    """Run the engine once and return a list of Requirement, or None when it could not be read."""
    from tui_backend import build_command, child_environment
    try:
        command = build_command(repo, 'requirements')
        done = subprocess.run(command, env=child_environment(language), stdin=subprocess.DEVNULL, capture_output=True,
                              timeout=READ_TIMEOUT, check=False)
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    if done.returncode != 0:
        return None
    return parse_tsv(done.stdout.decode('utf-8', 'replace'))
