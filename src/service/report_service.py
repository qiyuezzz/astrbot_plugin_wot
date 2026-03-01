from pathlib import Path

from html2image import Html2Image
from jinja2 import FileSystemLoader, Environment

from astrbot.api import logger
from data.plugins.astrbot_plugin_wot.src.config.constants import template_dir_path, template_path, font_path, \
    report_dir_path
from data.plugins.astrbot_plugin_wot.src.model.report import FinalSummary, WotRenderContext
from data.plugins.astrbot_plugin_wot.src.service.box_record_service import get_detail_record_list, get_final_summary
from data.plugins.astrbot_plugin_wot.src.service.box_stats_service import WotBoxService
from data.plugins.astrbot_plugin_wot.src.spiders.box_record_spider import get_arena_list_by_days, get_arena_list_by_times
from data.plugins.astrbot_plugin_wot.src.util.data_utils import read_binding_data

def get_report_data_by_days(send_id: str, days: int, title: str):
    """根据玩家名称按天数获取数据"""
    return _get_report_data_base(
        send_id=send_id,
        title=title,
        get_arena_list_func=get_arena_list_by_days,
        func_param=days
    )


def get_report_data_by_times(send_id: str, times: int, title: str):
    """根据玩家名称按场次获取数据"""
    return _get_report_data_base(
        send_id=send_id,
        title=title,
        get_arena_list_func=get_arena_list_by_times,
        func_param=times
    )

def _get_report_data_base(send_id: str, title: str, get_arena_list_func, func_param: int):
    """
    战绩报告数据获取通用核心函数（内部函数）
    :param send_id: 用户ID
    :param title: 报告标题
    :param get_arena_list_func: 获取对局列表的函数（get_arena_list_by_days/get_arena_list_by_times）
    :param func_param: 传给获取对局列表函数的参数（天数/场次）
    :return: WotRenderContext 渲染上下文
    """
    try:
        # 1. 读取绑定的玩家名称
        player_name = read_binding_data(send_id)
        if not player_name:
            raise ValueError(f"用户{send_id}未绑定玩家名称，无法获取战绩数据")

        # 2. 获取玩家基础统计信息
        wot_box_service = WotBoxService()
        player_stats = wot_box_service.get_player_stats(player_name)
        if not player_stats or len(player_stats) < 2:
            raise ValueError(f"获取玩家{player_name}基础统计信息失败，返回数据异常")

        # 3. 获取对局列表（按天数/场次，由传入的函数决定）
        arena_list = get_arena_list_func(player_name, func_param)

        # 4. 处理对局数据并生成汇总
        if arena_list:
            detail_arena_list = get_detail_record_list(player_name, arena_list)
            final_summary = get_final_summary(detail_arena_list, title)
        else:
            logger.warning(f"玩家{player_name}未查询到{title}对应的对局数据")
            final_summary = FinalSummary(summary_title=title)

        # 5. 构建渲染上下文
        wot_render_context = WotRenderContext(
            player_stats=player_stats[0],
            frequent_tank=player_stats[1],
            final_summary=final_summary
        )
        logger.info(f"成功生成{title}渲染上下文：{wot_render_context}")

        # 6. 生成报告
        _generate_report(send_id, wot_render_context)

    except Exception as e:
        logger.error(f"获取{title}数据失败（用户{send_id}）：{str(e)}", exc_info=True)
        raise  # 抛出异常让上层处理，也可注释掉仅记录日志


def _generate_report(send_id: str, wot_render_context: WotRenderContext, report_path=None):
    """
    生成WOT战绩报告（重构版）
    :param send_id: 用户ID（用于命名报告文件）
    :param wot_render_context: 渲染模板的上下文数据
    """
    # ========== 1. 路径标准化（转为Path对象，兼容Windows/Linux） ==========
    # 模板目录路径
    template_dir = Path(template_dir_path).resolve()
    # 模板文件完整路径
    template_file = Path(template_path).resolve()
    # 报告输出目录
    report_dir = Path(report_dir_path).resolve()
    # 字体文件路径
    font_file = Path(font_path).resolve()

    # 从模板文件路径中提取纯文件名（如：report_template.j2）
    template_filename = template_file.name
    # 确保报告输出目录存在（不存在则创建）
    report_dir.mkdir(parents=True, exist_ok=True)

    # ========== 3. 初始化Jinja2环境 ==========
    env = Environment(
        loader=FileSystemLoader(str(template_dir)),  # 传入模板目录字符串
        autoescape=False,  # HTML模板建议关闭autoescape
        trim_blocks=True,  # 清理模板多余空格
        lstrip_blocks=True
    )
    # 注册自定义过滤器
    env.filters['wot_time'] = _format_wot_time
    env.filters['win_rate'] = _format_win_rate

    # ========== 4. 加载模板并渲染HTML ==========
    # 仅传入模板文件名（核心修复：不再传完整路径）
    template = env.get_template(template_filename)
    # 渲染模板（传入上下文+字体文件绝对路径）
    html_output = template.render(
        ctx=wot_render_context,
        font_url=str(font_file)  # 传入字体绝对路径，避免相对路径问题
    )

    # ========== 5. 保存HTML文件 ==========
    html_file_path = report_dir / f"{send_id}.html"
    with open(html_file_path, 'w', encoding='utf-8') as f:
        f.write(html_output)
    logger.info(f"HTML文件已保存：{html_file_path}")

    # ========== 6. 转换HTML为PNG图片 ==========
    # 初始化Html2Image（指定输出目录为绝对路径）
    hti = Html2Image(
        output_path=str(report_dir),
        custom_flags=['--no-sandbox', '--disable-gpu']
    )
    # 生成PNG（size建议用元组，避免解析问题）
    png_file_name = f"{send_id}.png"
    hti.screenshot(
        html_file=str(html_file_path),
        save_as=png_file_name,
        size=(2560, 2800)
    )
    png_file_path = report_dir / png_file_name
    logger.info(f"PNG报告生成成功：{png_file_path}")

def _format_wot_time(seconds):
    """
    将秒数格式化为分秒格式的时间字符串
    :param: seconds (float/int/None): 秒数，可以为数字类型或None/空值
    :return: 格式化后的时间字符串，格式为"X分XX秒"，如果输入为空则返回'0分0秒'
    """
    if not seconds: return "0分0秒"
    # 计算分钟和秒数
    m, s = divmod(round(float(seconds)), 60)
    return f"{m}分{s:02d}秒"

def _format_win_rate(win_rate: float | None) -> str:
    """
    胜率格式化过滤器：忽略末尾0，添加%符号
    :param win_rate: 原始胜率（float/None）
    :return: 格式化后的字符串（如60%、62.1%、66.67%）
    """
    # 容错：空值/0值处理
    if win_rate is None or win_rate == 0:
        return "0%"

    # 核心逻辑：保留2位小数 → 去掉末尾0 → 去掉多余小数点 → 加%
    formatted = f"{win_rate:.2f}".rstrip('0').rstrip('.')
    return f"{formatted}%"