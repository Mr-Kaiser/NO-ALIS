# ALIS v0.7 — Bulk edits, draft recovery and aircraft references

**Autonomic Loadout Integration System** · Nuclear Option / Loadout Injector

Apply a station whitelist draft to several reviewed station files. Undo/redo
station and native preset edits, and recover unsaved drafts after a restart.
Your supplied aircraft drawings are now the default maps for all 13 stock
aircraft. Categories, themes, saved presets and custom layouts remain included.

## Start on Windows

Requires **Python 3.10+** and a current browser. Stop an older ALIS server with
**Ctrl+C**, extract this ZIP, then open PowerShell in `ALIS_v0.7`.

```powershell
python -m pip install -r requirements.txt
python .\app.py "C:\path\to\preset-loadout"
```

Your browser opens at **http://127.0.0.1:5000**. Keep the terminal open while
using ALIS. You can also double-click `Start_ALIS.bat` after installing Flask;
it prompts for the data folder. Choose `preset-loadout` itself.

If port 5000 is occupied, add `--port 5050`. Use `--no-browser` to open the
printed address yourself. Run installation and launch with the same Python.

Use the same data folder as v0.6. Station edits, backups and your saved names,
layouts and custom images remain available. No game/mod export is bundled in
this ZIP. Flask is the same dependency as v0.6; if it is already installed in
your Python environment, launch directly.

## Bulk station editing

Make a whitelist draft on a station, then click **Apply draft to stations**.
Choose the target station files on the same platform. Select all ready stations,
clear the selection, or select the source and its dictionary symmetry group.
Each row represents one station file, even when its map has several markers.

Click **Review bulk changes** to see the additions, removals and before/after
mount counts for every target. **Save reviewed stations** checks the source,
dictionaries and every target revision before writing. Each changed file gets
an exact backup; targets that already match are no-ops. Emptying any target
requires the separate empty-whitelist consent checkbox. The limit is 64 targets.

The batch applies the pending additions/removals; it preserves each target's
other mounts and JSON fields. It does not replace targets with the source's
complete whitelist. Unknown existing keys can be removed if they occur on the
source; missing copies on other targets are no-ops. Source changes are saved
only when the source is selected. Excluding it keeps that source draft open.

If a save fails, ALIS attempts to restore all changes from that batch. Its root
`.alis-bulk-journal.json` records exact originals and replacements before the
first target write. An unfinished batch blocks station and native preset saves.
Open **Bulk recovery**, inspect the listed files/backups, then **Restore batch
originals**. Recovery checks the record and current file revisions again.
Files changed outside the batch are retained and automatic recovery is refused;
inspect those files and their listed backups before restoring them manually.
Do not delete the recovery record to bypass a blocked batch.

After a process crash, a stale `.alis-write.lock` may remain. Stop every ALIS
server and confirm no save process is running before removing that abandoned
lock, then restart and use Bulk recovery. This deliberately requires checking
that the old process stopped. Batch saves are recoverable, but multiple files
cannot be replaced as one atomic filesystem transaction; power loss and
uncooperative external editors remain operational limits.

## Undo, redo and draft recovery

Use **Undo / Redo** above the whitelist or inside the preset editor. Histories
retain up to 100 changes for the open editor; short runs of typing coalesce.
Ctrl/Cmd+Z and Ctrl/Cmd+Shift+Z work outside text fields. Text fields retain the
browser's native text undo. Saving/loading a station or preset starts a fresh
history; layout, theme and category editors do not use this history.

Unsaved station patches and preset choices are stored automatically in this
browser for the selected data folder. **Drafts** shows the count. After reopening
ALIS, choose **Recover** to continue editing; recovery does not save game files.
If the source or dictionaries/whitelists changed, ALIS asks before reapplying the
draft to current files. Unavailable choices remain visible for repair. Changed
station names or preset station structure block recovery and retain the copy.
Recover, review, then save through the normal revision-checked workflow.

Leaving a station or closing a preset keeps its recovery copy. **Discard** on
a station deletes that station's recovery copy; returning to the loaded values
or saving also clears the editor's copy. **Delete recovery copy** removes an
old stored draft after confirmation. Another tab's newer copy is retained.

