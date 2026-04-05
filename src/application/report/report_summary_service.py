from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import datetime
from enum import Enum

from astrbot.api import logger
from data.plugins.astrbot_plugin_wot.src.domain.report import (
    FinalSummary,
    OverallSummary,
    RecordsBasic,
    RecordsDetail,
    Tank,
    TankSummary,
)
from data.plugins.astrbot_plugin_wot.src.infrastructure.gateways.wot_box_records_gateway import (
    get_detail_record_single,
)
from data.plugins.astrbot_plugin_wot.src.infrastructure.network.http_client import (
    HttpClient,
)


class BattleResult(str, Enum):
    """战斗结果"""

    WIN = "win"
    LOSE = "lose"
    DRAW = "draw"


def parse_battle_result(is_win: str) -> BattleResult:
    """将 is_win 字符串解析为 BattleResult 枚举"""
    mapping = {"1": BattleResult.WIN, "0": BattleResult.LOSE, "2": BattleResult.DRAW}
    return mapping.get(is_win, BattleResult.LOSE)


def get_final_summary(
    detail_record_list: list[RecordsDetail], title: str
) -> FinalSummary:
    return FinalSummary(
        summary_title=title,
        query_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        last_battle_time=datetime.fromtimestamp(
            float(detail_record_list[0].records_basic.start_time)
        ).strftime("%Y-%m-%d %H:%M:%S"),
        overall_summary=_calculate_overall_summary(detail_record_list),
        tank_summary=_calculate_tank_summary(detail_record_list),
    )


async def get_detail_record_list(
    player_name: str, arena_list: list[RecordsBasic]
) -> list[RecordsDetail]:
    detail_record_list: list[RecordsDetail] = []
    sem = asyncio.Semaphore(5)

    async with HttpClient() as http:

        async def _fetch_one(arena: RecordsBasic) -> RecordsDetail | None:
            async with sem:
                try:
                    return await get_detail_record_single(player_name, arena, http=http)
                except Exception as exc:
                    logger.warning(
                        f"Failed to fetch battle detail for arena {arena.arena_id}: {exc}"
                    )
                    return None

        results = await asyncio.gather(*[_fetch_one(arena) for arena in arena_list])
    for result in results:
        if result:
            detail_record_list.append(result)

    detail_record_list.sort(key=lambda x: x.records_basic.start_time, reverse=True)
    return detail_record_list


def _tally_result(counts: dict[str, int], is_win: str) -> None:
    """根据战斗结果更新计数"""
    result = parse_battle_result(is_win)
    counts[result.value] += 1


def _calculate_overall_summary(
    detail_record_list: list[RecordsDetail],
) -> OverallSummary:
    total_count = len(detail_record_list)
    counts = {"win": 0, "lose": 0, "draw": 0}
    sums = {
        "power": 0.0,
        "damage": 0,
        "blocked": 0,
        "assist": 0,
        "exp": 0,
        "credits": 0.0,
        "life_time": 0,
        "tier": 0,
    }

    for detail_record in detail_record_list:
        _tally_result(counts, detail_record.records_basic.is_win)

        sums["power"] += detail_record.power
        sums["damage"] += detail_record.damage_dealt
        sums["blocked"] += detail_record.blocked
        sums["assist"] += detail_record.assist_total
        sums["exp"] += detail_record.exp
        sums["credits"] += detail_record.credits
        sums["life_time"] += detail_record.life_time
        sums["tier"] += detail_record.tank_info.tier

    return OverallSummary(
        avg_tier=round(sums["tier"] / total_count, 1),
        win_rate=round(counts["win"] / total_count * 100, 2),
        total_count=total_count,
        win_count=counts["win"],
        lose_count=counts["lose"],
        draw_count=counts["draw"],
        avg_power=round(sums["power"] / total_count, 2),
        avg_damage=round(sums["damage"] / total_count, 2),
        avg_assist_total=round(sums["assist"] / total_count, 2),
        avg_block=round(sums["blocked"] / total_count, 2),
        avg_exp=round(sums["exp"] / total_count, 2),
        avg_credits=round(sums["credits"] / total_count, 2),
        avg_life_time=round(sums["life_time"] / total_count),
    )


def _calculate_tank_summary(
    detail_record_list: list[RecordsDetail],
) -> list[TankSummary]:
    tank_summary_list: list[TankSummary] = []
    summary = defaultdict(
        lambda: {
            "tank_info": Tank,
            "marks_on_gun": 0,
            "counts": {"win": 0, "lose": 0, "draw": 0},
            "totals": {
                "power": 0.0,
                "damage": 0,
                "assist_total": 0,
                "blocked": 0,
                "exp": 0,
                "credits": 0.0,
                "life_time": 0,
            },
        }
    )

    for detail_record in detail_record_list:
        tank_data = summary[detail_record.tank_info.name]
        tank_data["tank_info"] = detail_record.tank_info
        tank_data["marks_on_gun"] = detail_record.marks_on_gun
        _tally_result(tank_data["counts"], detail_record.records_basic.is_win)

        t = tank_data["totals"]
        t["power"] += detail_record.power
        t["damage"] += detail_record.damage_dealt
        t["assist_total"] += detail_record.assist_total
        t["blocked"] += detail_record.blocked
        t["exp"] += detail_record.exp
        t["credits"] += detail_record.credits
        t["life_time"] += detail_record.life_time

    for data in summary.values():
        total_count = sum(data["counts"].values())
        c = data["counts"]
        t = data["totals"]
        tank_summary_list.append(
            TankSummary(
                tank_info=data["tank_info"],
                gun_marks=data["marks_on_gun"],
                win_rate=round(c["win"] / total_count * 100, 2),
                total_count=total_count,
                win_count=c["win"],
                lose_count=c["lose"],
                draw_count=c["draw"],
                avg_power=round(t["power"] / total_count, 2),
                avg_damage=round(t["damage"] / total_count, 2),
                avg_assist_total=round(t["assist_total"] / total_count, 2),
                avg_block=round(t["blocked"] / total_count, 2),
                avg_exp=round(t["exp"] / total_count, 2),
                avg_credits=round(t["credits"] / total_count, 2),
                avg_life_time=round(t["life_time"] / total_count),
            )
        )

    tank_summary_list.sort(
        key=lambda x: (x.total_count, x.tank_info.tier), reverse=True
    )
    return tank_summary_list
