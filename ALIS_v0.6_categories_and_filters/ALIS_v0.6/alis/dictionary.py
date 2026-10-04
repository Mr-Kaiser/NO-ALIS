
from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Iterable

from .models import LoadoutDictionary, Platform, WeaponMount, WeaponStation


def _clean(value: str | None) -> str:
    return (value or "").strip()


def _optional_text(value: str | None) -> str | None:
    value = _clean(value)
    return None if value in {"", "-"} else value


def _int(value: str | int | None, field_name: str) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid integer for {field_name}: {value!r}") from exc


def _precluding(value: str | None) -> tuple[int, ...]:
    value = _clean(value)
    if value in {"", "-"}:
        return ()
    return tuple(_int(part.strip(), "precluding") for part in value.split(",") if part.strip())


def _weapon_from_row(row: dict[str, str]) -> WeaponMount:
    # Current 2.0.0-k2:
    # owner,jsonKey,displayName,assetName,ammo,note_code,note_detail
    #
    # Older export:
    # index,owner,jsonKey,displayName,assetName,ammo,note
    note_code = _clean(row.get("note_code"))
    note_detail = _clean(row.get("note_detail"))
    legacy_note = _clean(row.get("note"))

    if legacy_note and not note_code:
        if "(" in legacy_note and legacy_note.endswith(")"):
            note_code, note_detail = legacy_note.split("(", 1)
            note_detail = note_detail[:-1]
        else:
            note_code = legacy_note

    return WeaponMount(
        owner=_clean(row.get("owner")),
        json_key=_clean(row.get("jsonKey")),
        display_name=_clean(row.get("displayName")),
        asset_name=_clean(row.get("assetName")),
        ammo=_int(row.get("ammo"), "ammo"),
        note_code=note_code,
        note_detail=note_detail,
    )


def _station_from_row(row: dict[str, str]) -> WeaponStation:
    # Current 2.0.0-k2:
    # aircraft,index,name,symmetryName,hardpointCount,precluding,owner
    #
    # Older export:
    # index,aircraft,stationIndex,stationName,stationGroup,count,conflictsWith,owner
    station_index = row.get("stationIndex")
    if station_index is None:
        station_index = row.get("index")

    station_name = row.get("stationName")
    if station_name is None:
        station_name = row.get("name")

    symmetry_name = row.get("stationGroup")
    if symmetry_name is None:
        symmetry_name = row.get("symmetryName")

    hardpoint_count = row.get("count")
    if hardpoint_count is None:
        hardpoint_count = row.get("hardpointCount")

    precluding = row.get("conflictsWith")
    if precluding is None:
        precluding = row.get("precluding")

    return WeaponStation(
        platform=_clean(row.get("aircraft")),
        station_index=_int(station_index, "station index"),
        station_name=_clean(station_name),
        symmetry_name=_optional_text(symmetry_name),
        hardpoint_count=_int(hardpoint_count, "hardpoint count"),
        precluding=_precluding(precluding),
        owner=_clean(row.get("owner")),
    )


def _build_dictionary(
    weapons: Iterable[WeaponMount],
    stations: Iterable[WeaponStation],
) -> LoadoutDictionary:
    result = LoadoutDictionary(weapons=list(weapons))

    for station in stations:
        platform = result.platforms.setdefault(
            station.platform,
            Platform(internal_name=station.platform),
        )
        platform.stations.append(station)

    for platform in result.platforms.values():
        platform.stations.sort(key=lambda s: s.station_index)

    result.weapons.sort(key=lambda w: (w.display_name.casefold(), w.json_key.casefold()))
    return result


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def load_split_csvs(mount_csv: Path, station_csv: Path) -> LoadoutDictionary:
    weapons = [_weapon_from_row(row) for row in _read_csv_rows(mount_csv)]
    stations = [_station_from_row(row) for row in _read_csv_rows(station_csv)]
    return _build_dictionary(weapons, stations)


