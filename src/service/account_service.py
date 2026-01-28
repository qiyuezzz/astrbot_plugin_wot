from astrbot.api import logger
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