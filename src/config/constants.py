from pathlib import Path

from astrbot.core.utils.astrbot_path import get_astrbot_data_path

PLUGIN_DIR = Path(get_astrbot_data_path()) / "plugins" / "astrbot_plugin_wot"
RESOURCES_DIR = PLUGIN_DIR / "resources"

# 玩家和qq绑定数据
bind_data_path = RESOURCES_DIR / "static" / "data" / "player_name_binding.json"
# 全量坦克信息数据
tank_info_path = RESOURCES_DIR / "static" / "data" / "wot_tanks_full.json"

# 模板渲染字体
font_path = RESOURCES_DIR / "static" / "font" / "SourceHanSansSC-Medium.otf"
# 模板
template_path = RESOURCES_DIR / "static" / "templates" / "report_template.j2"
# 模板文件夹路径
template_dir_path = RESOURCES_DIR / "static" / "templates"
# 最终报表保存路径
report_dir_path = RESOURCES_DIR / "static" / "report"