def _extract_log_sections(text: str) -> tuple[list[str], list[str]]:
    weapon_lines: list[str] = []
    station_lines: list[str] = []
    section: str | None = None

    for raw_line in text.splitlines():
        line = raw_line.rstrip("\r\n")

        if line.strip() == "[A] WEAPON MOUNTS":
            section = "weapons"
            continue
        if line.strip().startswith("[B] HARDPOINT SETS"):
            section = "stations"
            continue
        if not line.strip():
            continue

        if section == "weapons":
            weapon_lines.append(line)
        elif section == "stations":
            station_lines.append(line)

    if not weapon_lines:
        raise ValueError("Could not find [A] WEAPON MOUNTS in hardpoint dictionary log.")
    if not station_lines:
        raise ValueError("Could not find [B] HARDPOINT SETS in hardpoint dictionary log.")

    return weapon_lines, station_lines


def load_raw_log(path: Path) -> LoadoutDictionary:
    # Legacy Loadout Injector format kept for backwards compatibility.
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    weapon_lines, station_lines = _extract_log_sections(text)

    weapon_reader = csv.DictReader(io.StringIO("\n".join(weapon_lines)), delimiter="\t")
    weapons = [_weapon_from_row(row) for row in weapon_reader]

    stations: list[WeaponStation] = []
    legacy_fields = (
        "aircraft",
        "stationIndex",
        "stationName",
        "stationGroup",
        "count",
        "conflictsWith",
        "owner",
    )
    for line_number, line in enumerate(station_lines, start=1):
        parts = line.split("\t", 6)
        if len(parts) != 7:
            raise ValueError(
                "Unexpected hardpoint-set row in raw log "
                f"(section row {line_number}): expected 7 tab-delimited fields, got {len(parts)}."
            )
        stations.append(_station_from_row(dict(zip(legacy_fields, parts, strict=True))))

    return _build_dictionary(weapons, stations)


def _prefer(paths: list[Path]) -> Path:
    if not paths:
        raise FileNotFoundError("No matching dictionary export found.")
    updated = [p for p in paths if "_updated" in p.stem.lower()]
    candidates = updated or paths
    return sorted(candidates, key=lambda p: (p.stat().st_mtime, p.name), reverse=True)[0]


def _mount_candidates(directory: Path) -> list[Path]:
    return (
        list(directory.glob("hardpointdictionary_mounts*.csv"))
        + list(directory.glob("hardpointdictionary_weapon_mounts*.csv"))
    )


def _station_candidates(directory: Path) -> list[Path]:
    return (
        list(directory.glob("hardpointdictionary_stations*.csv"))
        + list(directory.glob("hardpointdictionary_hardpoint_sets*.csv"))
    )


def _find_csv_pair(directory: Path) -> tuple[Path, Path]:
    mounts = _mount_candidates(directory)
    stations = _station_candidates(directory)
    if not mounts or not stations:
        raise FileNotFoundError(
            "Could not find a Loadout Injector mount/station CSV pair. "
            "Expected hardpointdictionary_mounts.csv + hardpointdictionary_stations.csv "
            "(current) or the older weapon_mounts/hardpoint_sets names."
        )
    return _prefer(mounts), _prefer(stations)


def _infer_csv_pair(csv_path: Path) -> tuple[Path, Path]:
    name = csv_path.name.lower()
    parent = csv_path.parent

    if "mounts" in name:
        mount_csv = csv_path
        station_csv = _prefer(_station_candidates(parent))
    elif "stations" in name or "hardpoint_sets" in name:
        station_csv = csv_path
        mount_csv = _prefer(_mount_candidates(parent))
    else:
        raise ValueError(f"Unrecognized Loadout Injector CSV filename: {csv_path.name}")

    return mount_csv, station_csv


def load_dictionary(source: str | Path) -> LoadoutDictionary:
    """
    Accepted inputs:
      * current preset-loadout directory
      * current hardpointdictionary_mounts.csv / hardpointdictionary_stations.csv
      * legacy split CSV exports
      * legacy hardpointdictionary.log
    """
    path = Path(source).expanduser().resolve()

    if not path.exists():
        raise FileNotFoundError(path)

    if path.is_dir():
        try:
            mount_csv, station_csv = _find_csv_pair(path)
            return load_split_csvs(mount_csv, station_csv)
        except FileNotFoundError:
            logs = sorted(path.glob("hardpointdictionary*.log"))
            if logs:
                return load_raw_log(logs[-1])
            raise

    if path.suffix.lower() == ".log":
        return load_raw_log(path)

    if path.suffix.lower() == ".csv":
        mount_csv, station_csv = _infer_csv_pair(path)
        return load_split_csvs(mount_csv, station_csv)

    raise ValueError(f"Unsupported dictionary source: {path}")
