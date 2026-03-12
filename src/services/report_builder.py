
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from data.plugins.astrbot_plugin_wot.src.domain.models.report import (
    FinalSummary,
    OverallSummary,
    RecordsBasic,
    RecordsDetail,
    Tank,
    TankSummary,
)
from data.plugins.astrbot_plugin_wot.src.services.record_query_service import get_detail_record_single

def get_final_summary(detail_record_list: list[RecordsDetail], title: str) -> FinalSummary:
    return FinalSummary(
        summary_title=title,
        query_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        last_battle_time=datetime.fromtimestamp(float(detail_record_list[0].records_basic.start_time)).strftime("%Y-%m-%d %H:%M:%S"),
        overall_summary=_calculate_overall_summary(detail_record_list),
        tank_summary=_calculate_tank_summary(detail_record_list),
    )


def get_detail_record_list(player_name: str, arena_list: list[RecordsBasic]) -> list[RecordsDetail]:
    detail_record_list: list[RecordsDetail] = []

    # 使用线程池，max_workers 建议设为 5-10
    with ThreadPoolExecutor(max_workers=5) as executor:
        # 提交所有任务
        future_to_arena = {
            executor.submit(get_detail_record_single, player_name, arena): arena
            for arena in arena_list
        }

        # 按照任务完成的顺序获取结果
        for future in as_completed(future_to_arena):
            result = future.result()
            if result:
                detail_record_list.append(result)

    # 多线程返回是乱序的，最后按时间排下序
    detail_record_list.sort(key=lambda x: x.records_basic.start_time, reverse=True)
    return detail_record_list

def _calculate_overall_summary(detail_record_list: list[RecordsDetail]) -> OverallSummary:
    # 1. 初始化累加变量
    total_count = len(detail_record_list)
    win_count = 0
    lose_count = 0
    draw_count = 0
    # 用于计算场均值
    sums = {
        "power": 0.0,
        "damage": 0,
        "blocked": 0,
        "assist": 0,
        "exp": 0,
        "credits": 0.0,
        "life_time": 0,
        "tier": 0
    }
    # 2. 遍历累加
    for detail_record in detail_record_list:
        if detail_record.records_basic.is_win=='1':
            win_count += 1
        elif detail_record.records_basic.is_win =='0':
            lose_count += 1
        elif detail_record.records_basic.is_win =='2':
            draw_count +=1
        sums["power"] += detail_record.power
        sums["damage"] += detail_record.damage_dealt
        sums["blocked"] += detail_record.blocked
        sums["assist"] += detail_record.assist_total
        sums["exp"] += detail_record.exp
        sums["credits"] += detail_record.credits
        sums["life_time"] += detail_record.life_time
        sums["tier"] += detail_record.tank_info.tier

        # 3. 计算最终平均指标
    overall_summary = OverallSummary(
        avg_tier= round(sums["tier"] / total_count, 1),
        win_rate=round(win_count/total_count*100,2),
        total_count=total_count,
        win_count = win_count,
        lose_count= lose_count,
        draw_count= draw_count,
        avg_power=round(sums["power"] / total_count, 2),
        avg_damage=round(sums["damage"] / total_count, 2),
        avg_assist_total = round(sums["assist"] / total_count, 2),
        avg_block=round(sums["blocked"] / total_count, 2),
        avg_exp=round(sums["exp"] / total_count, 2),
        avg_credits=round(sums["credits"] / total_count, 2),
        avg_life_time=round(sums['life_time'] / total_count)
    )
    return overall_summary


def _calculate_tank_summary(detail_record_list: list[RecordsDetail]) -> list[TankSummary]:

    tank_summary_list: list[TankSummary] = []
    # 使用字典存储每个坦克的汇总数据
    # key: tank_title, value: dict(汇总数据)
    summary = defaultdict(lambda: {
        'tank_info': Tank,
        "marks_on_gun": 0,
        "total_count": 0,
        "win_count": 0,
        "lose_count": 0,
        "draw_count": 0,
        "total_power": 0.0,
        "total_damage": 0,
        "assist_total": 0,
        "total_blocked": 0,
        "total_exp": 0,
        "total_credits": 0.0,
        "total_life_time": 0
    })

    for detail_record in detail_record_list:
        tank_count = summary[detail_record.tank_info.name]
        # 基础静态属性（取最新一场的即可）
        tank_count['tank_info']=detail_record.tank_info
        tank_count["marks_on_gun"] = detail_record.marks_on_gun
        # 累计数据
        tank_count["total_count"] += 1
        if detail_record.records_basic.is_win=='1':
            tank_count["win_count"] += 1
        elif detail_record.records_basic.is_win == '0':
            tank_count["lose_count"] += 1
        elif detail_record.records_basic.is_win == '2':
            tank_count["draw_count"] += 1

        tank_count["total_power"] += detail_record.power
        tank_count["total_damage"] += detail_record.damage_dealt
        tank_count["assist_total"] += detail_record.assist_total
        tank_count["total_blocked"] += detail_record.blocked
        tank_count["total_exp"] += detail_record.exp
        tank_count["total_credits"] += detail_record.credits
        tank_count["total_life_time"] += detail_record.life_time

    # 计算平均值并输出结果
    for title, data in summary.items():
        total_count = data["total_count"]
        tank_summary = TankSummary(
            tank_info= data["tank_info"],
            gun_marks=data["marks_on_gun"],
            win_rate=round(data['win_count'] / total_count * 100,2),
            total_count=total_count,
            win_count=data["win_count"],
            lose_count=data["lose_count"],
            draw_count=data["draw_count"],
            avg_power=round(data["total_power"] / total_count, 2),
            avg_damage=round(data["total_damage"] / total_count, 2),
            avg_assist_total=round(data["assist_total"] / total_count, 2),
            avg_block=round(data["total_blocked"] / total_count,2),
            avg_exp=round(data["total_exp"] / total_count, 2),
            avg_credits=round(data["total_credits"] / total_count, 2),
            avg_life_time=round(data["total_life_time"] / total_count)
        )
        tank_summary_list.append(tank_summary)
    tank_summary_list.sort(key=lambda x: (x.total_count, x.tank_info.tier), reverse=True)
    return tank_summary_list
