import json
import re

import aiofiles
from astrbot.api import logger
from data.plugins.astrbot_plugin_wot.model.enum_wot import NationEnum, TankTypeEnum, TankRoleEnum
from data.plugins.astrbot_plugin_wot.model.player_info import Tank, WotRenderContext
from html2image import Html2Image
from jinja2 import FileSystemLoader,Environment

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

def get_tank_info_by_name(tank_name) -> Tank:
    with open('data/plugins/astrbot_plugin_wot/static/json/wot_tanks_full.json', 'r', encoding='utf-8') as f:
        tanks_full_info = json.load(f)
    tank_full_info = tanks_full_info[tank_name]
    tank = Tank(
        name = tank_full_info['name'],
        vehicle_cd=tank_full_info['vehicle_cd'],
        tier=tank_full_info['tier'],
        premium=tank_full_info['premium'],
        nation = NationEnum.from_code(tank_full_info['nation']),
        type=TankTypeEnum.from_code(tank_full_info['type']),
        role = TankRoleEnum.from_code(tank_full_info['role']),
    )
    return tank

# 读取绑定数据
def read_binding_data(send_id:str) -> str:
    try:
        with open("data/plugins/astrbot_plugin_wot/static/json/player_name_binding.json", "r", encoding="utf-8") as f:
            bind_data = json.load(f)
            player_name = bind_data[send_id]
        return player_name if player_name else None
    except Exception as e:
        logger.error(f"读取绑定数据失败：{e}")
        return '读取绑定数据失败'

# 写入绑定数据
async def write_binding_data(qq_id:str,player_name:str):
    bind_data = {qq_id: player_name}
    try:
        async with aiofiles.open("data/plugins/astrbot_plugin_wot/static/json/player_name_binding.json", "w", encoding="utf-8") as f:
            await f.write(json.dumps(bind_data, ensure_ascii=False, indent=4))
    except Exception as e:
        logger.error(f"写入绑定数据失败：{e}")

def format_wot_time(seconds):
    if not seconds: return "0'0\""
    m, s = divmod(round(float(seconds)), 60)
    return f"{m}分{s:02d}秒"

def general_image(send_id:str,wot_render_context:WotRenderContext):
    #生成图片
    env = Environment(loader=FileSystemLoader('.'))
    env.filters['wot_time'] = format_wot_time
    output_dir = 'data/plugins/astrbot_plugin_wot/static/report'
    template = env.get_template('data/plugins/astrbot_plugin_wot/static/template/report_template.j2')
    html_output = template.render(ctx=wot_render_context)
    with open(f'data/plugins/astrbot_plugin_wot/static/report/{send_id}.html', 'w', encoding='utf-8') as f:
        f.write(html_output)
    hti = Html2Image(output_path=output_dir,custom_flags=['--no-sandbox', '--disable-gpu'])
    hti.screenshot(html_file=f'data/plugins/astrbot_plugin_wot/static/report/{send_id}.html', save_as=f'{send_id}.png', size=(2560, 2800))
