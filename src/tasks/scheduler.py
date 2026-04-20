import asyncio
import threading
import time

import schedule

from astrbot.api import logger
from data.plugins.astrbot_plugin_wot.src.application.tank_sync_service import (
    sync_all_tank_info,
)

_scheduler_started = False
_scheduler_thread: threading.Thread | None = None


def run_scheduler():
    """运行定时任务调度器"""

    def daily_task():
        """每日定时任务：同步坦克信息"""
        logger.info("开始执行每日坦克数据同步任务...")
        try:
            # 在新线程中创建独立的事件循环
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(sync_all_tank_info())
                logger.info(f"每日任务完成: {result}")
            finally:
                loop.close()
        except Exception as e:
            logger.error(f"每日任务执行失败: {e}")

    schedule.every().day.at("10:00").do(daily_task)
    logger.info("定时任务调度器已启动，下次执行时间: 明天 10:00")

    while True:
        schedule.run_pending()
        time.sleep(60)  # 改为 60 秒检查一次，降低 CPU 占用


def start_timer_thread():
    """启动定时任务线程（确保只启动一次）"""
    global _scheduler_started, _scheduler_thread

    if _scheduler_started:
        logger.debug("定时任务线程已存在，跳过启动")
        return

    _scheduler_thread = threading.Thread(
        target=run_scheduler, daemon=True, name="WotScheduler"
    )
    _scheduler_thread.start()
    _scheduler_started = True
    logger.info("定时任务线程已启动")


def stop_timer_thread():
    """停止定时任务线程（可选，用于插件卸载时清理）"""
    global _scheduler_started, _scheduler_thread

    if _scheduler_thread and _scheduler_thread.is_alive():
        # 由于是 daemon 线程，会在主程序退出时自动停止
        logger.info("定时任务线程将在主程序退出时自动停止")

    _scheduler_started = False
    _scheduler_thread = None
