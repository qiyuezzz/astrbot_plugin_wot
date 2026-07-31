import json

from data.plugins.astrbot_plugin_wot.src.infrastructure.repositories import (
    bindings_repository,
)
from data.plugins.astrbot_plugin_wot.src.infrastructure.repositories.bindings_repository import (
    read_binding_data,
    read_binding_info,
)


def test_read_binding_supports_legacy_and_new_format(tmp_path, monkeypatch):
    bind_file = tmp_path / "player_name_binding.json"
    bind_file.write_text(
        json.dumps(
            {
                "10001": "旧玩家",
                "10002": {"name": "新玩家", "account_id": "12345"},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        bindings_repository, "prepare_bind_data_path", lambda: bind_file
    )

    assert read_binding_data("10001") == "旧玩家"
    assert read_binding_info("10001").account_id is None

    new_info = read_binding_info("10002")
    assert new_info.name == "新玩家"
    assert new_info.account_id == "12345"
    assert read_binding_data("10002") == "新玩家"
    assert read_binding_info("10003") is None