Use the same browser, host address, local port and data folder after a restart.
These copies use browser local storage, with a 100-draft / 2 MiB cap. Private
browsing, clearing site data, moving the data folder or changing ports can make
copies unavailable. A **!** indicator and button tooltip report storage failure;
in that case, keep the page open until reviewed changes are saved. Undo history
itself is not stored across restarts; recovering a draft starts a new history.
Drafts are a convenience, separate from exact saved-file backups.

## Weapon and platform categories

Use the **Role**, **Weapon type** and **Guidance** selectors below the weapon
search. Filters combine with owner, search and All / Enabled / Pending views:
for example, vanilla + A2A + MIS + IR. Every selected group must match; items
can have multiple tags in a group. Search also recognizes tags and their full
names. Counts in the Enabled and Pending tabs cover the complete station draft.
Changing filters never clears hidden selections. **Clear filters** restores the
All view and clears the search, owner and category selectors.

- Roles: A2A, A2G, ASHM, ARM, SAM, G2G, REC, EW and utility.
- Weapon types: MIS, BMB, RKT, GUN, DEW, POD, FUEL, CARGO, TORP and SENSOR.
- Guidance: IR, ARH, SARH, OPT, LAS, PRH, INS, GPS and UNG.

The platform sidebar filters **Vehicle type** (fixed wing, VTOL, helicopter,
ground vehicle or ship) and **Role** (fighter, attack, bomber, multirole,
electronic warfare, transport, utility or trainer). Filtering the sidebar leaves
the selected platform and its station draft open even if its row is hidden.
Fixed wing and VTOL overlap for jets with vertical/short takeoff capability.
Each filter includes **Unclassified**, meaning that group has no tags.

Open **Edit tags** on a weapon row or beside the selected platform's tags.
The header **Categories** button opens a searchable catalog editor. Check any
combination of tags, then **Save categories**. Uncheck all tags in a group to
leave it unclassified. **Use automatic labels** restores that item's defaults
when saved. Labels persist in the data folder's `.alis/categories.json` and
follow the same revision check, atomic save and exact-backup approach as the
other ALIS settings. They can be saved alongside an independent whitelist draft.

The supplied dictionaries have no category fields. Defaults combine a small
stock model table with conservative name/key hints. Hover badges for the source;
the editor shows whether labels are automatic or custom. Unknown guidance stays
unclassified. SARH and other available labels can have zero automatic matches.
Real-world names such as AIM-120 or R-27 do **not** establish a mod's seeker type.
Nominal weapon roles do not guarantee launcher compatibility or target support;
verify mod behavior and adjust tags as needed. A stock model carried in a modded
mount keeps its stock guidance hint unless you override it. Carried SAM vehicles
are cargo; directed energy lasers use DEW rather than the LAS guidance tag.
Custom weapon labels are ignored if their dictionary owner, name or asset changes,
so reused keys do not silently inherit old labels. See `CATEGORY_NOTES.md` for
mapping sources and limits. Existing names, layouts, images, themes and native
loadout presets remain available when using the same data folder.

## Themes

Click **Themes** in the header. Choose **ALIS Original**, **Amber Terminal**,
**Midnight Blue**, or **Daylight** to preview it immediately.

**Copy as custom** creates a named editable palette. Editing a built-in color
also creates a custom copy automatically. Edit page/panel backgrounds, borders,
main/secondary text, accent, warning, error and symmetry colors. A contrast
readout helps you judge small-text readability; button/selected-marker text
automatically chooses a contrasting color for the accent.

Click **Save theme** to persist the palette and active selection. **Cancel**
restores the last saved theme. You can keep up to 12 custom themes. **Remove
custom** stages removal of the selected custom palette; **Save theme** applies
that change. Built-in palettes remain available.

Theme settings live in `preset-loadout/.alis/ui.json` and survive restarts and
ALIS upgrades when you keep using that data folder. Previous settings are
backed up before changes. Theme saves do not change game files or your pending
whitelist/preset drafts.

## Native loadout presets

Select a platform, then click **Loadout presets**. This editor works with that
platform's `.preset` files alongside its station folders.

1. Load an existing preset, choose **Save as copy**, or choose **New blank**.
2. Enter a name and fuel percentage, then select one allowed mount or **Empty**
   for each station group. Multiple physical hardpoints in a group share that
   selection, matching the supplied native preset format.
3. Keep the source livery reference to preserve it. The advanced livery field
   accepts the native reference string; an empty value leaves it unspecified.
   ALIS does not provide a livery catalog or image preview.
