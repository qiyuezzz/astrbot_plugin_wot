class BaseConfig:
    DEFAULT_TIMEOUT = 10
    DEFAULT_USER_AGENT = (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'Chrome/120.0.0.0 Safari/537.36'
    )

    # 能力声明（默认全部关闭）
    use_session: bool = False        # 是否使用 Session
    need_csrf: bool = False          # 是否自动注入 CSRF
    warmup_url: str | None = None    # 预热地址（获取 cookie）

    def build_headers(self) -> dict:
        """统一 Header 构造入口（可覆写）"""
        return {
            'User-Agent': self.DEFAULT_USER_AGENT
        }

    def build_params(self) -> dict | None:
        """统一 Params 构造入口（可覆写）"""
        return getattr(self, "params", None)

class WotBoxStatsConfig(BaseConfig):
    """获取偶游盒子统计页面"""

    base_url = "https://wotbox.ouj.com/wotbox/index.php"

    def build_params(self):
        return {
        'r': 'default/index',
        'pn': ''
    }

    def build_headers(self):
        return {
            'User-Agent': self.DEFAULT_USER_AGENT,
            'Referer': "https://wotbox.ouj.com/"
        }


class WotBoxAreanListConfig(BaseConfig):
    """获取玩家对局列表"""

    base_url = "https://wotapp.ouj.com/index.php"

    def build_params(self):
        return {
            'r': 'wx/ajaxLoadArenas',
            'p': '',
            'pn': ''
        }

    def build_headers(self):
        return {
            'User-Agent': self.DEFAULT_USER_AGENT,
            'Referer': "https://wotbox.ouj.com/"
        }


class WotBoxDetailRecordConfig(BaseConfig):
    """根据对局id获取对局详细详细信息"""

    base_url = "https://wotapp.ouj.com/"

    def build_headers(self):
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

    def build_params(self):
        return {
            'r': 'wotboxapi/battledetail',
            'pn': '',
            'arena_id': ''
        }

# 官网接口
class WotGameTankInfoConfig(BaseConfig):
    """获取坦克信息"""
    base_url = "https://wotgame.cn/wotpbe/tankopedia/api/vehicles/by_filters/"

    warmup_url="https://wotgame.cn/zh-cn/tankopedia/"

    data = {
        "filter[nation]": "ussr,usa,france,germany,uk,japan,czech,sweden,poland,italy,china",
        "filter[language]": "zh-cn",
        "filter[premium]": "0,1",
        "filter[apply_modified_ttc]": "1"
    }

    def build_headers(self):
        return {
            'X-Requested-With': 'XMLHttpRequest',
            "User-Agent": self.DEFAULT_USER_AGENT,
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Referer": self.warmup_url,
        }


class WotAccountSearchConfig(BaseConfig):
    """根据玩家名称查询玩家简单信息"""
    base_url = "https://wotgame.cn/zh-cn/community/accounts/search/"

    use_session = True
    need_csrf = True
    warmup_url = "https://wotgame.cn/zh-cn/community/accounts/"

    params = {
        "name": "",
        "name_gt": ""
    }

    def build_headers(self):
        return {
            "User-Agent": self.DEFAULT_USER_AGENT,
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": self.warmup_url,
        }


# 实例化配置类，主脚本直接用这个实例
#盒子接口
wot_box_config = WotBoxStatsConfig()
wot_box_records_config = WotBoxAreanListConfig()
wot_box_detail_record_config = WotBoxDetailRecordConfig()

#官网接口
wot_account_search_config = WotAccountSearchConfig()
wot_game_tank_info_config = WotGameTankInfoConfig()