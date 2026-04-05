import asyncio
import threading
import time

import schedule

from astrbot.api import logger
from data.plugins.astrbot_plugin_wot.src.application.tank_sync_service import (
    sync_all_tank_info,
)

_scheduler_started = False


def run_scheduler():
    def daily_task():
        logger.info("开始执行每日任务...")
        asyncio.run(sync_all_tank_info())
        logger.info("任务完成")

    schedule.every().day.at("10:00").do(daily_task)

    while True:
        schedule.run_pending()
        time.sleep(1)


def start_timer_thread():
    global _scheduler_started
    if _scheduler_started:
        return
    t = threading.Thread(target=run_scheduler, daemon=True)
    t.start()
    _scheduler_started = True
    logger.info("定时任务线程已启动")
