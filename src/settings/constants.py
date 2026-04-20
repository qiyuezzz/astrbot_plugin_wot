import json
import os
from pathlib import Path
from typing import Any

from data.plugins.astrbot_plugin_wot.src.settings.storage import (
    get_bind_data_path,
    get_plugin_package_dir,
    get_plugin_report_dir,
    get_plugin_resources_dir,
    get_plugin_temp_dir,
    get_tank_info_path,
)

_plugin_config: dict[str, Any] = {}


def set_plugin_config(config: dict[str, Any]) -> None:
    """设置插件配置"""
    global _plugin_config
    _plugin_config = config


def get_plugin_config() -> dict[str, Any]:
    """获取插件配置"""
    return _plugin_config or _load_config_from_file()


def _load_config_from_file() -> dict[str, Any]:
    """从配置文件直接读取配置"""
    from astrbot.core.utils.astrbot_path import get_astrbot_config_path

    config_path = Path(get_astrbot_config_path()) / "astrbot_plugin_wot_config.json"
    if config_path.exists():
        try:
            with open(config_path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def is_h2i_enabled() -> bool:
    """检查是否启用 H2I 本地渲染（动态读取配置）"""
    config = get_plugin_config()
    value = config.get("enable_h2i", False)
    if isinstance(value, str):
        value = value.lower() in ("true", "1", "yes")
    return bool(value)


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
report_image_retry_rows_threshold = _env_int("WOT_REPORT_RETRY_ROWS_THRESHOLD", 80)
report_image_retry_height_scale = _env_float("WOT_REPORT_RETRY_HEIGHT_SCALE", 1.25)
report_image_retry_extra_height = _env_int("WOT_REPORT_RETRY_EXTRA_HEIGHT", 600)


def get_cache_ttl_seconds() -> int:
    """获取缓存 TTL（优先从插件配置读取）"""
    return get_plugin_config().get(
        "cache_ttl_seconds",
        _env_int("WOT_REPORT_CACHE_TTL_SECONDS", 45),
    )


def get_cache_max_entries() -> int:
    """获取缓存最大条目数（优先从插件配置读取）"""
    return get_plugin_config().get(
        "cache_max_entries",
        _env_int("WOT_REPORT_CACHE_MAX_ENTRIES", 128),
    )


def get_inflight_wait_timeout() -> int:
    """获取并发请求等待超时（优先从插件配置读取）"""
    return get_plugin_config().get(
        "inflight_wait_timeout_seconds",
        _env_int("WOT_REPORT_INFLIGHT_WAIT_TIMEOUT_SECONDS", 30),
    )
