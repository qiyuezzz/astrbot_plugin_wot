import astrbot.api.message_components as Comp
from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from data.plugins.astrbot_plugin_wot.api import get_all_tank_info, get_record_today
from data.plugins.astrbot_plugin_wot.util.utils import write_binding_data


@register("astrbot_plugin_wot", "zzc", "查询坦克世界效率和战绩", "1.0.0")
class MyPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)

    async def initialize(self):
        """可选择实现异步的插件初始化方法，当实例化该插件类之后会自动调用该方法。"""

    @filter.command("wot帮助")
    async def wot_command_collection(self, event: AstrMessageEvent):
        """获取命令合集"""
        user_name = event.get_sender_name()
        message_str = event.message_str
        message_chain = event.get_messages()
        logger.info(message_chain)
        yield event.plain_result(f"Hello, {user_name}, 你发了 {message_str}!")

    @filter.command("绑定")
    async def wot_bind_player_name(self, event: AstrMessageEvent,player_name:str ):
        """绑定玩家游戏名称"""
        user_name = event.get_sender_name()
        send_id = event.get_sender_id()
        message_chain = event.get_messages()
        logger.info(message_chain)
        await write_binding_data(send_id, player_name)
        yield event.plain_result(f"Hello, {user_name}, 玩家名称为 {player_name}!,发送者id为:{send_id}")

    @filter.command("今日效率",alias={"今日战绩"})
    async def get_today_performance(self, event: AstrMessageEvent):
        """查询今日效率"""
        send_id = event.get_sender_id()
        message_chain = event.get_messages()
        logger.info(message_chain)
        get_record_today(send_id)
        chain = [
            Comp.At(qq=send_id),  # At 消息发送者
            Comp.Image.fromFileSystem(f"data/plugins/astrbot_plugin_wot/static/report/{send_id}.png"),  # 从本地文件目录发送图片
        ]
        yield event.chain_result(chain)

    @filter.command("昨日效率",alias={"昨日战绩"})
    async def get_yesterday_performance(self, event: AstrMessageEvent):
        """查询昨日效率"""
        user_name = event.get_sender_name()
        message_str = event.message_str
        message_chain = event.get_messages()
        logger.info(message_chain)
        yield event.plain_result(f"Hello, {user_name}, 你发了 {message_str}!")

    @filter.command("两日效率", alias={"两日战绩"})
    async def get_two_days_performance(self, event: AstrMessageEvent):
        """查询两日效率"""
        user_name = event.get_sender_name()
        message_str = event.message_str
        message_chain = event.get_messages()
        logger.info(message_chain)
        yield event.plain_result(f"Hello, {user_name}, 你发了 {message_str}!")

    @filter.command("三日效率", alias={"三日战绩"})
    async def get_three_days_performance(self, event: AstrMessageEvent):
        """查询三日效率"""
        user_name = event.get_sender_name()
        message_str = event.message_str
        message_chain = event.get_messages()
        logger.info(message_chain)
        yield event.plain_result(f"Hello, {user_name}, 你发了 {message_str}!")

    @filter.command("百场效率", alias={"百场战绩"})
    async def get_hundred_matches_performance(self, event: AstrMessageEvent):
        """查询百场效率"""
        user_name = event.get_sender_name()
        message_str = event.message_str
        message_chain = event.get_messages()
        logger.info(message_chain)
        yield event.plain_result(f"Hello, {user_name}, 你发了 {message_str}!")
    
    @filter.command("同步坦克",alias={"更新坦克"})
    async def get_full_tank_info(self, event: AstrMessageEvent):
        """从官网同步坦克信息"""
        message_chain = event.get_messages()
        logger.info(message_chain)
        get_all_tank_info()
        yield event.plain_result("已同步坦克基本信息")
async def terminate(self):
        """可选择实现异步的插件销毁方法，当插件被卸载/停用时会调用。"""
