# config.py
from dataclasses import dataclass


class BaseConfig:
    """基础配置父类，存放通用配置"""
    # 通用超时时间（所有接口共用）
    DEFAULT_TIMEOUT = 10
    # 通用User-Agent（可被子类覆盖）
    DEFAULT_USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36'


# 获取玩家统计页面
class WotBoxStatsConfig(BaseConfig):
    base_url = "https://wotbox.ouj.com/wotbox/index.php"

    # 使用方法或属性确保灵活性
    @property
    def headers(self):
        return {
            'User-Agent': self.DEFAULT_USER_AGENT,
            'Referer': "https://wotbox.ouj.com/"
        }

    # 基础参数
    params = {
        'r': 'default/index',
        'pn': ''
    }

#获取玩家对局列表
class WotBoxAreanListConfig(BaseConfig):
    base_url = "https://wotapp.ouj.com/index.php"

    @property
    def headers(self):
        return {
            'User-Agent': self.DEFAULT_USER_AGENT,
            'Referer': "https://wotbox.ouj.com/"
        }

    # 基础参数
    params = {
        'r': 'wx/ajaxLoadArenas',
        'p': '',
        'pn': ''
    }
    # 核心修复：添加copy方法，实现配置深拷贝
    def copy(self):
        new_config = WotBoxAreanListConfig()
        new_config.url = self.base_url
        # 对params做浅拷贝即可（字典值都是字符串）
        new_config.params = self.params.copy()
        return new_config

#根据对局id获取对局详细详细信息
class WotBoxDetailRecordConfig(BaseConfig):
    base_url = "https://wotapp.ouj.com/"

    @property
    def headers(self):
        return {
            'Accept':'*/*',
            'Accept-Encoding':'gzip,deflate,br,zstd',
            'Accept-Language':'zh-CN,zh;q=0.9,en;q=0.8',
            'Connection':'keep-alive',
            'Host':'wotapp.ouj.com',
            'Referer':'https://wotbox.ouj.com/',
            'Sec-Fetch-Dest': 'script',
            'Sec-Fetch-Mode': 'no-cors',
            'Sec-Fetch-Site': 'same-site',
            'User-Agent': self.DEFAULT_USER_AGENT,
            'sec-ch-ua':'"Not(A:Brand";v="8", "Chromium";v="144", "Google Chrome";v="144"',
            'sec-ch-ua-mobile':'?0',
            'sec-ch-ua-platform':'"Windows"'
        }

    # 基础参数
    params = {
        'r': 'wotboxapi/battledetail',
        'pn': '',
        'arena_id': ''
    }

class WotGameConfig(BaseConfig):
    """WGGames接口配置（军团查询等）"""
    base_url = "https://wgn.wggames.cn"
    # 具体接口路径
    CLAN_SEARCH_PATH = "/clans/wot/search/api/accounts/"

    @property
    def FULL_CLAN_SEARCH_URL(self):
        return f"{self.base_url}{self.CLAN_SEARCH_PATH}"

    # 专属headers（如需自定义可覆盖）
    HEADERS = {
        'User-Agent': BaseConfig.DEFAULT_USER_AGENT
    }

# ===================== 对外暴露实例（方便调用） =====================
# 实例化配置类，主脚本直接用这个实例
#盒子接口
wot_box_config = WotBoxStatsConfig()
wot_box_records_config = WotBoxAreanListConfig()
wot_box_detail_record_config = WotBoxDetailRecordConfig()

#官方接口
wot_game_config = WotGameConfig()