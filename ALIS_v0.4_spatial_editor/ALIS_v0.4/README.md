# ALIS v0.4 — Spatial station editor

**Autonomic Loadout Integration System** · Nuclear Option / Loadout Injector

Click a station marker on a schematic to open its mount whitelist. This release
adds friendly stock platform names, 13 stock schematics, and a layout editor for
stock or modded platforms. The v0.2 backup, revision check and verified save
engine remains in use.

## Start on Windows

Requires **Python 3.10+** and a current browser. Stop an older ALIS server with
**Ctrl+C**, extract this ZIP, then open PowerShell in `ALIS_v0.4`.

```powershell
python -m pip install -r requirements.txt
python .\app.py "C:\path\to\preset-loadout"
```

Your browser opens at **http://127.0.0.1:5000**. Keep the terminal open while
using ALIS. You can also double-click `Start_ALIS.bat` after installing Flask;
it prompts for the data folder. Choose `preset-loadout` itself.

If port 5000 is occupied, add `--port 5050`. Use `--no-browser` to open the
printed address yourself. Run installation and launch with the same Python.

Use the same data folder as v0.3. Existing station edits and adjacent backups
remain available. No game/mod export is bundled in this ZIP.

## Choose and edit a station

1. Search platforms by either friendly name or internal ID. The platform list
   retains its scrollbar. Internal IDs stay visible and remain the identifiers
   used for files and API requests.
2. Click a numbered marker, or a station in the scrollable list below the map.
   The marker number is the CSV station index. Enter/Space also activates a
   focused marker.
3. Search mounts, filter owners, and toggle allowed mounts. All, Enabled and
   Pending views filter the catalog without changing your whitelist.
4. Click **Review changes**, inspect the additions/removals, then **Save
   station**. ALIS checks the loaded file revision, backs up its exact bytes,
   replaces it atomically, and rereads the saved result.

Changes stay in a browser draft until saved. **Discard** restores the loaded
selection. Switching stations warns before discarding a draft. Emptying a
whitelist requires a separate consent checkbox during review.

The map highlights the selected station in cyan, other stations in its symmetry
group in blue, and stations it precludes with a dashed amber outline. These are
dictionary relationships. ALIS does not automatically mirror whitelist edits
or treat these relationships as a currently equipped loadout.

**Multiple markers with the same index open the same station whitelist.**
For example, the Brawler's paired internal guns have two markers labeled `00`.
Separate markers do not create separate station files.

ALIS edits `allowedWeapons`, not physical geometry, weapon fit or `.preset`
files. Check your mount changes in Nuclear Option after the platform reloads.

## Layout editor

Stock positions are labeled **SCHEMATIC / APPROXIMATE**. The supplied CSV has no
physical coordinates, so these original silhouettes and markers are navigation
aids. They are not measured aircraft diagrams or extracted game assets.

Choose **Edit layout** to:

- Change the display name without renaming the internal platform or its files.
- Pick a built-in silhouette or attach a top-down **PNG, JPEG or WebP** image
  up to **2 MiB**. Images fit inside a square canvas; orient the nose/front up.
- Choose a station and marker, then drag it, click the canvas to place it, or
  enter **X/Y percentages**. The top-left is `0%, 0%` and bottom-right is
  `100%, 100%`. Add/remove markers as needed, up to 16 per station.
- Check **I checked this layout against my reference** after validating the
  positions. The main view then says **USER CHECKED**. Moving markers or
  changing the silhouette/image clears that checkbox.

The editor reports station coverage. Unmapped stations remain accessible in the
station list. Unknown modded platforms start with their internal name and a
blank canvas so you can supply their names and layouts.

**Save layout** stores only ALIS settings, separately from weapon whitelists.
You can save a layout while keeping an unsaved weapon draft. **Cancel** warns
before discarding layout changes. If another session updates the profiles,
ALIS rejects the stale save and keeps your layout draft available. Close the
editor and reload data to use the current settings.

Names, marker positions and custom images are stored together in
`preset-loadout/.alis/platforms.json`. They survive server restarts and future
ALIS upgrades when you use the same data folder. Existing settings are backed
up before subsequent changes; those backups are beside `platforms.json`.
The current editor does not expose a profile backup restoration menu.

If a station index disappears or its name changes in a regenerated dictionary,
its old markers are omitted and the layout loses its checked status. Reload
data and remap it against the updated reference. If you regenerate or move the
entire data folder, retain `.alis` to preserve your layouts.

## Stock display names

Verified using the Nuclear Option community wiki's Dev Name fields. Names are
editable if your game/mod uses different labels. Modded names are not guessed.

| Internal ID | Display name |
| --- | --- |
| CAS1 | A-19 Brawler |
| COIN | CI-22 Cricket |
| trainer | T/A-30 Compass |
| VTOLTrainer1 | VT-7 Vagrant |
| Fighter1 | FS-12 Revoker |
| SmallFighter1 | FS-20 Vortex |
| Multirole1 | KR-67 Ifrit |
| EW1 | EW-25 Medusa |
| Darkreach | SFB-81 Darkreach |
| FastBomber1 | Alkyon AB-4 |
| AttackHelo1 | SAH-46 Chicane |
| UtilityHelo1 | UH-90 Ibis |
| QuadVTOL1 | VL-49 Tarantula |