4. Click **Review preset**. The review names the file, shows mount changes and
   fuel, and states whether it will create a file or back up an existing one.
5. Click **Save preset**. ALIS writes and verifies the native file. New files
   are created without replacing an existing file; updates keep an exact backup.

Changing a loaded preset's name saves it as a new copy. A duplicate name is
refused unless that existing preset was loaded for editing. Filenames follow
Windows-safe naming rules. You can edit `DEFAULT` through the same reviewed
backup flow.

The native format is based on all 147 files in your supplied export: `Fuel`,
`Livery`, matching `Stations` name/key entries and `Hardpoints` arrays. Copies
and updates preserve unknown fields and any existing `Vanilla` flag. New blank
presets use those four core fields and do not invent optional metadata.
Unchanged valid presets remain byte-for-byte unchanged when saved.

Selections use the **saved station whitelists**. To use a newly allowed mount,
first save the whitelist edit, then reopen/reload the preset editor. Pending
whitelist drafts are kept separate and can remain unsaved while a preset is
saved. Preset changes also remain drafts until reviewed and saved.

ALIS rejects unavailable/unknown mounts and simultaneously occupied precluding
stations. It does not silently clear your choices or automatically mirror
symmetry groups. The supplied export contains **six unavailable selections
across five existing presets**; these remain readable and are flagged for repair.
Choose an available mount or Empty, or update the station whitelist separately.

Station names/order and both native arrays must match the current dictionary.
Malformed presets are refused for editing; you can still choose another preset
or create a new one. A preview expires after 10 minutes and is single use.
Changing the source preset, target file, dictionaries or whitelists after review
blocks the save and keeps the draft available. Return to editing, close/reopen
or load the preset again to refresh its catalog.

Preset backups are adjacent files named like
`My loadout.preset.TIMESTAMP.ID.bak`. The current UI has no preset-backup restore
menu; to restore one, stop ALIS and copy that backup over its original `.preset`
file, then restart. The footer's **Station backups** handles whitelist JSON
backups only. New file creation requires hard-link support on the local
filesystem (including ordinary NTFS); an unsupported filesystem reports a
failure instead of falling back to a partial write.

Load your new preset in Nuclear Option after the injector refreshes its files.
Native file structure, saves and backups were tested here; in-game loading and
actual mount fit still need a check on your machine.

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
selection. Switching stations warns before leaving a draft; its recovery copy remains
available when browser storage succeeds. Emptying a
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

Your supplied drawings are bundled unchanged: **19 images, 20 selectable views,
13 stock aircraft**. Top views load by default. **Bundled reference** offers
front views where supplied. The Medusa's combined plate uses a viewport crop
for its top view; the complete plate remains selectable. `Compass_top.png` is
actually a front view, so the Compass uses `TA30-Top.png` as its default.
The Ibis and Vagrant originals are only 100×100 and 80×105, respectively, so
they look softer when enlarged. ALIS does not synthesize replacement images.

Existing saved custom profiles continue to take precedence. To adopt the new
image and marker layout, open **Edit layout → Use bundled default → Save layout**.
The button stages a complete default profile (name, image, shape and markers);
Cancel keeps your saved profile. Selecting only a **Bundled reference** view
keeps your current markers and clears the checked status, so reposition them
for a front view. Uploading a custom image or removing the image clears any
bundled crop and remains supported.

Stock marker positions are still labeled **SCHEMATIC / APPROXIMATE**. They have
been aligned by eye to the drawings, but the supplied CSV has no physical
coordinates. Verify their locations in the layout editor as needed. Modded
platforms without a bundled reference retain their saved profile or blank map.

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

On temporary copies of the supplied schema `2.0.0-k2` export:

- Bulk tests cover exact backups, no-ops, aliases, source/target/dictionary
  conflicts, empty consent, rollback failures, outside-edit preservation,
  record/backup tampering, API token/origin checks and single-use tickets.
  An abrupt subprocess exit retained its recovery record and exact backups;
  originals were recovered after removing the confirmed abandoned lock.
- The v0.7 real-HTTP DOM check covers station and preset Undo/Redo, page-restart
  recovery, changed-file recovery decline/accept, storage quota failure, bulk
  review/save/conflict/source exclusion, bundled top/front references, explicit
  default resets, custom profile persistence and the Medusa crop.
