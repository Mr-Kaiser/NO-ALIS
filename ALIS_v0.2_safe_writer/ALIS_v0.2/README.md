# ALIS v0.2 — Safe Station Writer

**Autonomic Loadout Integration System** · Loadout Injector tools for Nuclear Option

v0.2 adds previewable station edits, automatic backups, atomic replacement,
verification, and exact backup restoration. It includes the working v0.1.1
parser. The browser interface is the next milestone; this release uses commands.

## Quick start (Windows / PowerShell)

Requires **Python 3.10 or newer**. No third-party packages or database needed.
Extract this ZIP and open PowerShell in `ALIS_v0.2` (the folder containing
`edit_station.py`). Set your real folder path once:

```powershell
$preset = "C:\path\to\preset-loadout"
```

List a platform's station indexes using the same parser command as before:

```powershell
python .\test_parser.py $preset --platform CAS1
```

Search for the exact weapon mount key:

```powershell
python .\edit_station.py $preset --find-weapon "MMR-S3"
```

Preview adding one mount to station 1. `AAM1_single` is a sample dictionary key:

```powershell
python .\edit_station.py $preset --platform CAS1 --station 1 --add AAM1_single
```

Preview output shows the target file, counts, additions/removals, and revision.
**Preview does not write anything.** Once the preview is right, repeat with
`--apply`:

```powershell
python .\edit_station.py $preset --platform CAS1 --station 1 --add AAM1_single --apply
```

A successful save prints the backup path and `Saved and verified.` Repeating
that add is a no-op: it does not duplicate the weapon or create another backup.

Remove a mount:

```powershell
python .\edit_station.py $preset --platform CAS1 --station 1 --remove AAM1_single
```

Again, add `--apply` to save. Multiple edits can be combined in one operation:

```powershell
python .\edit_station.py $preset --platform CAS1 --station 1 --add AAM1_single --add AAM2_single --remove bomb_500_glide_single
```

Only use keys you intend to edit. A key from the dictionary identifies a known
mount; it does **not** prove that mount fits a particular station. This tool
edits the **allowed weapon whitelist**, not a selected loadout or a `.preset`.
It does not alter station geometry, symmetry, preclusions, or the dictionary.
Game-side compatibility and appearance still need to be checked in Nuclear
Option after the affected platform reloads.

## Restore the original station

Every real save creates an adjacent, unique backup such as:

```text
Center Pylon.json.20261002T170000123456Z.a1b2c3d4e5f6.bak
```

Copy the actual backup path printed by ALIS; do not type the example timestamp.
Preview restoration:

```powershell
python .\edit_station.py $preset --platform CAS1 --station 1 --restore "C:\actual\path\to\Center Pylon.json.TIMESTAMP.ID.bak"
```

Add `--apply` to restore. ALIS verifies that the backup belongs to that station,
backs up the current version, and restores the selected backup **byte for byte**.
Old backups are retained, so restoring can itself be undone.

## Save behavior

- Only explicitly requested mount additions/removals change `allowedWeapons`.
  Other JSON fields, weapon order, and unresolved existing keys are retained.
- New weapon keys must resolve unambiguously in the current dictionary. Search
  is case-insensitive; weapon identifiers themselves are case-sensitive.
- `STALE-KEY` additions use the row's corrected `assetName`. Normalization is
  limited to that requested mount; unrelated stale entries remain untouched.
- Removing an unknown key already present in the station is allowed, for
  cleanup after uninstalling a mod. Unknown new keys or removal typos are refused.
- Emptying a nonempty whitelist requires `--allow-empty`. Under strict whitelist
  enforcement, an empty list may disable all mounts for that station.
- Malformed JSON, duplicate JSON fields, missing/ambiguous station files,
  filename mismatches and linked station paths are refused.
- Original bytes are backed up and verified before a temporary file in the same
  folder is written, flushed, verified, and atomically substituted. The final
  file is read again and verified against the intended document.
- A SHA-256 revision detects changes since preview. Use `--expect-revision`
  with the printed revision to bind a later CLI save to a specific preview:

```powershell
python .\edit_station.py $preset --platform CAS1 --station 1 --add AAM1_single --expect-revision "PASTE_64_CHARACTER_REVISION" --apply
```

Without that option, repeating a CLI command calculates a fresh plan; its own
commit still checks for intervening changes. `--json` gives structured output
for integration. Failures return exit code 1; invalid arguments return 2.

## Operating notes

Keep other editors from changing the same station during a save. ALIS serializes
its own writers with `.alis-write.lock`, but other applications do not honor
that lock. Revision checks narrow the external-write race; they cannot remove
it completely. Use a local folder. Atomic replacement on ordinary local
filesystems prevents partially written JSON; it is not a power-loss guarantee.

If the process is interrupted, a backup or `.alis-*.tmp` file may remain.
A stale `.alis-write.lock` can also remain. Only remove that lock after checking
that no ALIS write process is active. A normal completed or failed save cleans
up its temporary file and lock. Existing backups are never overwritten.

If post-save verification fails, ALIS reports the original backup path and does
not automatically overwrite the station again. Inspect the station and use the
restore command if appropriate. Windows file locks, permissions, or disk space
can prevent a save; an error is reported instead of a success message.

## Verification

The included suite exercises previews, add/remove, alias handling, empty-list
protection, byte-exact restores, backups, malformed inputs, revision conflicts,
write failures, symlinks and preservation of unrelated JSON data:

```powershell
python -m unittest discover -s tests -v
```

The reference verifier tests every station on a **temporary copy** of the input:

```powershell
python .\verify_reference.py $preset
```

Validation of the supplied schema `2.0.0-k2` folder:

- 32 platforms, 192 stations, 986 weapon mounts, 147 presets.
- Every station passed add, repeated add, remove, and exact restoration.
- All original file hashes and presets matched afterward; 0 validation issues.
- 30 automated tests passed on Python 3.12/Linux. Windows and in-game checks
  remain to be performed on your machine.

No game/mod exports are bundled. Legacy CSV/log parsing is retained from v0.1.1;
this release's full write validation targets the supplied current format.

## Source layout

| File | Responsibility |
| --- | --- |
| `test_parser.py` | Read-only inventory and validation |
| `edit_station.py` | Search, previews, save and restore commands |
| `alis/dictionary.py` | CSV/log parsing |
| `alis/models.py` | Platform, station and mount data |
| `alis/stations.py` | Station discovery and validation |
| `alis/writer.py` | Edit plans, backups, atomic saves, revision checks |
| `tests/test_writer.py` | Automated behavior and failure tests |
| `verify_reference.py` | Full-folder verification on a temporary copy |

The future local Flask interface can call `plan_edit()` / `commit()` directly,
with the same save safeguards and revision checks.
