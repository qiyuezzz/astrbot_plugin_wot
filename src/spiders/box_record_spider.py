import json
import re
import time
from datetime import datetime, timedelta
from astrbot.api import logger
from data.plugins.astrbot_plugin_wot.src.http.request_context import wot_box_detail_record_config, wot_box_records_config
from data.plugins.astrbot_plugin_wot.src.model.report import RecordsBasic, RecordsDetail
from data.plugins.astrbot_plugin_wot.src.util.data_utils import get_tank_info_by_name
from data.plugins.astrbot_plugin_wot.src.http.http_client import HttpClient

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


def get_detail_record_single(player_name:str,arena:RecordsBasic) -> RecordsDetail:
    """单个详情请求的逻辑，封装成函数供线程调用"""
    # 1. 深度拷贝配置，防止线程间干扰
    client = HttpClient()
    params = wot_box_detail_record_config.build_params()
    params["pn"] = player_name
    params['arena_id'] = arena.arena_id
    res = client.send_get(wot_box_detail_record_config,params)
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

def _get_arena_page(player_name:str,page_num:int) ->list[RecordsBasic]:
    """获取战绩列表"""
    client = HttpClient()
    arena_list: list[RecordsBasic] = []
    required_keys = {'arena_id', 'is_win', 'gui_type', 'start_time'}
    params = wot_box_records_config.build_params()
    params["pn"] = player_name
    params["p"] = page_num
    res = client.send_get(wot_box_records_config,params)
    res_data = res.json()
    data = res_data['data']['arenas']
    for record in data:
        # 只获取标准对局（gui_type="1"）
        if record.get("gui_type") != "1":
            continue
        filtered_record = {k: v for k, v in record.items() if k in required_keys}
        arena_list.append(RecordsBasic(**filtered_record))
    return arena_list

