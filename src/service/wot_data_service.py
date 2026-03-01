import json
from astrbot.core import  logger
from data.plugins.astrbot_plugin_wot.src.config.constants import tank_info_path
from data.plugins.astrbot_plugin_wot.src.spiders.wot_game_spider import get_all_tank_info
from data.plugins.astrbot_plugin_wot.src.model.player import AccountInfo
from data.plugins.astrbot_plugin_wot.src.spiders.wot_game_spider import wot_account_search
from data.plugins.astrbot_plugin_wot.src.util.data_utils import write_binding_data


async def account_bind(send_id:str, player_name : str) -> AccountInfo | None:
    if len(player_name) > 14 or len(player_name) < 4:
        logger.info("用户名必须在 4 和 14 个字符之间")
        return None
    else:
        resp = wot_account_search(player_name)
        resp_dict = resp.json()
        if resp_dict['response']:
            data = resp_dict['response'][0]
            filtered_data = {k: v for k, v in data.items() if k in AccountInfo.__annotations__}
            account_info = AccountInfo(**filtered_data)
            logger.info(account_info.__str__())
            await write_binding_data(send_id,account_info.account_name)
            return account_info
        else:
            logger.info("未找到该用户")
            return None

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
