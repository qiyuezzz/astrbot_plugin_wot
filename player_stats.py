import json
import re

from bs4 import BeautifulSoup

from data.plugins.astrbot_plugin_wot.config.config import wot_box_config
from data.plugins.astrbot_plugin_wot.model.player_info import FrequentTank, PlayerStats
from data.plugins.astrbot_plugin_wot.util.request_utils import send_get_request
from data.plugins.astrbot_plugin_wot.util.utils import get_tank_info_by_name, clean_number


#获取雷达图数据
def get_radar_data(html_content):
    """
    从脚本字符串中提取雷达图的 5 个维度数据
    """
    # 正则表达式解释：
    # App\.init\(\[ 表示匹配 App.init([
    # (.*?) 捕获括号内的所有内容
    # \] 表示匹配 ]
    pattern = r'App\.init\(\[\s*(.*?)\s*\]\)'

    match = re.search(pattern, html_content, re.S)
    if match:
        raw_data = match.group(1)
        # raw_data 现在类似于 "Math.min(2000, 1194), Math.min(2000, 1155), ..."

        # 提取所有的数字
        numbers = re.findall(r'\d+', raw_data)
        print(numbers)
        #numbers的实例结构['2000', '1194', '2000', '1155', '2000', '1116', '2000', '0', '2000', '1142']
        #
        radar_values = [int(n) for n in numbers[1::2]]
        return radar_values
    return []

def get_player_stats_wot_box(player_name: str) ->tuple[PlayerStats,list[FrequentTank]]:
    """
    获取玩家统计数据页面
    :param player_name: 玩家游戏名称
    :return: 暂无
    """
    stats_data = {
        'name': player_name,
        'update_time':'',
        'power':'',
        'power_float':'',
        'win_rate': '',
        'total_count': '',
        'win_count': '',
        'lose_count': '',
        'hit_rate': '',
        'avg_tier':'',
        'avg_damage':'',
        'avg_exp':'',
        'avg_kill':'',
        'avg_occupy':'',
        'avg_defense':'',
        'avg_discovery':'',
        'comment':'',
        'radar_data': [],
    }
    wot_box_config.params['pn']=player_name
    res = send_get_request(wot_box_config)
    soup = BeautifulSoup(res.text, 'html.parser')
    other_info_div = soup.select_one('.other-info')
    # 获取效率部分
    stats_data['power'] = other_info_div.find('span', class_='num').get_text()
    stats_data['power_float'] = other_info_div.find('span',class_='float-num').get_text()

    # ---页面主体区域 --
    # 获取主体区域标题,获取更新时间
    title_text = soup.find('div',class_='userRecord-history__title').find('p')
    time_text = title_text.get_text(strip=True).split('(')[0]
    match = re.search(r'\d{4}-\d{2}-\d{2}', time_text)
    stats_data['update_time'] = match.group()
    # --- 1. 获取饼图区块 ---
    charts_box = soup.find('div',class_='userRecord-charts')
    #胜率
    win_frame = charts_box.find("div", class_="userRecord-charts__winRate--frame")
    if win_frame and len(win_frame.find_all("p")) >= 2:
        stats_data['win_rate'] = win_frame.find_all("p")[1].get_text(strip=True)
    # 胜负场次
    win_data = charts_box.find('div', class_='userRecord-charts__winRate--data')
    if win_data:
        total_tag = win_data.find('p', class_="total")
        stats_data['total_count']= clean_number(total_tag.get_text(),True)
        result_tag = win_data.find('p', class_="result")
        if result_tag:
            win_span = result_tag.find('span', class_="win")
            fail_span = result_tag.find('span', class_="fail")
            stats_data['win_count'] = clean_number(win_span.get_text(),True)
            stats_data['lose_count'] = clean_number(fail_span.get_text(),True)
    #命中率
    kill_frame = charts_box.find("div", class_="userRecord-charts__killRate--frame")
    if kill_frame and len(kill_frame.find_all('p')) >= 2:
        stats_data['hit_rate'] = kill_frame.find_all('p')[1].get_text(strip=True)
    #出战战等级
    fight_level = charts_box.find("div", class_="userRecord-charts__fightingRate--frame")
    stats_data['avg_tier'] = fight_level.find_all('p')[1].get_text(strip=True)

    # --- 2. 获取“战绩详细数据” ---
    # 源码中它紧跟在饼图后面，且有唯一的 class
    detail_data = soup.find('ul',class_='userRecord-data')
    data_list = detail_data.find_all('li')
    stats_data['avg_damage']=data_list[0].find_all('p')[1].get_text(strip=True)
    stats_data['avg_exp']=data_list[1].find_all('p')[1].get_text(strip=True)
    stats_data['avg_kill']=data_list[2].find_all('p')[1].get_text(strip=True)
    stats_data['avg_occupy']=data_list[3].find_all('p')[1].get_text(strip=True)
    stats_data['avg_defense']=data_list[4].find_all('p')[1].get_text(strip=True)
    stats_data['avg_discovery']=data_list[5].find_all('p')[1].get_text(strip=True)
    # --- 3. 获取“底部内容” ---
    # 包含盒子评价和近1000场战斗力
    comment_list = soup.find('div',class_='comment-list__text')
    # 提取每个 p 标签的文本，并去除首尾多余空格
    texts = [p.get_text(strip=True) for p in comment_list]
    # 使用换行符拼接
    stats_data['comment'] = "\n".join(texts)
    stats_data['radar_data'] = get_radar_data(res.text)

    player_stats = PlayerStats(**stats_data)
    frequent_tank_list = get_frequent_tank_list(soup.find_all('div',class_='user-tank__pop'))
    return player_stats,frequent_tank_list

def get_frequent_tank_list(tank_list_div) ->list[FrequentTank]:
    # 提取并实例化坦克对象列表
    tanks:list[FrequentTank] = []
    for pop in tank_list_div:
        header = pop.find('div', class_='tank-pop__info')
        if not header:
            continue
        p_text = header.find('p').get_text(strip=True) if header.find('p') else ""
        # 提取坦克详细指标
        body_spans = pop.find('div', class_='tank-pop__body').find_all('span', class_='data') if pop.find('div',
                                                                                                          class_='tank-pop__body') else []
        # 确保 body_spans 长度足够，避免索引越界
        if len(body_spans) < 5:
            print(f"坦克 {header.find('h3').get_text(strip=True) if header.find('h3') else '未知'} 数据不完整")
            continue
        name = header.find('h3').get_text(strip=True) if header.find('h3') else ""
        tank_info = get_tank_info_by_name(name)
        tank_info = FrequentTank(
            tank_info=tank_info,
            win_rate=header.find('span', class_='win num').get_text(strip=True) if header.find('span',
                                                                                               class_='win num') else "0",
            win_count=re.search(r'胜(\d+)场', p_text).group(1) if re.search(r'胜(\d+)场', p_text) else "0",
            avg_power=re.search(r'战力：(\d+)', p_text).group(1) if re.search(r'战力：(\d+)', p_text) else "0",
            avg_damage=body_spans[0].text,
            avg_exp=body_spans[1].text,
            avg_destroy=body_spans[2].text,
            avg_credits=body_spans[3].text,
            hit_rate = body_spans[4].text,
        )
        tanks.append(tank_info)
    return tanks