# ALIS v0.3 — Local Web Application

**Autonomic Loadout Integration System** · Nuclear Option / Loadout Injector

ALIS now opens in your browser. Select a platform and station, search the mount
catalog, toggle allowed mounts, review your changes, and save through the
backup-and-verification writer tested in v0.2.

## Start on Windows

Requires **Python 3.10+** and a current browser. Extract the ZIP and open
PowerShell in `ALIS_v0.3`, the folder containing `app.py`.

Install the web dependency once:

```powershell
python -m pip install -r requirements.txt
```

Start ALIS using your actual folder path:

```powershell
python .\app.py "C:\path\to\preset-loadout"
```

Your browser opens at **http://127.0.0.1:5000**. Keep the terminal open while
using ALIS; press **Ctrl+C** in that terminal to stop it. Closing the browser
alone leaves the local server running.

You can also double-click `Start_ALIS.bat` after installing the dependency. It
prompts for your `preset-loadout` folder. Paste the path and press Enter.

If port 5000 is already occupied:

```powershell
python .\app.py "C:\path\to\preset-loadout" --port 5050
```

Use `--no-browser` if you want to open the printed address yourself. If you use
an existing Python virtual environment, run both commands in that environment.

## Editing workflow

1. **Choose a platform** in the left panel. Its internal name is retained so it
   matches your mod's dictionary. The platform list has its own search field.
2. **Choose a station** in the middle panel. The list shows station indexes,
   hardpoint counts, and the number of allowed mounts. Symmetry groups and
   preclusion references are shown below it; click a related station to inspect it.
3. **Find mounts** using search and the owner filter. Search includes display
   name, JSON key, asset name, owner and dictionary notes. Switch between All
   mounts, Enabled and Pending views without changing the whitelist.
4. **Toggle the checkboxes.** The changes remain in memory. Pending additions
   and removals are marked, and the bottom bar shows a change count.
5. **Review changes.** The server validates the requested keys and the loaded
   file revision, then creates a preview. Inspect the additions/removals.
6. **Save station.** The same writer from v0.2 backs up the original bytes,
   replaces the file atomically, and reads it back to verify the result. The
   interface displays the backup path and refreshes the station from disk.

Use **Discard** to revert the draft to what was loaded. Switching stations or
reloading data prompts before discarding a draft. Closing/reloading the browser
also warns when a draft exists (browser behavior may vary).

An empty whitelist requires explicit consent in the review. Under strict
whitelist enforcement this can disable all mounts on that station.

A mount being present in the dictionary does not establish physical fit. ALIS
edits **allowedWeapons**, not a chosen loadout, station geometry or `.preset`.
Check your intended change in Nuclear Option after the affected platform reloads.

## Backups and restore

Click **Station backups** in the footer to see the selected station's history.
Choose **Review restore**, inspect the differences, and click **Restore station**.
Restoration creates another backup of the current file and restores the selected
backup byte for byte. It replaces any unsaved draft on that station when saved.

Backups are adjacent files named like:

```text
Center Pylon.json.20261003T010000123456Z.a1b2c3d4e5f6.bak
```

The command-line editor and parser from earlier releases remain included:

```powershell
python .\test_parser.py "C:\path\to\preset-loadout" --platform CAS1
python .\edit_station.py "C:\path\to\preset-loadout" --platform CAS1 --station 1 --add AAM1_single
```

The editor previews by default; add `--apply` to write. Use `--help` for search,
remove, restore, revision guards and JSON output.

## Data and save rules

- Uses your current `hardpointdictionary_mounts.csv`,
  `hardpointdictionary_stations.csv` and station JSON files.
- Preserves unrelated JSON fields, untouched entries and unresolved existing
  weapon keys. Unknown existing entries appear with an **UNRESOLVED** badge and
  can be explicitly removed.
- New keys must resolve unambiguously. STALE-KEY additions use the corrected
  write key; CHECK notes remain visible for inspection.
- Station paths, malformed JSON, duplicate fields, station filename mismatches
  and missing/ambiguous station files are checked by the writer.