- All 19 packaged aircraft images match the uploaded ZIP byte for byte.

- **141 Python tests passed**: 30 writer, 15 web API, 16 layout/profile,
  23 native preset, 13 theme, 15 category, 22 bulk/recovery and 7 reference tests.
- Native read/copy/review/create/update/exact-backup checks passed for all
  **147 presets**. The **142 valid originals** were byte-exact no-ops; six
  unavailable selections in five files were flagged and the originals retained.
- All four built-in themes saved and survived restart. Custom palette validation,
  conflicts, backups, removal and failed writes were covered by Python tests.
- All 986 weapon and 32 platform category groups validated. Custom labels on
  seven representative mounts and all 32 platforms survived restart, had exact
  backups, and reverted to automatic labels without changing any game files.
- Existing station API preview/save/exact restoration passed on all **192
  stations**. Profiles persisted for all 32 platforms, with 13 complete stock
  schematics. Original hashes and presets were preserved, with zero validation
  issues.
- DOM/event checks made real HTTP requests for category filters and edits,
  hidden-draft preservation, custom tag save/revert/reload/exact backup, platform
  labels and stale-category conflicts. They also checked the existing
  theme live preview/custom edit/save/cancel/reload, blank/copy preset creation,
  overwrite backup, preclusion rejection, catalog-change rejection, malformed
  DEFAULT recovery, and preservation of an independent whitelist draft.

Rendered themes, browser layout, native dialogs, pointer geometry and image
rendering were not inspected here because local browser preview was blocked.
Dialogs were stubbed in DOM tests. Windows filesystem behavior and in-game
preset loading also need local verification. The native schema was checked
against your supplied files; injector source retrieval was unavailable here.

```powershell
python -m unittest discover -s tests -v
python .\verify_reference.py "C:\path\to\preset-loadout"
python -m tests.verify_reference_api "C:\path\to\preset-loadout"
python -m tests.verify_presets "C:\path\to\preset-loadout"
python -m tests.verify_categories "C:\path\to\preset-loadout"
```

Reference checks edit only temporary copies. The station/API reference check
expects a complete export matching the built-in profiles. Optional DOM checks
need Node.js, `jsdom`, the supplied 32-platform export, and free ports 5053/5054:

```powershell
npm install --no-save jsdom
node .\tests\verify_ui.cjs "C:\path\to\preset-loadout"
node .\tests\verify_v07_ui.cjs "C:\path\to\preset-loadout"
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
layouts, `.alis/ui.lock` for themes, or `.alis/categories.lock` for categories.
Normal saves remove their locks and temporary files. Backups remain.
Restart ALIS after a lost session and use **Drafts** in the same browser/address
to recover stored station or preset edits. For an unfinished bulk batch, retain
its recovery record and use **Bulk recovery** after clearing an abandoned lock
only when all old ALIS processes are stopped.

If theme settings are corrupt, stop ALIS and restore `.alis/ui.json` from one
of its backups. Moving only that file aside resets appearance to ALIS Original
on the next start; `.alis/platforms.json` contains your separate layouts/images.
For corrupt category settings, stop ALIS and restore `.alis/categories.json`
from its backup, or move only that file aside to return to automatic labels.

| Path | Purpose |
| --- | --- |
| `app.py`, `Start_ALIS.bat` | Local launch |
| `alis/writer.py` | Safe station save and restore |
| `alis/web.py` | Browser API |
| `alis/bulk.py`, `static/bulk.js` | Reviewed batch edits, rollback and recovery |
| `static/drafts.js` | Undo/redo and browser draft recovery |
| `alis/references.py`, `config/references.json`, `static/references/` | Bundled aircraft images and views |
| `alis/layouts.py` | Separate profile validation and persistence |
| `alis/presets.py` | Native loadout format, validation, review and safe writes |
| `alis/themes.py` | Built-in palettes and persistent custom theme settings |
| `config/platforms.json` | Stock names and approximate coordinates |
| `static/silhouettes/` | Original schematic SVGs |
| `templates/`, `static/app.*`, `static/extras.js` | UI and interactions |
| `alis/categories.py`, `static/categories.js`, `CATEGORY_NOTES.md` | Category labels, filters and mapping notes |
| `tests/`, `verify_reference.py` | Automated checks |
