from data.plugins.astrbot_plugin_wot.src.infrastructure.api_clients.wot_game_api import (
    _normalize_achievements,
    _normalize_profile_page,
    normalize_player_career,
    normalize_player_vehicles,
)


def test_normalize_profile_page_extracts_player_and_clan_data():
    html = '''
    <script>USER_DATA = {"nickname":"玩家","reg_timestamp":123,"summary":{"last_battle_at":456},"clan_info":{"tag":"TAG","name":"Clan","color":"#abc","role":"recruit","days_in_clan":12}}, OTHER = {};</script>
    <span class="clan-box_img" style="background-image:url(//example.com/emblem.png);"></span>
    '''

    assert _normalize_profile_page(html) == {
        "nickname": "玩家",
        "registered_at": 123,
        "last_battle_at": 456,
        "clan": {
            "tag": "TAG",
            "name": "Clan",
            "color": "#abc",
            "role": "recruit",
            "days": 12,
            "emblem_url": "https://example.com/emblem.png",
        },
    }


def test_normalize_achievements_maps_summary_and_icon():
    result = _normalize_achievements(
        {
            "data": {
                "parameters": ["mark", "icon", "value"],
                "data": [["勇士", "wot/current/achievement/warrior.png", 11]],
                "mastery": {"mastery_count": 22, "vehicles_count": 173},
                "unique_achievements_count": 81,
                "total_achievements_count": 5710,
            }
        }
    )

    assert result["mastery_count"] == 22
    assert result["vehicles_count"] == 173
    assert result["unique_count"] == 81
    assert result["total_count"] == 5710
    assert result["items"][0]["name"] == "勇士"
    assert result["items"][0]["icon_url"].endswith("wot/current/achievement/warrior.png")


def test_normalize_player_vehicles_maps_official_parameter_rows():
    payload = {
        "status": "ok",
        "data": {
            "parameters": [
                "vehicle_cd",
                "name",
                "tier",
                "type",
                "wins_ratio",
                "frags_per_battle_average",
                "damage_per_battle_average",
                "xp_per_battle_average",
                "battles_count",
                "marksOnGun",
            ],
            "data": [[49, "59式", 8, "mediumTank", 58.18, 0.53, 946, 771, 55, 2]],
        },
    }

    assert normalize_player_vehicles(payload) == [
        {
            "vehicle_cd": 49,
            "vehicle_name": "59式",
            "vlevel": 8,
            "vtype": "mediumTank",
            "battles": 55,
            "win_rate": 58.18,
            "avg_frags": 0.53,
            "damage_avg": 946,
            "xp_per_battle_average": 771,
            "frags_per_battle_average": 0.53,
            "marksOnGun": 2,
            "markOfMastery": None,
        }
    ]


def test_normalize_player_vehicles_handles_empty_payload():
    assert normalize_player_vehicles({"status": "ok", "data": {}}) == []


def test_normalize_player_career_maps_summary_and_distributions():
    result = normalize_player_career(
        {
            "status": "ok",
            "data": {
                "battles_count": 100,
                "wins_ratio": 55.5,
                "wtr": 1234,
                "xp_per_battle_average": 700,
            },
        },
        {
            "status": "ok",
            "data": {
                "battles_count": 100,
                "wins_count": 55,
                "wins_count_percent": 55.0,
                "frags_count_avg": 1.2,
                "master_level_counts": {"4": 3, "3": 4},
                "tiers": {
                    "8": {
                        "battles_count": 100,
                        "battles_count_percent": 100,
                        "wins_count_percent": 55,
                    }
                },
                "nations": {},
                "types": {},
            },
        },
    )

    assert result["summary"]["battles"] == 100
    assert result["summary"]["win_rate"] == 55.0
    assert result["average"]["frags"] == 1.2
    assert result["summary"]["wtr"] == 1234
    assert result["master_levels"][0] == {"name": "特级", "count": 3}
    assert result["tiers"][0]["name"] == "8级"
