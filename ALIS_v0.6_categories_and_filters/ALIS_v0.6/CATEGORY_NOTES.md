# ALIS v0.6 category mapping notes

These are editable UI labels, not a game weapon specification or fit validator.
The supplied schema `2.0.0-k2` CSVs contain names, keys, owners and mount metadata;
they do not contain roles, seekers or vehicle classes. The implementation is in
`alis/categories.py`. Labels never change dictionaries, whitelist JSON or presets.

## Default guidance table

Stock labels match the full displayed model name followed by an optional count
or parenthetical suffix. A modded mount with a recognizable stock model receives
the same guidance hint. You can override it if the mod changes the model's behavior.
The source tooltip distinguishes stock labels, name/key hints and custom labels.

| Stock model | Default guidance | Reference |
| --- | --- | --- |
| MMR-S3, IRM-S1, IRM-S2 | IR | [Munitions table](https://nuclearoption.wiki.gg/wiki/Munitions) |
| AAM-29 Scythe, AAM-36 Scimitar | ARH | [Munitions table](https://nuclearoption.wiki.gg/wiki/Munitions) |
| AGM-48 | OPT | [AGM-48](https://nuclearoption.wiki.gg/wiki/AGM-48) |
| AGM-68 | OPT | [AGM-68](https://nuclearoption.wiki.gg/wiki/AGM-68) |
| ATP-1 | OPT | [ATP-1](https://nuclearoption.wiki.gg/wiki/ATP-1) |
| AT-145 | OPT | [AT-145](https://nuclearoption.wiki.gg/wiki/Ground_to_Ground_missile) |
| PAB-125 | OPT | [PAB-125](https://nuclearoption.wiki.gg/wiki/PAB-125) |
| PAB-250 | OPT | [PAB-250](https://nuclearoption.wiki.gg/wiki/PAB-250) |
| GPO-500 | OPT | [GPO-500](https://nuclearoption.wiki.gg/wiki/GPO-500) |
| PAB-80LR | OPT | [PAB-80LR](https://nuclearoption.wiki.gg/wiki/PAB-80LR) |
| PAB-250LR | OPT | [PAB-250LR](https://nuclearoption.wiki.gg/wiki/PAB-250LR) |
| GBM-500LR | OPT | [GBM-500LR](https://nuclearoption.wiki.gg/wiki/GBM-500LR) |
| Eyeball Mk.II | OPT | [Munitions table](https://nuclearoption.wiki.gg/wiki/Munitions) |
| AGR-18 Lynchpin, AGR-24 Kingpin | LAS | [Development notes](https://nuclearoption.wiki.gg/wiki/Development) |

Community wiki search-index extracts were checked on 2026-10-03. No page text,
statistics, images or game assets are bundled. Versions of the game or individual
mods can change the behavior, so this table is a starting point for labels.

## Name and key hints

Role and weapon type use conservative literal names/keys: AAM, AIM and IRM
families suggest A2A missiles; AGM, ATGM and bomb families suggest ground attack;
SAM suggests surface-to-air; AShM and ARM add anti-ship/anti-radiation roles.
Names explicitly identifying rockets, guns, howitzers, torpedoes, cargo, fuel,
reconnaissance and equipment identify their corresponding types. Carried vehicle
names take precedence over words such as SAM or gun inside the vehicle name.
Some arbitrary mod model names stay unclassified even if recognizable to players.

Explicit IR/infrared, ARH, SARH, optical, laser, INS, GPS and unguided tokens
can add guidance hints for missiles, bombs or rockets. Real-world model names
alone do not identify a mod's seeker. Directed energy lasers are DEW weapons;
they do not automatically receive the LAS guidance tag. Nominal A2G includes
families also fitted to ground/naval launchers, and is not a launcher constraint.
G2G, PRH and other tags can be assigned manually. Several guidance filters can
have zero automatic matches in this export.

## Stock platform labels

| Internal ID | Type | Nominal role |
| --- | --- | --- |
| CAS1 | Fixed wing | Attack |
| COIN | Fixed wing | Attack |
| trainer | Fixed wing | Trainer |
| VTOLTrainer1 | Fixed wing, VTOL | Multirole, trainer |
| Fighter1 | Fixed wing | Fighter |
| SmallFighter1 | Fixed wing, VTOL | Fighter |
| Multirole1 | Fixed wing | Multirole |
| EW1 | Fixed wing, VTOL | Electronic warfare |
| Darkreach | Fixed wing | Bomber |
| FastBomber1 | Fixed wing | Bomber |
| AttackHelo1 | Helicopter | Attack |
| UtilityHelo1 | Helicopter | Utility, transport |
| QuadVTOL1 | VTOL | Transport |

Fixed wing and VTOL overlap for jets with vertical/short takeoff capability.
VTOL availability can depend on load and fuel. Stock IDs follow the existing
friendly-name mappings; role/type references include the wiki
[aircraft catalog](https://nuclearoption.wiki.gg/wiki/Aircraft),
[Vagrant](https://nuclearoption.wiki.gg/wiki/VTOLTrainer1),
[Vortex](https://nuclearoption.wiki.gg/wiki/FS-20_Vortex),
[Ifrit](https://nuclearoption.wiki.gg/wiki/KR-67_Ifrit), and
[Medusa](https://nuclearoption.wiki.gg/wiki/EW-25_Medusa).

Modded platform labels use explicit internal-name hints such as CargoPlane,
Helicopter, Fighter, Attacker, UGV, tank/truck and LandingKraft. Unknown names
stay unclassified. A station owner is the modifying source, so it does not
determine whether a platform is stock or identify its role.

## Custom labels and persistence

Each item can have multiple tags per group. A custom save replaces all groups
for that item; an empty group is intentionally unclassified. Restoring automatic
labels removes that override. Weapon overrides retain an identity fingerprint
of owner, key, asset and display name. If these change, defaults are used and the
editor reports an ignored old override. Overrides for temporarily absent items
remain stored. Platform overrides use the exact internal ID.

Category saves patch a single item while preserving other saved labels. ALIS
rejects stale settings revisions and dictionary identities, creates exact backups
on replacement, and saves atomically. Backup names begin `categories.json.` and
end `.bak`. Categories are stored independently from themes and layout profiles.
