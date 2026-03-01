import threading
from data.plugins.astrbot_plugin_wot.src.handler.command_handler import update_all_tank_info
import schedule
import time
from astrbot.api import logger

def run_scheduler():
    def daily_task():
        logger.info("开始执行每日任务...")
        update_all_tank_info()
        logger.info("任务完成")

    schedule.every().day.at("23:32").do(daily_task)

    while True:
        schedule.run_pending()
        time.sleep(1)


def start_timer_thread():
    # 创建一个守护线程，专门跑定时任务
    t = threading.Thread(target=run_scheduler, daemon=True)
    t.start()
    logger.info("定时任务线程已启动")
# 在插件启动时创建这个任务
start_timer_thread()