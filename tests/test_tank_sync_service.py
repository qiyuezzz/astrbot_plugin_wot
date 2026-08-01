import json

import pytest

from data.plugins.astrbot_plugin_wot.src.application import tank_sync_service


class _FakeResponse:
    status = 200

    def __init__(self, payload):
        self.payload = payload

    async def json(self):
        return self.payload


@pytest.mark.asyncio
async def test_sync_rejects_empty_payload_and_preserves_existing_database(
    monkeypatch, tmp_path
):
    tank_file = tmp_path / "tanks.json"
    original = {"59式": {"name": "59式", "vehicle_cd": 49, "tier": 8}}
    tank_file.write_text(json.dumps(original), encoding="utf-8")

    async def _fetch():
        return _FakeResponse({"data": {"parameters": [], "data": []}})

    monkeypatch.setattr(tank_sync_service, "fetch_all_tank_info", _fetch)
    monkeypatch.setattr(tank_sync_service, "prepare_tank_info_path", lambda: tank_file)

    result = await tank_sync_service.sync_all_tank_info()

    assert result.startswith("更新失败：")
    assert json.loads(tank_file.read_text(encoding="utf-8")) == original


@pytest.mark.asyncio
async def test_sync_atomically_replaces_database_after_validation(monkeypatch, tmp_path):
    tank_file = tmp_path / "tanks.json"
    tank_file.write_text('{"旧数据": {"name": "旧数据"}}', encoding="utf-8")
    rows = [[f"坦克{i}", i + 1, 8] for i in range(100)]

    async def _fetch():
        return _FakeResponse(
            {
                "data": {
                    "parameters": ["name", "vehicle_cd", "tier"],
                    "data": rows,
                }
            }
        )

    async def _wotinspector_failure():
        raise RuntimeError("offline")

    monkeypatch.setattr(tank_sync_service, "fetch_all_tank_info", _fetch)
    monkeypatch.setattr(tank_sync_service, "fetch_tank_db_js", _wotinspector_failure)
    monkeypatch.setattr(tank_sync_service, "prepare_tank_info_path", lambda: tank_file)

    result = await tank_sync_service.sync_all_tank_info()
    saved = json.loads(tank_file.read_text(encoding="utf-8"))

    assert result == "更新成功！已保存 100 辆坦克的全字段信息。"
    assert len(saved) == 100
    assert "旧数据" not in saved
