
# ALIS v0.1.1 — Current Loadout Injector Parser

**Autonomic Loadout Integration System**

This revision is based on a real Loadout Injector `preset-loadout` folder using
schema **2.0.0-k2**.

ALIS is still intentionally **read-only** at this milestone.

## Current format supported

Point ALIS at the `preset-loadout` folder itself:

```text
preset-loadout/
├── .schema-version
├── hardpointdictionary_mounts.csv
├── hardpointdictionary_stations.csv
├── <platform>/
│   ├── DEFAULT.preset
│   ├── <other presets>.preset
│   ├── weaponstation0/
│   │   └── <station name>.json
│   └── ...
└── ...
```

The parser also retains compatibility with the earlier
`hardpointdictionary_weapon_mounts*.csv`,
`hardpointdictionary_hardpoint_sets*.csv`, and raw `.log` formats.

## Current CSV schemas

Mounts:

```text
owner,jsonKey,displayName,assetName,ammo,note_code,note_detail
```

Stations:

```text
aircraft,index,name,symmetryName,hardpointCount,precluding,owner
```

Despite the CSV field still being named `aircraft`, ALIS internally calls these
entries **platforms** because current Loadout Injector data can include
non-aircraft entities as well.

## Run

```powershell
python .\test_parser.py "C:\path\to\preset-loadout"
```

One platform only:

```powershell
python .\test_parser.py "C:\path\to\preset-loadout" --platform CAS1
```

`--aircraft CAS1` is retained as an alias.

Machine-readable output:

```powershell
python .\test_parser.py "C:\path\to\preset-loadout" --json
```

## Validation performed

When pointed at the folder root, ALIS verifies:

- every station JSON maps to a platform + station in the station CSV
- JSON filenames agree with station names
- every `allowedWeapons` entry resolves to either a `jsonKey` or `assetName`
- dictionary stations are not silently missing station JSON
- multiple JSON files inside one station folder are surfaced
- `STALE-KEY` rows are recognized
- schema version and preset count are reported

## Reference-folder validation

The supplied current `preset-loadout` reference validated with:

```text
Schema          : 2.0.0-k2
Platforms       : 32
Station metadata: 192
Station JSONs   : 192
Presets         : 147
Weapon mounts   : 986
STALE-KEY rows  : 1
CHECK rows      : 18
Validation      : 0 issue(s)
```

No source game/mod files are bundled with ALIS.

## Next milestone

v0.2 will add the first write path:

1. edit an `allowedWeapons` list in memory
2. validate every requested key
3. create an automatic backup
4. write via a temporary file + atomic replace
5. re-read and verify the result

Only after that write path is proven should the Flask API/UI be allowed to
modify station JSON.