- Every server preview has a single-use ticket and expires after 10 minutes.
  Changing the file outside ALIS invalidates the revision. Your draft stays
  available; close the review and reload data to load the current file.
- Reload data after the game/mod regenerates dictionaries or station files.
- Keep other editors from modifying a station during a save. ALIS serializes
  its own writers with `.alis-write.lock`; outside programs do not honor it.
  Revision checks reduce but cannot entirely eliminate external-write races.
- Use a local folder. Atomic replacement prevents partial JSON on ordinary
  local filesystems; it is not a power-loss transaction guarantee.
- Failed verification reports the original backup rather than overwriting the
  station a second time. Inspect the file before restoring.

## Local operation

The launcher binds to **127.0.0.1 only**. There is no login, cloud account,
database, external font/CDN, analytics, or remote upload in the application.
The browser assets are bundled. Internet is needed to install Flask initially;
normal operation reads and writes the selected local folder.

The API rejects non-local connections and untrusted host/origin headers, requires
a process-specific token for mutations, and runs without a debugger. Keep ALIS
local; this is not a remotely hosted application. See the official
[Flask documentation](https://flask.palletsprojects.com/en/stable/) for the framework.

## What this release includes

A dark terminal-style interface with platform/station navigation, catalog search,
owner filtering, whitelist checkboxes, change review, verified saves and backup
history. CSS layouts cover desktop and narrow screens.

Physical aircraft silhouettes and marker coordinates are **the next milestone**.
This release shows real station metadata and relationships without inventing
physical positions. No automatic mirror editing is performed.

## Verification and current limits

- **45 automated Python tests passed**: 30 writer tests and 15 API tests.
- API preview/save/exact restoration passed on **all 192 stations** in a copy of
  the supplied schema `2.0.0-k2` data (32 platforms, 986 mounts, 147 presets).
  Original file hashes and presets matched afterward; 0 validation issues.
- Interface DOM/event tests sent **real HTTP requests** to a temporary local
  server and verified search, owner/Enabled filtering, station selection,
  unsaved-draft protection, review, actual file save, exact restoration,
  outside-edit conflicts and empty-whitelist consent.
- **Rendered browser layout and native dialogs could not be inspected here**:
  the cloud browser blocked local preview URLs. Dialog rendering was stubbed
  for DOM tests. Windows, your browser's layout/behavior and in-game effects
  need a check on your machine.

Run Python tests:

```powershell
python -m unittest discover -s tests -v
```

Run the original full-folder writer verifier (uses a temporary copy):

```powershell
python .\verify_reference.py "C:\path\to\preset-loadout"
```

Optional developer DOM/event verification needs Node.js + `jsdom`. It is not
needed to run ALIS. This check expects the supplied 32-platform reference export
and an unused port 5053. It copies the folder before making any edits:

```powershell
npm install --no-save jsdom
node .\tests\verify_ui.cjs "C:\path\to\preset-loadout"
```

Set `ALIS_TEST_PYTHON` if the test should launch a specific Python interpreter.

## Troubleshooting

- **Missing Flask:** run the installation command with the same Python used to
  start ALIS. Use `python --version` to check the interpreter.
- **Invalid folder:** choose `preset-loadout` itself, not the game root or ZIP.
- **Permission/file-lock errors:** ALIS reports a failure. Make sure the target
  folder is writable and the station is not locked by another process.
- **Stale lock after an interrupted save:** check no ALIS write is active before
  deleting `.alis-write.lock` from the data root. Normal saves clean up the lock
  and temporary file. Existing backups are retained.
- **Lost server/session:** restart ALIS and reload its browser tab. Unsaved
  browser drafts are not persisted across restarts.

## Project layout

| Path | Purpose |
| --- | --- |
| `app.py` | Local launcher and automatic browser opening |
| `alis/web.py` | Inventory, station, preview and commit API |
| `alis/writer.py` | Existing safe save/restore engine |
| `templates/index.html` | Interface structure |
| `static/app.css` | Terminal visual style and responsive layouts |
| `static/app.js` | Search, drafts, review, save and restore interactions |
| `tests/` | Writer/API tests and optional DOM verification |

No game/mod exports or weapon datasets are bundled in this release.
