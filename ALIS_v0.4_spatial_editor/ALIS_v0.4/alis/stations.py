
from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

from .models import LoadoutDictionary, RepositorySnapshot, StationConfig, ValidationIssue


STATION_DIR_RE = re.compile(r"^weaponstation(?P<index>\d+)$", re.IGNORECASE)


def _read_station_json(path: Path) -> StationConfig:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected a JSON object.")
    allowed = data.get("allowedWeapons")
    if not isinstance(allowed, list) or not all(isinstance(item, str) for item in allowed):
        raise ValueError(f"{path}: expected allowedWeapons to be an array of strings.")

    station_dir = path.parent
    match = STATION_DIR_RE.match(station_dir.name)
    if not match:
        raise ValueError(f"Unexpected station folder name: {station_dir}")

    return StationConfig(
        platform=station_dir.parent.name,
        station_index=int(match.group("index")),
        station_name=path.stem,
        path=path,
        allowed_weapons=list(allowed),
        raw_data=data,
    )


def scan_preset_loadout(root: str | Path) -> dict[str, dict[int, list[StationConfig]]]:
    root = Path(root).expanduser().resolve()
    if not root.exists():
        raise FileNotFoundError(root)
    if not root.is_dir():
        raise NotADirectoryError(root)

    result: dict[str, dict[int, list[StationConfig]]] = defaultdict(lambda: defaultdict(list))

    for platform_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        for station_dir in sorted(p for p in platform_dir.iterdir() if p.is_dir()):
            match = STATION_DIR_RE.match(station_dir.name)
            if not match:
                continue

            index = int(match.group("index"))
            for json_path in sorted(station_dir.glob("*.json")):
                result[platform_dir.name][index].append(_read_station_json(json_path))

    return {
        platform: {index: configs for index, configs in sorted(stations.items())}
        for platform, stations in sorted(result.items())
    }


def validate_station_configs(
    dictionary: LoadoutDictionary,
    station_configs: dict[str, dict[int, list[StationConfig]]],
    root: Path | None = None,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    aliases = dictionary.weapon_aliases

    for platform_name, stations in station_configs.items():
        platform = dictionary.platforms.get(platform_name)
        if platform is None:
            issues.append(ValidationIssue(
                "error", "PLATFORM_NOT_IN_DICTIONARY",
                f"Platform {platform_name!r} has station JSON but no dictionary entry."
            ))
            continue

        metadata = {station.station_index: station for station in platform.stations}

        for index, configs in stations.items():
            station = metadata.get(index)
            if station is None:
                issues.append(ValidationIssue(
                    "error", "STATION_NOT_IN_DICTIONARY",
                    f"{platform_name} station {index} exists on disk but not in the station CSV."
                ))
                continue

            if len(configs) != 1:
                issues.append(ValidationIssue(
                    "warning", "MULTIPLE_STATION_JSON",
                    f"{platform_name} station {index} contains {len(configs)} JSON files."
                ))

            for config in configs:
                rel = None
                if root:
                    try:
                        rel = str(config.path.relative_to(root))
                    except ValueError:
                        rel = str(config.path)

                if config.station_name != station.station_name:
                    issues.append(ValidationIssue(
                        "warning", "STATION_NAME_MISMATCH",
                        f"{platform_name} station {index}: CSV name {station.station_name!r} "
                        f"!= JSON filename {config.station_name!r}.",
                        rel,
                    ))

                for key in config.allowed_weapons:
                    if key not in aliases:
                        issues.append(ValidationIssue(
                            "warning", "UNKNOWN_WEAPON_KEY",
                            f"{platform_name} station {index} references unknown weapon {key!r}.",
                            rel,
                        ))

    # Also flag metadata stations that have no station JSON.
    for platform_name, platform in dictionary.platforms.items():
        on_disk = station_configs.get(platform_name, {})
        for station in platform.stations:
            if station.station_index not in on_disk:
                issues.append(ValidationIssue(
                    "warning", "MISSING_STATION_JSON",
                    f"{platform_name} station {station.station_index} "
                    f"({station.station_name}) has no station JSON."
                ))

    return issues


def load_repository(root: str | Path) -> RepositorySnapshot:
    from .dictionary import load_dictionary

    root = Path(root).expanduser().resolve()
    dictionary = load_dictionary(root)
    station_configs = scan_preset_loadout(root)
    schema_path = root / ".schema-version"
    schema_version = (
        schema_path.read_text(encoding="utf-8-sig").strip()
        if schema_path.exists()
        else None
    )
    preset_count = sum(1 for _ in root.glob("*/*.preset"))
    issues = validate_station_configs(dictionary, station_configs, root)

    return RepositorySnapshot(
        root=root,
        schema_version=schema_version,
        dictionary=dictionary,
        station_configs=station_configs,
        preset_count=preset_count,
        issues=issues,
    )
