import pytest

from data.plugins.astrbot_plugin_wot.src.application import career_service
from data.plugins.astrbot_plugin_wot.src.application.career_service import (
    _wtr_title,
    build_career_text,
)


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        (6199, "王牌I"),
        (6200, "王牌II"),
        (7299, "王牌II"),
        (7300, "王牌III"),
        (7999, "王牌III"),
        (8000, "传奇I"),
        (8800, "传奇II"),
        (9900, "传奇III"),
    ],
)
def test_wtr_title_boundaries(score, expected):
    assert _wtr_title(score) == expected


@pytest.mark.asyncio
async def test_build_career_text_formats_summary_and_distributions(monkeypatch):
    async def _fake_fetch(_account_id):
        return {
            "profile": {
                "nickname": "玩家",
                "registered_at": 1679757371,
                "last_battle_at": 1784915133,
                "clan": {
                    "tag": "别急",
                    "name": "FaZe Corps",
                    "role": "recruit",
                    "days": 682,
                },
            },
            "achievements": {
                "mastery_count": 22,
                "vehicles_count": 173,
                "unique_count": 81,
                "total_count": 5710,
                "items": [
                    {"name": "勇士", "value": 11, "icon_url": "https://example.com/warrior.png"}
                ],
            },
            "summary": {
                "battles": 7536,
                "wins": 3937,
                "losses": 3447,
                "win_rate": 52.24,
                "survived_rate": 29.05,
                "damage_ratio": 1.1,
                "frags_deaths_ratio": 1.16,
                "armor_ratio": 0.44,
                "capture_points": 5539,
                "defense_points": 1282,
                "wtr": 6712,
            },
            "average": {
                "frags": 0.82,
                "damage": 1495,
                "xp": 817,
                "damage_received": 1365,
            },
            "records": {"max_frags": 7, "max_damage": 7313, "max_xp": 2403},
            "master_levels": [
                {"name": "特级", "count": 22},
                {"name": "I级", "count": 22},
            ],
            "tiers": [
                {
                    "code": "8",
                    "name": "8级",
                    "battles": 4163,
                    "battle_percent": 55.24,
                    "win_rate": 50.78,
                    "master_count": 50,
                }
            ],
            "types": [
                {
                    "code": "heavyTank",
                    "name": "重型坦克",
                    "battles": 3848,
                    "battle_percent": 51.06,
                    "win_rate": 51.85,
                    "master_count": 72,
                }
            ],
            "nations": [],
        }

    monkeypatch.setattr(career_service, "fetch_player_career", _fake_fetch)
    career_service._career_cache.clear()

    text = await build_career_text("玩家", "7059354392")

    assert "总成绩" in text
    assert "玩家名称：玩家" in text
    assert "军团标签：别急" in text
    assert "军团名称：FaZe Corps" in text
    assert "战斗勋章：特级M 22 / 173 · 独特 81 · 总计 5,710" in text
    assert "勇士：11|https://example.com/warrior.png" in text
    assert "场次：7,536" in text
    assert "每场战斗击毁的敌方坦克：0.82" in text
    assert "造成损伤：1,495" in text
    assert "经验：817" in text
    assert "平均每场战斗数据" in text
    assert "成绩记录" in text
    assert "MB" in text
    assert "特级：22" in text
    assert "战斗坦克分布（按等级）" in text
    assert "1级：0场" in text
    assert "8级：4,163场 · 占比55.24% · 胜率50.78% · MB50" in text
    assert "11级：0场" in text
    assert "战斗坦克分布（按坦克类型）" in text
    assert "数据来源：游戏官网" in text
    career_service._career_cache.clear()
