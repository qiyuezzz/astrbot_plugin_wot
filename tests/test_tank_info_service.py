import pytest

from data.plugins.astrbot_plugin_wot.src.application import tank_info_service
from data.plugins.astrbot_plugin_wot.src.application.tank_info_service import (
    build_tank_comparison_text,
    build_tank_comparison_report,
    build_tank_info_text,
    build_tank_info_report,
    split_comparison_query,
)
from data.plugins.astrbot_plugin_wot.src.domain.report import (
    Tank,
    TankNationEnum,
    TankRoleEnum,
    TankTypeEnum,
)


def _tank(name: str, vehicle_cd: int, tier: int = 8) -> Tank:
    return Tank(
        name=name,
        tier=tier,
        premium=1,
        vehicle_cd=vehicle_cd,
        nation=TankNationEnum.CHINA,
        type=TankTypeEnum.MEDIUM_TANK,
        role=TankRoleEnum.ROLE_MT_UNIVERSAL,
    )


def _find(name: str):
    tanks = {
        "59式": _tank("59式", 49),
        "查狄伦 25t": _tank("查狄伦 25t", 65, 10),
    }
    return [tanks[name]] if name in tanks else []


def _info(tank: Tank):
    base = {
        "max_health": 1300,
        "damage1": 250,
        "damage_per_minute": 1900,
        "piercing1": 185,
        "piercing2": 241,
        "piercing3": 50,
        "shot_dispersion_radius": 0.35,
        "aiming_time": 2,
        "speed_forward_kmh": 60,
        "power_weight_ratio": 18.06,
        "chassis_rotation_speed_deg": 46,
        "turret_rotation_speed_deg": 46,
        "circular_vision_radius": 380,
    }
    if tank.name == "查狄伦 25t":
        base["damage1"] = 390
    return base


def test_build_tank_info_text(monkeypatch):
    monkeypatch.setattr(tank_info_service, "find_tanks_by_name", _find)
    monkeypatch.setattr(tank_info_service, "get_tank_full_info", _info)
    text = build_tank_info_text("59式")
    assert "59式 坦克百科" in text
    assert "8级 · 中国 · 中坦" in text
    assert "单发伤害：250" in text
    assert "穿深：185/241/50" in text


def test_split_comparison_query_supports_names_with_spaces(monkeypatch):
    monkeypatch.setattr(tank_info_service, "find_tanks_by_name", _find)
    assert split_comparison_query("59式 查狄伦 25t") == ("59式", "查狄伦 25t")
    assert split_comparison_query("59式 和 查狄伦 25t") == (
        "59式",
        "查狄伦 25t",
    )


def test_build_tank_comparison_text(monkeypatch):
    monkeypatch.setattr(tank_info_service, "find_tanks_by_name", _find)
    monkeypatch.setattr(tank_info_service, "get_tank_full_info", _info)
    text = build_tank_comparison_text("59式 和 查狄伦 25t")
    assert "坦克对比：59式 vs 查狄伦 25t" in text
    assert "单发伤害：250 | 390" in text


def test_profile_groups_and_fittings_use_preferred_deploy():
    profile = {
        "tank_info_list": [
            {
                "name": "移动",
                "deploy_list": [
                    {
                        "name": "基础配置",
                        "parameter_list": [
                            {"name": "发动机功率，马力", "key": "engine_power", "current": 60}
                        ],
                        "fittings": [
                            {"type": "engine", "title": "基础发动机"}
                        ],
                    },
                    {
                        "name": "高级配置",
                        "parameter_list": [
                            {"name": "发动机功率，马力", "key": "engine_power", "current": 100}
                        ],
                        "fittings": [
                            {"type": "engine", "title": "高级发动机"}
                        ],
                    },
                ],
            }
        ]
    }

    groups = tank_info_service._profile_groups(profile)

    assert groups[0][1][0]["current"] == 100
    assert tank_info_service._find_fitting(profile, "engine")["title"] == "高级发动机"


