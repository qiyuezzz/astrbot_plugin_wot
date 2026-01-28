import json
from astrbot.core import  logger
from data.plugins.astrbot_plugin_wot.src.config.constants import tank_info_path
from data.plugins.astrbot_plugin_wot.src.spiders.wot_game_spider import get_all_tank_info


def update_tank_info():
    resp =get_all_tank_info()
    resp.raise_for_status()
    result = resp.json()
    inner_data = result.get('data', {})

    params = inner_data.get('parameters', [])
    tank_rows = inner_data.get('data', [])

    # 建立名称索引字典
    name_indexed_library = {}

    for row in tank_rows:
        # 将该行所有数据与参数名一一对应
        tank_details = {params[i]: row[i] for i in range(len(params))}

        # 使用名称作为 Key
        tank_name = tank_details.get('name')
        if tank_name:
            # 如果存在重名车，可以通过组合 [名称+ID] 或者覆盖
            name_indexed_library[tank_name] = tank_details

    # 保存为 JSON
    with open(tank_info_path, 'w', encoding='utf-8') as f:
        json.dump(name_indexed_library, f, ensure_ascii=False, indent=4)

    logger.info(f"成功！已保存 {len(name_indexed_library)} 辆坦克的全字段信息。")
    logger.info(f"包含字段: {', '.join(params[:10])} ... 等共 {len(params)} 个字段")
    return f"更新成功！已保存 {len(name_indexed_library)} 辆坦克的全字段信息。"
