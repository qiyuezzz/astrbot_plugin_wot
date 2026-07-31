import json
from pathlib import Path

from data.plugins.astrbot_plugin_wot.src.infrastructure.repositories import (
    tank_repository,
)
from data.plugins.astrbot_plugin_wot.src.infrastructure.repositories.tank_repository import (
    find_tank_by_name,
    find_tank_candidates_by_name,
    find_tanks_by_name,
    get_tank_info_by_name,
    invalidate_tank_db_cache,
)


def _tank_payload(name: str, tier: int) -> dict:
    return {
        "name": name,
        "vehicle_cd": 1,
        "tier": tier,
        "premium": 0,
        "nation": "china",
        "type": "mediumTank",
        "role": "",
    }


class _CountingPath(Path):
    """记录 open 调用次数的 Path，用于验证缓存命中。"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.reads = 0

    def open(self, *args, **kwargs):
        mode = kwargs.get("mode", args[1] if len(args) > 1 else "r")
        if "r" in mode:
            self.reads += 1
        return super().open(*args, **kwargs)


def test_tank_repository_reads_and_reloads_cached_db(tmp_path, monkeypatch):
    data_file = _CountingPath(tmp_path / "wot_tanks_full.json")
    data_file.write_text(
        json.dumps({"TankA": _tank_payload("TankA", 5)}), encoding="utf-8"
    )
    monkeypatch.setattr(
        tank_repository, "prepare_tank_info_path", lambda: data_file
    )
    invalidate_tank_db_cache()

    tank = get_tank_info_by_name("TankA")
    assert tank.name == "TankA"
    assert tank.tier == 5

    # 同一 mtime 直接命中缓存，不再读取文件
    tank_again = get_tank_info_by_name("TankA")
    assert tank_again == tank
    assert data_file.reads == 1

    # 同步后主动失效，应重新读取新数据
    data_file.write_text(
        json.dumps({"TankA": _tank_payload("TankA", 7)}), encoding="utf-8"
    )
    invalidate_tank_db_cache()
    assert get_tank_info_by_name("TankA").tier == 7


def test_tank_repository_returns_unknown_for_missing_tank(tmp_path, monkeypatch):
    data_file = tmp_path / "wot_tanks_full.json"
    data_file.write_text(json.dumps({}), encoding="utf-8")
    monkeypatch.setattr(
        tank_repository, "prepare_tank_info_path", lambda: data_file
    )
    invalidate_tank_db_cache()

    tank = get_tank_info_by_name("NoSuchTank")
    assert tank.name == "NoSuchTank"
    assert tank.tier == 0


def test_find_tank_by_name_supports_unique_partial_name(tmp_path, monkeypatch):
    data_file = tmp_path / "wot_tanks_full.json"
    data_file.write_text(
        json.dumps(
            {
                '"野牛" C45': _tank_payload('"野牛" C45', 10),
                '"鞭蛇"': _tank_payload('"鞭蛇"', 9),
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        tank_repository, "prepare_tank_info_path", lambda: data_file
    )
    invalidate_tank_db_cache()

    tank = find_tank_by_name("野牛")

    assert tank is not None
    assert tank.name == '"野牛" C45'


def test_find_tanks_by_name_returns_all_partial_matches_for_59(tmp_path, monkeypatch):
    data_file = tmp_path / "wot_tanks_full.json"
    data_file.write_text(
        json.dumps(
            {
                "59式": _tank_payload("59式", 8),
                "黄金59式": _tank_payload("黄金59式", 8),
                "59-16": _tank_payload("59-16", 6),
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        tank_repository, "prepare_tank_info_path", lambda: data_file
    )
    invalidate_tank_db_cache()

    tanks = find_tanks_by_name("59")

    assert [tank.name for tank in tanks] == ["59式", "黄金59式", "59-16"]
    assert find_tanks_by_name("59式")[0].name == "59式"


def test_find_tanks_by_name_returns_all_ambiguous_partial_matches(
    tmp_path, monkeypatch
):
    data_file = tmp_path / "wot_tanks_full.json"
    data_file.write_text(
        json.dumps(
            {
                "野牛 C45": _tank_payload("野牛 C45", 10),
                "野牛 C46": _tank_payload("野牛 C46", 10),
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        tank_repository, "prepare_tank_info_path", lambda: data_file
    )
    invalidate_tank_db_cache()

    tanks = find_tanks_by_name("野牛")

    assert [tank.name for tank in tanks] == ["野牛 C45", "野牛 C46"]
    assert find_tank_by_name("野牛") is None


def test_find_tank_candidates_includes_exact_and_partial_matches(
    tmp_path, monkeypatch
):
    data_file = tmp_path / "wot_tanks_full.json"
    data_file.write_text(
        json.dumps(
            {
                "野牛": _tank_payload("野牛", 3),
                "野牛 C45": _tank_payload("野牛 C45", 4),
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        tank_repository, "prepare_tank_info_path", lambda: data_file
    )
    invalidate_tank_db_cache()

    candidates = find_tank_candidates_by_name("野牛")

    assert [tank.name for tank in candidates] == ["野牛", "野牛 C45"]
