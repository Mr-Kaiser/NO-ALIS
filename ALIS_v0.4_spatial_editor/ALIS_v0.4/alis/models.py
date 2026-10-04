
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True, slots=True)
class WeaponMount:
    owner: str
    json_key: str
    display_name: str
    asset_name: str
    ammo: int
    note_code: str = ""
    note_detail: str = ""

    @property
    def note(self) -> str:
        if self.note_code and self.note_detail:
            return f"{self.note_code}({self.note_detail})"
        return self.note_code or self.note_detail

    @property
    def is_stale_key(self) -> bool:
        return self.note_code.upper() == "STALE-KEY" or self.note.upper().startswith("STALE-KEY")

    @property
    def write_key(self) -> str:
        # Loadout Injector explicitly marks STALE-KEY rows where assetName is
        # the current spelling to use for generated station data.
        return self.asset_name if self.is_stale_key else self.json_key


@dataclass(frozen=True, slots=True)
class WeaponStation:
    platform: str
    station_index: int
    station_name: str
    symmetry_name: str | None
    hardpoint_count: int
    precluding: tuple[int, ...]
    owner: str

    # Compatibility aliases for the terminology used in ALIS v0.1.
    @property
    def aircraft(self) -> str:
        return self.platform

    @property
    def station_group(self) -> str | None:
        return self.symmetry_name

    @property
    def count(self) -> int:
        return self.hardpoint_count

    @property
    def conflicts_with(self) -> tuple[int, ...]:
        return self.precluding


@dataclass(slots=True)
class Platform:
    internal_name: str
    stations: list[WeaponStation] = field(default_factory=list)

    def sorted_stations(self) -> list[WeaponStation]:
        return sorted(self.stations, key=lambda s: s.station_index)


# Backward-compatible alias. Internally ALIS now uses "Platform" because the
# current Loadout Injector dictionary can contain aircraft, ground vehicles,
# ships, and other weapon-bearing entities.
AirVehicle = Platform


@dataclass(slots=True)
class LoadoutDictionary:
    weapons: list[WeaponMount] = field(default_factory=list)
    platforms: dict[str, Platform] = field(default_factory=dict)

    @property
    def air_vehicles(self) -> dict[str, Platform]:
        # Compatibility alias for v0.1 callers.
        return self.platforms

    @property
    def weapons_by_json_key(self) -> dict[str, WeaponMount]:
        return {weapon.json_key: weapon for weapon in self.weapons}

    @property
    def weapons_by_write_key(self) -> dict[str, WeaponMount]:
        return {weapon.write_key: weapon for weapon in self.weapons}

    @property
    def weapon_aliases(self) -> dict[str, WeaponMount]:
        aliases: dict[str, WeaponMount] = {}
        for weapon in self.weapons:
            aliases[weapon.json_key] = weapon
            aliases[weapon.asset_name] = weapon
        return aliases


@dataclass(slots=True)
class StationConfig:
    platform: str
    station_index: int
    station_name: str
    path: Path
    allowed_weapons: list[str]
    raw_data: dict

    @property
    def aircraft(self) -> str:
        return self.platform


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    severity: str
    code: str
    message: str
    path: str | None = None


@dataclass(slots=True)
class RepositorySnapshot:
    root: Path
    schema_version: str | None
    dictionary: LoadoutDictionary
    station_configs: dict[str, dict[int, list[StationConfig]]]
    preset_count: int
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def station_json_count(self) -> int:
        return sum(
            len(configs)
            for stations in self.station_configs.values()
            for configs in stations.values()
        )
