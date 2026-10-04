
"""ALIS core package."""

from .models import (
    AirVehicle,
    LoadoutDictionary,
    Platform,
    RepositorySnapshot,
    StationConfig,
    ValidationIssue,
    WeaponMount,
    WeaponStation,
)
from .dictionary import load_dictionary
from .stations import load_repository, scan_preset_loadout, validate_station_configs
from .writer import ChangedOnDisk, EditPlan, SaveResult, WriteError, commit, plan_edit, plan_restore

__version__ = "0.2.0"

__all__ = [
    "AirVehicle",
    "LoadoutDictionary",
    "Platform",
    "RepositorySnapshot",
    "StationConfig",
    "ValidationIssue",
    "WeaponMount",
    "WeaponStation",
    "load_dictionary",
    "load_repository",
    "scan_preset_loadout",
    "validate_station_configs",
    "ChangedOnDisk",
    "EditPlan",
    "SaveResult",
    "WriteError",
    "commit",
    "plan_edit",
    "plan_restore",
]
