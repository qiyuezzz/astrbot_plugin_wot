import copy
import json
import re
from collections import defaultdict
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from astrbot.api import logger
from data.plugins.astrbot_plugin_wot.src.config.request import wot_box_detail_record_config, wot_box_records_config
from data.plugins.astrbot_plugin_wot.src.model.report import RecordsBasic, RecordsDetail, Tank, FinalSummary, TankSummary, OverallSummary
from data.plugins.astrbot_plugin_wot.src.util.data_utils import get_tank_info_by_name
from data.plugins.astrbot_plugin_wot.src.util.http_client import send_get_request


def _get_arena_page(player_name:str,page_num:int) ->list[RecordsBasic]:
    """获取战绩列表"""
    arena_list: list[RecordsBasic] = []
    required_keys = {'arena_id', 'is_win', 'gui_type', 'start_time'}
    config = wot_box_records_config.copy()  # 拷贝配置防止多线程冲突
    config.params["pn"] = player_name
    config.params["p"] = page_num
    res = send_get_request(config)
    res_data = res.json()
    data = res_data['data']['arenas']
    for record in data:
        # 只获取标准对局（gui_type="1"）
        if record.get("gui_type") != "1":
            continue
        filtered_record = {k: v for k, v in record.items() if k in required_keys}
        arena_list.append(RecordsBasic(**filtered_record))
    return arena_list

def get_arena_list_by_times(player_name:str,times:int) -> list[RecordsBasic]:
    """获取最近N场的标准对局战绩"""
    all_valid_records: list[RecordsBasic] = []
    return all_valid_records

def get_arena_list_by_days(player_name: str, days: int = 1) -> list[RecordsBasic]:
    """
    基于get_arena_page函数，获取最近N天的标准对局战绩
    无页数限制，通过时间戳自动终止翻页
    :param player_name: 玩家名称
    :param days: 要获取的天数（默认1天）
    :return: 符合条件的战绩列表
    """
    # 1. 计算时间阈值：N天前的零点时间戳
    current_time = datetime.now()

    if days>0:
        end_timestamp_threshold = int(current_time.timestamp())
        time_threshold = current_time - timedelta(days=days-1)
    else:
        end_timestamp_threshold = int(current_time.replace(hour=0, minute=0, second=0, microsecond=0).timestamp())
        time_threshold = current_time - timedelta(days=abs(days))
    time_threshold = time_threshold.replace(hour=0, minute=0, second=0, microsecond=0)
    start_timestamp_threshold = int(time_threshold.timestamp())
    print(f"开始查询【{player_name}】最近{days}天的标准对局，时间阈值：{time_threshold}（戳：{start_timestamp_threshold}）,截止为{end_timestamp_threshold}")

    # 2. 初始化变量
    all_valid_records:list [RecordsBasic] =[]  # 最终结果
    seen_arena_ids = set()  # 去重
    page = 1
    stop_flag = False

    # 3. 逐页查询，直到触发终止条件
    while not stop_flag:
        try:
            print(f"正在查询第 {page} 页...")
            # 调用你提供的get_arena_page函数获取单页数据
            page_records = _get_arena_page(player_name, page)

            # 终止条件1：当前页无数据（无更多战绩）
            if not page_records:
                print(f"第 {page} 页无标准对局数据，终止查询")
                break

            # 处理当前页数据
            page_has_valid = False
            for record in page_records:
                record_timestamp = int(record.start_time)
                # 去重
                if record.arena_id in seen_arena_ids:
                    continue
                # 获取的对战列表是时间倒序排列的，对战时间比截止时间更新，跳过获取下一条，获取昨日效率时用到
                if end_timestamp_threshold<record_timestamp:
                    continue
                # 终止条件2：记录时间超出阈值（数据倒序，后续页更旧）
                try:
                    if record_timestamp < start_timestamp_threshold:
                        logger.info(f"第 {page} 页发现超出{days}天的记录，终止查询")
                        stop_flag = True
                        break
                except ValueError:
                    logger.error(f"第{page}页记录{record.arena_id}时间戳无效，跳过")
                    continue

                # 符合条件：加入结果
                all_valid_records.append(record)
                seen_arena_ids.add(record.arena_id)
                page_has_valid = True

            # 终止条件3：当前页无有效数据（都是重复/超时记录）
            if not page_has_valid and not stop_flag:
                print(f"第 {page} 页无符合时间范围的有效记录，终止查询")
                break
            page += 1

        except Exception as e:
            print(f"查询第 {page} 页时出错: {e}")
            # 单页失败，继续下一页（最多尝试2次失败后终止）
            if page > 2 and not page_has_valid:
                print("连续多页查询失败，终止")
                break
            page += 1
            time.sleep(0.5)
            continue

    # 按时间戳倒序排序（最新的在前）
    all_valid_records.sort(key=lambda x: int(x.start_time), reverse=True)
    return all_valid_records