def _profile(tank: Tank):
    damage = 250 if tank.name == "59式" else 390
    return {
        "tank_id": tank.vehicle_cd,
        "name": tank.name,
        "tank_info_list": [
            {
                "name": "装备",
                "deploy_list": [
                    {
                        "name": "基础配置",
                        "fittings": [
                            {
                                "title": f"{tank.name}主炮",
                                "type": "gun",
                                "tier": f"{tank.tier}级",
                                "fit_list": [
                                    {"name": "口径，毫米", "value": 100},
                                    {
                                        "name": "伤害，HP",
                                        "value": f"{damage}/{damage}/500",
                                    },
                                    {
                                        "name": "穿透，毫米",
                                        "value": "185/241/50",
                                    },
                                ],
                            },
                            {
                                "title": f"{tank.name}发动机",
                                "type": "engine",
                                "tier": f"{tank.tier}级",
                                "fit_list": [
                                    {"name": "起火几率，%", "value": 12},
                                ],
                            },
                        ],
                        "parameter_list": [
                            {
                                "name": "伤害，HP",
                                "key": "ammo_damage",
                                "current": damage,
                            },
                            {
                                "name": "坦克移动准心扩圈参数",
                                "key": "weaponry_moving",
                                "current": 0.14,
                            },
                            {
                                "name": "射击俯角，度",
                                "key": "gun_move_down_arc",
                                "current": 7,
                            },
                        ],
                    }
                ],
            },
            {
                "name": "视野和隐蔽",
                "deploy_list": [
                    {
                        "name": "基础配置",
                        "parameter_list": [
                            {
                                "name": "静止隐蔽系数（%）",
                                "key": "everything_else_stationary_camo",
                                "current": 15.68,
                            }
                        ],
                    }
                ],
            },
        ],
    }


async def _fake_wiki_data(tank: Tank):
    return {"tanke_image": f"https://example.com/{tank.vehicle_cd}.png"}, _profile(tank)


@pytest.mark.asyncio
async def test_build_tank_info_report_uses_detailed_camp_data(monkeypatch):
    monkeypatch.setattr(tank_info_service, "find_tanks_by_name", _find)
    monkeypatch.setattr(tank_info_service, "_get_wiki_data", _fake_wiki_data)

    report = await build_tank_info_report("59式")

    assert "【火力与炮控】" in report.text
    assert "坦克移动准心扩圈参数：0.14" in report.text
    assert "射击俯角：-7°" in report.text
    assert "【视野与隐蔽】" in report.text
    assert "静止隐蔽系数（%）：15.68" in report.text
    mobility_text = report.text.split("【机动性能】", 1)[1].split("\n\n", 1)[0]
    assert "发动机型号：" not in mobility_text
    assert "发动机等级：8级" in mobility_text
    assert "起火几率，%：12" in mobility_text
    firepower_text = report.text.split("【火力与炮控】", 1)[1].split("\n\n", 1)[0]
    assert "火炮型号：59式主炮" in firepower_text
    assert "口径，毫米：100" in firepower_text
    assert firepower_text.count("伤害，HP") == 1
    assert "【模块配置 · 火炮】" not in report.text
    assert "【模块配置 · 发动机】" not in report.text
    assert "【模块配置 · 炮塔】" not in report.text
    assert "【模块配置 · 悬挂】" not in report.text
    assert "【模块配置 · 电台】" not in report.text
    assert report.hero_images == (("59式", "https://example.com/49.png"),)


@pytest.mark.asyncio
async def test_build_tank_comparison_report_uses_both_profiles(monkeypatch):
    monkeypatch.setattr(tank_info_service, "find_tanks_by_name", _find)
    monkeypatch.setattr(tank_info_service, "_get_wiki_data", _fake_wiki_data)

    report = await build_tank_comparison_report("59式 和 查狄伦 25t")

    assert "伤害，HP：250/250/500 | 390/390/500" in report.text
    assert "射击俯角：-7° | -7°" in report.text
    mobility_text = report.text.split("【机动性能】", 1)[1].split("\n\n", 1)[0]
    assert "发动机型号：" not in mobility_text
    assert "起火几率，%：12 | 12" in mobility_text
    assert "【模块配置" not in report.text
    assert len(report.hero_images) == 2
