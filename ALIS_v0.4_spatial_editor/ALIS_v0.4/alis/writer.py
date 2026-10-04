"""Preview, back up and atomically save a single Loadout Injector station.

The same plan/commit interface can later be used by the local web UI.
"""
from __future__ import annotations

import copy
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tempfile
from uuid import uuid4

from .dictionary import load_dictionary


class WriteError(ValueError):
    """A save was refused or could not be verified."""


class ChangedOnDisk(WriteError):
    """The station changed since its preview was generated."""


def revision(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _object(raw: bytes) -> dict:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise WriteError(f"Duplicate JSON field: {key!r}")
            result[key] = value
        return result

    def bad_constant(value):
        raise WriteError(f"Nonstandard JSON value: {value}")

    try:
        data = json.loads(raw.decode('utf-8-sig'), object_pairs_hook=pairs,
                          parse_constant=bad_constant)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise WriteError(f"Invalid UTF-8 station JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise WriteError('Station JSON must be an object.')
    allowed = data.get('allowedWeapons')
    if not isinstance(allowed, list) or any(not isinstance(k, str) or not k for k in allowed):
        raise WriteError('allowedWeapons must be an array of nonempty strings.')
    return data


def _safe_file(root: Path, path: Path) -> Path:
    # Check lexical components before resolving: a link within root may point
    # outside it (or change its destination). Refuse links entirely.
    try:
        parts = path.relative_to(root).parts
    except ValueError as exc:
        raise WriteError('Station path is outside preset-loadout.') from exc
    current = root
    for part in parts:
        current /= part
        if current.is_symlink():
            raise WriteError(f'Symbolic links are not supported: {current}')
    resolved = path.resolve(strict=True)
    if not resolved.is_relative_to(root) or not resolved.is_file():
        raise WriteError('Expected a regular file beneath preset-loadout.')
    return resolved


def _target(root, platform, index):
    root = Path(root).expanduser().resolve(strict=True)
    dictionary = load_dictionary(root)
    matches = [p for p in dictionary.platforms if p.casefold() == platform.casefold()]
    if len(matches) != 1:
        raise WriteError(f'Unknown or ambiguous platform: {platform!r}')
    name = matches[0]
    if Path(name).name != name or name in {'.', '..'} or '/' in name or '\\' in name:
        raise WriteError('Unsafe platform identifier in dictionary.')
    definitions = [s for s in dictionary.platforms[name].stations if s.station_index == index]
    if len(definitions) != 1:
        raise WriteError(f'Expected one definition for {name} station {index}.')
    folder = root / name / f'weaponstation{index}'
    if folder.is_symlink() or folder.parent.is_symlink():
        raise WriteError('Symbolic links are not supported for station folders.')
    files = sorted(folder.glob('*.json'))
    if len(files) != 1:
        raise WriteError(f'Expected exactly one station JSON in {folder}; found {len(files)}.')
    path = _safe_file(root, files[0])
    if path.stem != definitions[0].station_name:
        raise WriteError('Station JSON filename does not match the station dictionary.')
    return root, path, dictionary


def _write_key(dictionary, key):
    if not isinstance(key, str) or not key:
        raise WriteError('Weapon keys must be nonempty strings.')
    # Exact jsonKey wins over general asset aliases; never silently pick one
    # of several weapons with the same alias.
    exact = [w for w in dictionary.weapons if w.json_key == key]
    candidates = exact or [w for w in dictionary.weapons if w.asset_name == key]
    if len(candidates) != 1:
        raise WriteError(f'Unknown or ambiguous weapon key: {key!r}')
    result = candidates[0].write_key
    if not result:
        raise WriteError(f'Weapon {key!r} has no usable write key.')
    return result


@dataclass(frozen=True)
class EditPlan:
    root: Path
    path: Path
    original: bytes
    replacement: bytes
    before: tuple[str, ...]
    after: tuple[str, ...]
    normalized: tuple[tuple[str, str], ...] = ()
    restoring: Path | None = None

    @property
    def expected_revision(self):
        return revision(self.original)

    @property
    def changed(self):
        return self.original != self.replacement

    def summary(self):
        return {
            'path': str(self.path), 'changed': self.changed,
            'revision': self.expected_revision,
            'before_count': len(self.before), 'after_count': len(self.after),
            'added': [k for k in self.after if k not in self.before],
            'removed': [k for k in self.before if k not in self.after],
            'normalized': dict(self.normalized),
            'restore_source': str(self.restoring) if self.restoring else None,
        }


@dataclass(frozen=True)
class SaveResult:
    path: Path
    changed: bool
    backup: Path | None
    revision: str


def plan_edit(root, platform: str, index: int, *, add=(), remove=(),
              allow_empty=False, expected_revision: str | None = None) -> EditPlan:
    root, path, dictionary = _target(root, platform, index)
    original = path.read_bytes()
    if expected_revision is not None and revision(original) != expected_revision:
        raise ChangedOnDisk('Station changed on disk. Reload before editing.')
    data = _object(original)
    before = data['allowedWeapons']
    add = list(add)
    additions = list(dict.fromkeys(_write_key(dictionary, key) for key in add))
    removals = list(remove)
    # Removing an unknown existing key is allowed; this enables cleanup after
    # a mod is uninstalled without destroying other unresolved keys.
    remove_keys = set()
    for key in removals:
        if key in before:
            remove_keys.add(key)
        try:
            canonical = _write_key(dictionary, key)
        except WriteError:
            if key not in before:
                raise
        else:
            remove_keys.add(canonical)
            remove_keys.update(w.json_key for w in dictionary.weapons if w.write_key == canonical)
    if set(additions) & remove_keys:
        raise WriteError('The same weapon was requested for both add and remove.')
    after = [key for key in before if key not in remove_keys]
    normalized = []
    for key in add:
        canonical = _write_key(dictionary, key)
        if key != canonical:
            normalized.append((key, canonical))
        # Adding a stale alias also replaces that mount's obsolete spelling.
        stale_aliases = {w.json_key for w in dictionary.weapons
                         if w.is_stale_key and w.write_key == canonical}
        if stale_aliases & set(after):
            updated = []
            for existing in after:
                resolved = canonical if existing in stale_aliases else existing
                if resolved != canonical or canonical not in updated:
                    updated.append(resolved)
            after = updated
        if canonical not in after:
            after.append(canonical)
    if not after and after != before and not allow_empty:
        raise WriteError('This would empty the whitelist. Pass --allow-empty if intentional.')
    replacement = original
    if after != before:
        updated = copy.deepcopy(data)
        updated['allowedWeapons'] = after
        text = original.decode('utf-8-sig')
        indent_match = re.search(r'^([ \t]+)"', text, re.MULTILINE)
        indent = indent_match.group(1) if indent_match else '    '
        newline = '\r\n' if '\r\n' in text else '\n'
        rendered = json.dumps(updated, indent=indent, ensure_ascii=False, allow_nan=False)
        rendered += '\n' if text.endswith('\n') else ''
        replacement = rendered.replace('\n', newline).encode('utf-8')
        if original.startswith(b'\xef\xbb\xbf'):
            replacement = b'\xef\xbb\xbf' + replacement
        if _object(replacement) != updated:
            raise WriteError('Could not verify rendered JSON.')
    return EditPlan(root, path, original, replacement, tuple(before), tuple(after), tuple(normalized))


def plan_restore(root, platform: str, index: int, backup) -> EditPlan:
    root, path, _ = _target(root, platform, index)
    backup = Path(backup).expanduser().absolute()
    backup = _safe_file(root, backup)
    pattern = re.escape(path.name) + r'\.\d{8}T\d{12}Z\.[0-9a-f]{12}\.bak'
    if backup.parent != path.parent or not re.fullmatch(pattern, backup.name):
        raise WriteError('Choose an ALIS backup belonging to this station.')
    original = path.read_bytes()
    replacement = backup.read_bytes()
    before, after = _object(original), _object(replacement)
    return EditPlan(root, path, original, replacement,
                    tuple(before['allowedWeapons']), tuple(after['allowedWeapons']), restoring=backup)


@contextmanager
def _lock(root):
    path = root / '.alis-write.lock'
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise WriteError(f'Another ALIS save is active, or a stale lock exists: {path}') from exc
    try:
        with os.fdopen(descriptor, 'w') as handle:
            handle.write(f'ALIS pid={os.getpid()}\n')
            handle.flush()
            os.fsync(handle.fileno())
        yield
    finally:
        path.unlink()


def _backup(path, original):
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    backup = path.with_name(f'{path.name}.{stamp}.{uuid4().hex[:12]}.bak')
    created = False
    try:
        with backup.open('xb') as handle:
            created = True
            handle.write(original)
            handle.flush()
            os.fsync(handle.fileno())
        if backup.read_bytes() != original:
            raise WriteError('Backup verification failed; station was not changed.')
    except BaseException:
        if created:
            backup.unlink(missing_ok=True)
        raise
    return backup


def commit(plan: EditPlan) -> SaveResult:
    """Save only if disk still matches the preview; never overwrite old backups.

    ALIS's lock serializes its own writers. External programs do not honor it;
    keep other editors closed while saving. Replacement is atomic on ordinary
    local filesystems, but this is not a power-loss transaction guarantee.
    """
    _object(plan.original)
    intended = _object(plan.replacement)
    if tuple(intended['allowedWeapons']) != plan.after:
        raise WriteError('Invalid edit plan.')
    if plan.restoring is None:
        expected = _object(plan.original)
        expected['allowedWeapons'] = list(plan.after)
        if intended != expected:
            raise WriteError('Edit plan changed fields other than allowedWeapons.')
    with _lock(plan.root):
        path = _safe_file(plan.root, plan.path)
        if path.read_bytes() != plan.original:
            raise ChangedOnDisk('Station changed since preview. Reload and preview again.')
        if not plan.changed:
            return SaveResult(path, False, None, revision(plan.original))
        backup = _backup(path, plan.original)
        temporary = None
        try:
            descriptor, name = tempfile.mkstemp(prefix='.alis-', suffix='.tmp', dir=path.parent)
            temporary = Path(name)
            with os.fdopen(descriptor, 'wb') as handle:
                handle.write(plan.replacement)
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temporary, stat.S_IMODE(path.stat().st_mode))
            if temporary.read_bytes() != plan.replacement:
                raise WriteError('Temporary-file verification failed; station was not changed.')
            _safe_file(plan.root, path)
            if path.read_bytes() != plan.original:
                raise ChangedOnDisk('Station changed during save. Reload and preview again.')
            os.replace(temporary, path)
            temporary = None
            written = path.read_bytes()
            if written != plan.replacement or _object(written) != intended:
                raise WriteError(f'Save verification failed. Original backup: {backup}. '
                                 'Inspect the station before restoring.')
            return SaveResult(path, True, backup, revision(written))
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