def _get_detail_record_single(player_name:str,arena:RecordsBasic) -> RecordsDetail:
    """单个详情请求的逻辑，封装成函数供线程调用"""
    # 1. 深度拷贝配置，防止线程间干扰
    config = copy.deepcopy(wot_box_detail_record_config)
    config.params["pn"] = player_name
    config.params['arena_id'] = arena.arena_id

    res = send_get_request(config)
    raw_response = res.text
    json_match = re.search(r'\{.*\}', raw_response)
    # 获取对局结果
    data = json.loads(json_match.group())['result']
    # 获取玩家id
    player_id = int(data['player_id'])
    # 获取玩家阵营所有人数据
    player_data_list = data.get('team_a')
    # 根据玩家id匹配该玩家对局详情数据
    player_data = next((p for p in player_data_list if p['vehicle']['accountDBID'] == player_id), None)

    vehicle = player_data['vehicle']
    tank_info = get_tank_info_by_name(player_data['tank_title'])
    detail_record = RecordsDetail(
        tank_info=tank_info,
        records_basic=arena,
        exp=vehicle['xp'],
        power=round(player_data['combat'], 2),
        death_count=vehicle['deathCount'],
        damage_dealt=vehicle['damageDealt'],
        assist_radio=vehicle['damageAssistedRadio'],
        assist_track=vehicle['damageAssistedTrack'],
        assist_stun=vehicle['damageAssistedStun'],
        kills=vehicle['kills'],
        shots=vehicle['shots'],
        hits=vehicle['directHits'],
        hit_received=vehicle['directHitsReceived'],
        piercings=vehicle['piercings'],
        piercings_received=vehicle['piercingsReceived'],
        blocked=vehicle['damageBlockedByArmor'],
        marks_on_gun=vehicle['marksOnGun'],
        credits=vehicle['credits'],
        life_time=vehicle['lifeTime']
    )
    return detail_record

def get_detail_record_list(player_name:str,arena_list:list[RecordsBasic]) -> list[RecordsDetail]:
    detail_record_list: list[RecordsDetail] = []

    # 使用线程池，max_workers 建议设为 5-10
    with ThreadPoolExecutor(max_workers=8) as executor:
        # 提交所有任务
        future_to_arena = {
            executor.submit(_get_detail_record_single, player_name, arena): arena
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

def _calculate_overall_summary(detail_record_list:list[RecordsDetail]) -> OverallSummary:
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
        sums["assist"] += detail_record.total_assist
        sums["exp"] += detail_record.exp
        sums["credits"] += detail_record.credits
        sums["life_time"] += detail_record.life_time
        sums["tier"] += detail_record.tank_info.tier

        # 3. 计算最终平均指标
    overall_summary= OverallSummary(
        avg_tier= round(sums["tier"] / total_count, 1),
        win_rate=round(win_count/total_count*100,2),
        total_count=total_count,
        win_count = win_count,
        lose_count= lose_count,
        draw_count= draw_count,
        avg_power=round(sums["power"] / total_count, 2),
        avg_damage=round(sums["damage"] / total_count, 2),
        avg_total_assist = round(sums["assist"] / total_count, 2),
        avg_block=round(sums["blocked"] / total_count, 2),
        avg_exp=round(sums["exp"] / total_count, 2),
        avg_credits=round(sums["credits"] / total_count, 2),
        avg_life_time=round(sums['life_time'] / total_count)
    )
    return overall_summary


def _calculate_tank_summary(detail_record_list:list[RecordsDetail]) -> list[TankSummary]:

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
        "total_assist": 0,
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
        tank_count["total_assist"] += detail_record.total_assist
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
            avg_total_assist=round(data["total_assist"] / total_count, 2),
            avg_block=round(data["total_blocked"] / total_count,2),
            avg_exp=round(data["total_exp"] / total_count, 2),
            avg_credits=round(data["total_credits"] / total_count, 2),
            avg_life_time=round(data["total_life_time"] / total_count)
        )
        tank_summary_list.append(tank_summary)
    tank_summary_list.sort(key=lambda x: (x.total_count, x.tank_info.tier), reverse=True)
    return tank_summary_list

def get_final_summary(detail_record_list:list[RecordsDetail],title:str) -> FinalSummary:
    return FinalSummary(
        summary_title=title,
        query_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        last_battle_time=datetime.fromtimestamp(float(detail_record_list[0].records_basic.start_time)).strftime("%Y-%m-%d %H:%M:%S"),
        overall_summary=_calculate_overall_summary(detail_record_list),
        tank_summary=_calculate_tank_summary(detail_record_list),
    )
