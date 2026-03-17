import os

from data.plugins.astrbot_plugin_wot.src.settings.storage import (
    get_bind_data_path,
    get_plugin_package_dir,
    get_plugin_report_dir,
    get_plugin_resources_dir,
    get_plugin_temp_dir,
    get_tank_info_path,
)

PLUGIN_DIR = get_plugin_package_dir()
RESOURCES_DIR = get_plugin_resources_dir()
RUNTIME_DIR = get_plugin_temp_dir()

# 玩家和qq绑定数据
bind_data_path = get_bind_data_path()
# 全量坦克信息数据
tank_info_path = get_tank_info_path()

# 模板渲染字体
font_path = RESOURCES_DIR / "static" / "font" / "SourceHanSansSC-Medium.otf"
# 模板
template_path = RESOURCES_DIR / "static" / "templates" / "report_template.j2"
# 模板文件夹路径
template_dir_path = RESOURCES_DIR / "static" / "templates"
# 最终报表保存路径
report_dir_path = get_plugin_report_dir()


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


report_image_width = _env_int("WOT_REPORT_IMAGE_WIDTH", 2560)
report_image_min_height = _env_int("WOT_REPORT_IMAGE_MIN_HEIGHT", 2800)
report_image_base_height = _env_int("WOT_REPORT_IMAGE_BASE_HEIGHT", 500)
report_image_per_summary_row = _env_int("WOT_REPORT_IMAGE_PER_SUMMARY_ROW", 80)
report_image_max_height = _env_int("WOT_REPORT_IMAGE_MAX_HEIGHT", 12000)
report_image_retry_rows_threshold = _env_int("WOT_REPORT_RETRY_ROWS_THRESHOLD", 999)
report_image_retry_height_scale = _env_float("WOT_REPORT_RETRY_HEIGHT_SCALE", 1.25)
report_image_retry_extra_height = _env_int("WOT_REPORT_RETRY_EXTRA_HEIGHT", 600)

# 报表上下文缓存（减少短时间重复请求）
report_query_cache_ttl_seconds = _env_int("WOT_REPORT_CACHE_TTL_SECONDS", 45)
report_query_cache_max_entries = _env_int("WOT_REPORT_CACHE_MAX_ENTRIES", 128)
report_query_inflight_wait_timeout_seconds = _env_int(
    "WOT_REPORT_INFLIGHT_WAIT_TIMEOUT_SECONDS", 30
)
