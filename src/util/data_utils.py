import json
import re
import aiofiles
from astrbot.api import logger
from data.plugins.astrbot_plugin_wot.src.config.constants import tank_info_path, bind_data_path
from data.plugins.astrbot_plugin_wot.src.model.enum import TankNationEnum, TankTypeEnum, TankRoleEnum
from data.plugins.astrbot_plugin_wot.src.model.report import Tank

def clean_number(text, default="0", to_int=False):
    """
    通用数字提取函数
    :param text: 原始文本 (如 "胜 822", "54%", "1,500", None)
    :param default: 匹配失败时的默认返回值
    :param to_int: 是否直接转为整数类型 (int)
    :return: 提取后的数字字符串或整数
    """
    if text is None or text == "N/A":
        return 0 if to_int else default

    # 1. 使用 findall 提取所有数字片段并合并 (处理 1,500 这种带逗号的情况)
    digits = "".join(re.findall(r'\d+', str(text)))

    # 2. 如果没提取到数字，返回默认值
    if not digits:
        return 0 if to_int else default

    # 3. 根据参数返回类型
    return int(digits) if to_int else digits

def get_player_name(message_str:str):
    command_bind_prefix = "wot绑定 "
    player_name = message_str.split(command_bind_prefix, maxsplit=1)[1]
    return player_name

def get_tank_info_by_name(tank_name) -> Tank:
    with open(tank_info_path, 'r', encoding='utf-8') as f:
        tanks_full_info = json.load(f)
    tank_full_info = tanks_full_info[tank_name]
    tank = Tank(
        name = tank_full_info['name'],
        vehicle_cd=tank_full_info['vehicle_cd'],
        tier=tank_full_info['tier'],
        premium=tank_full_info['premium'],
        nation = TankNationEnum.from_code(tank_full_info['nation']),
        type=TankTypeEnum.from_code(tank_full_info['type']),
        role = TankRoleEnum.from_code(tank_full_info['role']),
    )
    return tank

def binding_check(qq_id:str)->str | None:
    bind_data = read_binding_data(qq_id)
    print(bind_data)
    if bind_data:
        return bind_data
    else:
        return None

def read_binding_data(send_id:str) -> str | None:
    """读取绑定数据"""
    try:
        with open(bind_data_path, "r", encoding="utf-8") as f:
            bind_data = json.load(f)
            player_name = bind_data[send_id]
        return player_name if player_name else None
    except Exception as e:
        logger.error(f"读取绑定数据失败：{e}")
        return None


async def write_binding_data(qq_id: str, player_name: str) -> bool:
    """更新绑定数据：如果 Key 存在则覆盖，不存在则追加"""
    try:
        # 1. 读取现有数据
        bind_data = {}
        try:
            async with aiofiles.open(bind_data_path, "r", encoding="utf-8") as f:
                content = await f.read()
                if content.strip():  # 确保文件不为空
                    bind_data = json.loads(content)
        except FileNotFoundError:
            # 文件不存在时，初始化为空字典
            bind_data = {}

        # 2. 修改数据（如果 qq_id 已存在，会自动覆盖旧的 player_name）
        bind_data[qq_id] = player_name

        # 3. 将更新后的完整字典写回文件
        async with aiofiles.open(bind_data_path, "w", encoding="utf-8") as f:
            await f.write(json.dumps(bind_data, ensure_ascii=False, indent=4))
        return True
    except Exception as e:
        logger.error(f"操作绑定数据失败：{e}")
        return False

