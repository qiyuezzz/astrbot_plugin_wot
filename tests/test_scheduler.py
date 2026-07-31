import schedule

from data.plugins.astrbot_plugin_wot.src.tasks import scheduler


def test_run_scheduler_does_not_register_global_jobs():
    existing_jobs = list(schedule.jobs)
    scheduler._scheduler_stop.set()
    try:
        scheduler.run_scheduler()
        assert schedule.jobs == existing_jobs
    finally:
        scheduler._scheduler_stop.clear()
