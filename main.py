from typing import Union

import astrbot.api.message_components as Comp
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from data.plugins.astrbot_plugin_wot.src.config.message import WotBindMsg, CheckBindMsg
from data.plugins.astrbot_plugin_wot.src.config.constants import report_dir_path
from data.plugins.astrbot_plugin_wot.src.handler.command_handler import get_record_today, get_record_yesterday, \
    get_record_two_days, get_record_three_days
from data.plugins.astrbot_plugin_wot.src.spiders.tank_info_spider import get_all_tank_info
from data.plugins.astrbot_plugin_wot.src.util.data_utils import write_binding_data, binding_check


@register("astrbot_plugin_wot", "zzc", "查询坦克世界效率和战绩", "1.0.0")
class MyPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)

    async def initialize(self):
        """可选择实现异步的插件初始化方法，当实例化该插件类之后会自动调用该方法。"""


    @filter.event_message_type(filter.EventMessageType.ALL)
    @filter.event_message_type(filter.EventMessageType.GROUP_MESSAGE)
    async def command_router(self, event: AstrMessageEvent):
        """监听所有"""
        user_name = event.get_sender_name()
        message_str = event.message_str
        # 匹配触发词
        if message_str in ['今日效率', '今日战绩']:
            # 因为 get_today_performance 里面有 yield，所以需要异步迭代
            async for result in self.get_today_performance(event):
                yield result
            return  # 触发后直接结束
        if message_str in['昨日效率','昨日战绩']:
            async for result in self.get_yesterday_performance(event):
                yield result
            return  # 触发后直接结束
        if message_str in['两日效率','两日战绩']:
            async for result in self.get_two_days_performance(event):
                yield result
            return  # 触发后直接结束
        if message_str in['三日效率','三日战绩']:
            async for result in self.get_three_days_performance(event):
                yield result
            return  # 触发后直接结束

    @filter.command("wot绑定")
    async def wot_bind_player_name(self, event: AstrMessageEvent,player_name:str ):
        """绑定玩家游戏名称"""
        send_id = event.get_sender_id()
        message_chain = event.get_messages()
        logger.info(message_chain)
        if await write_binding_data(send_id,player_name):
            msg=WotBindMsg.success(player_name)
        else:
            msg=WotBindMsg.fail(player_name)
        yield event.plain_result(msg)

    @filter.command("今日效率",alias={"今日战绩"})
    async def get_today_performance(self, event: AstrMessageEvent):
        """查询今日效率"""
        send_id = event.get_sender_id()
        message_chain = event.get_messages()
        logger.info(message_chain)
        exist_flag = binding_check(send_id)
        if exist_flag:
            get_record_today(send_id)
            res =Comp.Image.fromFileSystem(f"{report_dir_path}/{send_id}.png")
        else:
            res =Comp.Plain(CheckBindMsg.failed())
        chain: list[Union[Comp.At, Comp.Image, Comp.Plain]] = [
            Comp.At(qq=send_id),res
        ]
        yield event.chain_result(chain)
    @filter.command("昨日效率",alias={"昨日战绩"})
    async def get_yesterday_performance(self, event: AstrMessageEvent):
        """查询昨日效率"""
        send_id = event.get_sender_id()
        message_chain = event.get_messages()
        logger.info(message_chain)
        get_record_yesterday(send_id)
        chain = [
            Comp.At(qq=send_id),  # At 消息发送者
            Comp.Image.fromFileSystem(f"{report_dir_path}/{send_id}.png"),  # 从本地文件目录发送图片
        ]
        yield event.chain_result(chain)

    @filter.command("两日效率", alias={"两日战绩"})
    async def get_two_days_performance(self, event: AstrMessageEvent):
        """查询两日效率"""
        send_id = event.get_sender_id()
        message_chain = event.get_messages()
        logger.info(message_chain)
        get_record_two_days(send_id)
        chain = [
            Comp.At(qq=send_id),  # At 消息发送者
            Comp.Image.fromFileSystem(f"{report_dir_path}/{send_id}.png"),  # 从本地文件目录发送图片
        ]
        yield event.chain_result(chain)


    @filter.command("三日效率", alias={"三日战绩"})
    async def get_three_days_performance(self, event: AstrMessageEvent):
        """查询三日效率"""
        send_id = event.get_sender_id()
        message_chain = event.get_messages()
        logger.info(message_chain)
        get_record_three_days(send_id)
        chain = [
            Comp.At(qq=send_id),  # At 消息发送者
            Comp.Image.fromFileSystem(f"{report_dir_path}/{send_id}.png"),  # 从本地文件目录发送图片
        ]
        yield event.chain_result(chain)

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
