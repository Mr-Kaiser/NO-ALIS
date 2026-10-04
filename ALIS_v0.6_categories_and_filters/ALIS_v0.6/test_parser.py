
from __future__ import annotations

import argparse
import json
from pathlib import Path

from alis import load_dictionary, load_repository, scan_preset_loadout, validate_station_configs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="ALIS v0.2 read-only Loadout Injector parser/validator."
    )
    parser.add_argument(
        "source",
        type=Path,
        help=(
            "Recommended: path to the current preset-loadout directory. "
            "Also accepts either dictionary CSV or a legacy hardpointdictionary.log."
        ),
    )
    parser.add_argument(
        "--preset-root",
        type=Path,
        help="Optional preset-loadout directory when source is an individual CSV/log.",
    )
    parser.add_argument(
        "--platform",
        "--aircraft",
        dest="platform",
        help="Only print one platform by internal name (case-insensitive).",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON summary.")
    return parser.parse_args()


def select_platforms(dictionary, requested: str | None):
    platforms = dictionary.platforms

    if not requested:
        return [platforms[name] for name in sorted(platforms)]

    folded = requested.casefold()
    matches = [p for name, p in platforms.items() if name.casefold() == folded]
    if not matches:
        raise SystemExit(
            f"Platform not found: {requested!r}. "
            f"Known platforms: {', '.join(sorted(platforms))}"
        )
    return matches


def load_inputs(args):
    source = args.source.expanduser().resolve()

    if source.is_dir() and (source / ".schema-version").exists():
        snapshot = load_repository(source)
        return (
            snapshot.dictionary,
            snapshot.station_configs,
            snapshot.schema_version,
            snapshot.preset_count,
            snapshot.issues,
        )

    dictionary = load_dictionary(source)
    preset_root = args.preset_root.expanduser().resolve() if args.preset_root else None
    configs = scan_preset_loadout(preset_root) if preset_root else {}
    issues = validate_station_configs(dictionary, configs, preset_root) if preset_root else []
    schema = None
    preset_count = 0
    if preset_root:
        schema_path = preset_root / ".schema-version"
        if schema_path.exists():
            schema = schema_path.read_text(encoding="utf-8-sig").strip()
        preset_count = sum(1 for _ in preset_root.glob("*/*.preset"))

    return dictionary, configs, schema, preset_count, issues


def build_summary(dictionary, configs, schema, preset_count, issues, platforms):
    aliases = dictionary.weapon_aliases

    output = {
        "schema_version": schema,
        "platform_count": len(dictionary.platforms),
        "station_metadata_count": sum(len(p.stations) for p in dictionary.platforms.values()),
        "station_json_count": sum(
            len(items)
            for platform in configs.values()
            for items in platform.values()
        ),
        "preset_count": preset_count,
        "weapon_mount_count": len(dictionary.weapons),
        "stale_key_count": sum(w.is_stale_key for w in dictionary.weapons),
        "check_note_count": sum(w.note_code.upper() == "CHECK" for w in dictionary.weapons),
        "validation_issue_count": len(issues),
        "validation_issues": [
            {
                "severity": i.severity,
                "code": i.code,
                "message": i.message,
                "path": i.path,
            }
            for i in issues
        ],
        "platforms": [],
    }

    for platform in platforms:
        p_out = {
            "internal_name": platform.internal_name,
            "station_count": len(platform.stations),
            "stations": [],
        }

        for station in platform.sorted_stations():
            station_configs = configs.get(platform.internal_name, {}).get(station.station_index, [])
            allowed = [
                key
                for config in station_configs
                for key in config.allowed_weapons
            ]

            p_out["stations"].append({
                "index": station.station_index,
                "name": station.station_name,
                "symmetry_name": station.symmetry_name,
                "hardpoint_count": station.hardpoint_count,
                "precluding": list(station.precluding),
                "owner": station.owner,
                "allowed_weapon_count": len(allowed),
                "unknown_allowed_weapon_keys": sorted({k for k in allowed if k not in aliases}),
            })

        output["platforms"].append(p_out)

    return output


def print_report(summary):
    print("ALIS // AUTONOMIC LOADOUT INTEGRATION SYSTEM")
    print("READ-ONLY PARSER / VALIDATOR")
    print("=" * 64)
    print(f"Schema          : {summary['schema_version'] or 'unknown'}")
    print(f"Platforms       : {summary['platform_count']}")
    print(f"Station metadata: {summary['station_metadata_count']}")
    print(f"Station JSONs   : {summary['station_json_count'] or 'not scanned'}")
    print(f"Presets         : {summary['preset_count'] or 'not scanned'}")
    print(f"Weapon mounts   : {summary['weapon_mount_count']}")
    print(f"STALE-KEY rows  : {summary['stale_key_count']}")
    print(f"CHECK rows      : {summary['check_note_count']}")
    print(f"Validation      : {summary['validation_issue_count']} issue(s)")
    print()

    if summary["validation_issues"]:
        for issue in summary["validation_issues"]:
            path = f" [{issue['path']}]" if issue["path"] else ""
            print(f"! {issue['severity'].upper()} {issue['code']}: {issue['message']}{path}")
        print()

    for platform in summary["platforms"]:
        print(f"{platform['internal_name']}  ({platform['station_count']} stations)")
        for station in platform["stations"]:
            symmetry = station["symmetry_name"] or "-"
            precluding = ",".join(map(str, station["precluding"])) or "-"
            print(
                f"  [{station['index']:02d}] {station['name']}"
                f" | symmetry={symmetry}"
                f" | hardpoints={station['hardpoint_count']}"
                f" | precluding={precluding}"
                f" | allowed={station['allowed_weapon_count']}"
            )
        print()


def main() -> None:
    args = parse_args()
    dictionary, configs, schema, preset_count, issues = load_inputs(args)
    platforms = select_platforms(dictionary, args.platform)
    summary = build_summary(
        dictionary, configs, schema, preset_count, issues, platforms
    )

    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print_report(summary)


if __name__ == "__main__":
    main()
