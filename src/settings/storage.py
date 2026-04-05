from __future__ import annotations

import shutil
from pathlib import Path

from astrbot.core.utils.astrbot_path import (
    get_astrbot_data_path,
    get_astrbot_plugin_data_path,
    get_astrbot_temp_path,
)

PLUGIN_NAME = "astrbot_plugin_wot"
DATA_DIR_NAME = "data"
REPORT_DIR_NAME = "report"


def get_plugin_package_dir() -> Path:
    return Path(__file__).resolve().parents[2]


def get_plugin_resources_dir() -> Path:
    return get_plugin_package_dir() / "resources"


def get_plugin_data_dir() -> Path:
    return Path(get_astrbot_plugin_data_path()) / PLUGIN_NAME


def get_plugin_temp_dir() -> Path:
    return Path(get_astrbot_temp_path()) / PLUGIN_NAME


def get_plugin_persistent_data_dir() -> Path:
    return get_plugin_data_dir() / DATA_DIR_NAME


def get_plugin_report_dir() -> Path:
    return get_plugin_temp_dir() / REPORT_DIR_NAME


def get_legacy_static_data_dir() -> Path:
    return (
        Path(get_astrbot_data_path())
        / "plugins"
        / PLUGIN_NAME
        / "resources"
        / "static"
        / "data"
    )


def ensure_storage_layout() -> None:
    get_plugin_persistent_data_dir().mkdir(parents=True, exist_ok=True)
    get_plugin_temp_dir().mkdir(parents=True, exist_ok=True)


def _migrate_legacy_file(file_name: str) -> Path:
    target_path = get_plugin_persistent_data_dir() / file_name
    legacy_path = get_legacy_static_data_dir() / file_name
    if not target_path.exists() and legacy_path.exists():
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(legacy_path, target_path)
    return target_path


def get_bind_data_path() -> Path:
    return get_plugin_persistent_data_dir() / "player_name_binding.json"


def get_tank_info_path() -> Path:
    return get_plugin_persistent_data_dir() / "wot_tanks_full.json"


def prepare_bind_data_path() -> Path:
    ensure_storage_layout()
    return _migrate_legacy_file("player_name_binding.json")


def prepare_tank_info_path() -> Path:
    ensure_storage_layout()
    return _migrate_legacy_file("wot_tanks_full.json")
