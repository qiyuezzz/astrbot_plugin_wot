from data.plugins.astrbot_plugin_wot.src.model.player import AccountInfo
from data.plugins.astrbot_plugin_wot.src.service.account_service import account_bind
from data.plugins.astrbot_plugin_wot.src.service.report_service import get_report_data_by_days
from data.plugins.astrbot_plugin_wot.src.service.wot_data_service import update_tank_info


def update_all_tank_info():
    """更新全部坦克信息"""
    return update_tank_info()

async def bind_user_name(send_id:str, msg:str)  -> AccountInfo | None:
    """绑定玩家名称"""
    return  await account_bind(send_id,msg)

def get_record_today(send_id:str):
    """查询今日效率"""
    get_report_data_by_days(send_id,1,title = '今日战绩')

def get_record_yesterday(send_id: str):
    """查询昨日效率"""
    get_report_data_by_days(send_id, -1, title='昨日战绩')

def get_record_two_days(send_id:str):
    """查询两日效率"""
    get_report_data_by_days(send_id, 2, title='两日战绩')

def get_record_three_days(send_id:str):
    """查询三日效率"""
    get_report_data_by_days(send_id, 3, title='三日战绩')