Source: [Nuclear Option aircraft wiki](https://nuclearoption.wiki.gg/wiki/Aircraft)
and its individual aircraft pages, including
[A-19 Brawler](https://nuclearoption.wiki.gg/wiki/A-19_Brawler),
[FS-12 Revoker](https://nuclearoption.wiki.gg/wiki/FS-12_Revoker),
[T/A-30 Compass](https://nuclearoption.wiki.gg/wiki/T/A-30_Compass),
[Alkyon AB-4](https://nuclearoption.wiki.gg/wiki/Alkyon_AB-4),
[VT-7 Vagrant](https://nuclearoption.wiki.gg/wiki/VTOLTrainer1),
[KR-67 Ifrit](https://nuclearoption.wiki.gg/wiki/KR-67_Ifrit),
[SFB-81 Darkreach](https://nuclearoption.wiki.gg/wiki/SFB-81_Darkreach),
[SAH-46 Chicane](https://nuclearoption.wiki.gg/wiki/SAH-46),
[CI-22 Cricket](https://nuclearoption.wiki.gg/wiki/CI-22_Cricket),
[EW-25 Medusa](https://nuclearoption.wiki.gg/wiki/EW-25_Medusa),
[UH-90 Ibis](https://nuclearoption.wiki.gg/wiki/UH-90_Ibis),
[FS-20 Vortex](https://nuclearoption.wiki.gg/wiki/FS-20_Vortex),
[VL-49 Tarantula](https://nuclearoption.wiki.gg/wiki/VL-49_Tarantula).

## Station backups and save rules

Click **Station backups** in the footer, choose **Review restore**, then
**Restore station**. Restoring creates a backup of the current file and restores
the selected backup byte for byte. Saving a restoration replaces the current
unsaved weapon draft.

- Untouched entries, unrelated JSON fields and unresolved existing keys are
  preserved. Unresolved keys appear with a badge and can be explicitly removed.
- New mount keys must resolve unambiguously. STALE-KEY additions use the
  corrected write key; CHECK notes remain visible.
- Missing/ambiguous station files, name/path mismatches, malformed JSON,
  duplicate fields and symlinked target paths are rejected.
- Reviews expire after 10 minutes and are single use. Changes made outside ALIS
  invalidate the loaded revision; reload data before trying again.
- ALIS serializes its own writers. Other programs do not honor its locks;
  revision checks reduce but cannot eliminate an external-write race.
- Use a local writable folder. Atomic replacement avoids partial JSON on
  ordinary local filesystems; it is not a power-loss transaction guarantee.

The CLI tools remain available:

```powershell
python .\test_parser.py "C:\path\to\preset-loadout" --platform CAS1
python .\edit_station.py "C:\path\to\preset-loadout" --platform CAS1 --station 1 --add AAM1_single
```

The editor previews by default; add `--apply` to write. Use `--help` for options.

## Verification

On a copy of the supplied schema `2.0.0-k2` export:

- **61 Python tests passed**: 30 writer, 15 web API and 16 layout/profile tests.
- Writer add/repeat/remove/exact restore passed on all **192 stations**.
- Web API preview/save/exact restore passed on all **192 stations**. Profiles
  saved and survived application restarts for all **32 platforms**; all 13
  built-in stock profiles matched the export's station names and covered every
  stock station.
- Original game file hashes and **147 presets** were preserved; **986 mounts**
  loaded and validation reported zero issues. The input folder was untouched.
- DOM/event tests made real HTTP requests for name/ID search, SVG selection,
  whitelist save/restore/conflict, empty consent, numeric marker edit/add/remove,
  profile save/reload/conflict, mod platform mapping, and independent drafts.

Rendered browser layout, pointer geometry, image decoding and native dialogs
could not be inspected here because local browser preview was blocked. Dialogs
were stubbed in DOM tests. Verify dragging, custom images and the rendered
interface in your browser; Windows and in-game effects also need a local check.

```powershell
python -m unittest discover -s tests -v
python .\verify_reference.py "C:\path\to\preset-loadout"
python -m tests.verify_reference_api "C:\path\to\preset-loadout"
```

The last check expects a complete export matching the built-in profiles. Both
reference verifiers edit only temporary copies. Optional DOM checks need
Node.js and `jsdom` and expect the supplied 32-platform export and free port 5053:

```powershell
npm install --no-save jsdom
node .\tests\verify_ui.cjs "C:\path\to\preset-loadout"
```

Set `ALIS_TEST_PYTHON` to launch a specific interpreter for the DOM check.

## Troubleshooting and local operation

The server binds to **127.0.0.1 only**, rejects non-local connections and
untrusted host/origin headers, requires a session token for saves, and has no
debugger. Assets are bundled. Internet is needed for the initial Flask install;
normal operation uses your selected local folder. Custom images stay local.

For missing Flask, install requirements with the interpreter used to launch.
For permission/lock errors, ensure the data folder is writable and no other
program is locking the target file.

After an interrupted save, check that no ALIS write is active before removing
an abandoned `.alis-write.lock` in the data root or `.alis/profiles.lock` for
layouts. Normal saves remove their locks and temporary files. Backups remain.
Restart ALIS and reload the browser after a lost session; unsaved browser drafts
do not survive a restart.

| Path | Purpose |
| --- | --- |
| `app.py`, `Start_ALIS.bat` | Local launch |
| `alis/writer.py` | Safe station save and restore |
| `alis/web.py` | Browser API |
| `alis/layouts.py` | Separate profile validation and persistence |
| `config/platforms.json` | Stock names and approximate coordinates |
| `static/silhouettes/` | Original schematic SVGs |
| `templates/`, `static/app.*` | UI and interactions |
| `tests/`, `verify_reference.py` | Automated checks |
