from dataclasses import dataclass
from typing import Optional

from data.plugins.astrbot_plugin_wot.src.domain.models.enums import TankNationEnum, TankRoleEnum, TankTypeEnum

@dataclass
class PlayerStats:
    """ 从偶游盒子页面爬取的玩家数据信息,
        显示在报表头部
    """
    name: str           #玩家昵称
    update_time: str    #更新时间
    power: str          #效率
    power_float: str    #效率浮动
    win_rate: str       #胜率
    total_count: int    #总场次
    win_count: int      #胜利场次
    lose_count: int     #失败场次
    hit_rate: str       #命中率
    avg_tier: str       #出战等级
    avg_damage: str     #场均损伤
    avg_exp: str        #场均经验
    avg_kill: str       #场均击毁
    avg_occupy: str     #场均占领
    avg_defense: str    #场均防守
    avg_discovery: str  #场均发现
    comment: str        #评价
    radar_data: list[float] #雷达数据

@dataclass
class Tank:
    """坦克基本属性信息，更多信息可从wot_tank_full.json中查看"""
    name: str           #坦克名称
    tier: int           #坦克等级
    premium: int        #金币/特种车辆,1为金币/特种车辆，0为银币坦克
    vehicle_cd:int      #车辆唯一标识
    nation: TankNationEnum  #坦克系别，TankNationEnum
    type: TankTypeEnum  #坦克类型，中坦-重坦等
    role: TankRoleEnum  #坦克定位，详见TankRoleEnum


@dataclass
class FrequentTank:
    """常用坦克信息，从偶游坦克世界盒子页面获取常用坦克信息"""
    tank_info: Tank     #坦克信息
    win_rate: float     #胜率
    hit_rate: float     #命中率
    win_count: int      #胜利场次
    avg_power: int      #场均效率
    avg_damage: float   #场均伤害
    avg_exp: float      #场均经验
    avg_destroy: float  #场均击毁
    avg_credits: float  #场均收益

@dataclass
class RecordsBasic:
    """从偶游坦克世界盒子页面爬取基本战斗信息"""
    arena_id: str       #对战id，用来获取详细战绩
    is_win: str         #对局结果，0-失败，1-胜利，2-平局
    gui_type: str       #对局类型
    start_time: str     #开始时间

@dataclass
class RecordsDetail:
    """根据对战id获取的坦克单场详细战斗数据"""
    tank_info: Tank     #坦克信息
    records_basic:RecordsBasic  #战斗基本信息
    exp:int             #本场经验
    power:int           #本场效率
    death_count:int     #死亡统计
    damage_dealt:int    #造成伤害
    assist_radio:int    #点亮协助
    assist_track:int    #断带协助
    assist_stun:int     #弹震协助
    kills:int           #击毁数
    shots:int           #射击次数
    hits:int            #命中次数
    hit_received:int    #被击中次数
    piercings:int       #击穿次数
    piercings_received:int #被击穿次数
    blocked:int         #抵挡损伤
    marks_on_gun:int    #坦克环线
    credits:int         #本场收益
    life_time:int       #存活时间

    @property
    def assist_total(self) -> int:
        """计算总协助：点亮 + 断带 + 弹震"""
        return max(self.assist_radio,self.assist_track, self.assist_stun)
        # return self.assist_radio + self.assist_track + self.assist_stun

@dataclass
class OverallSummary:
    """全局场均数据汇总（全量对局数据计算）"""
    avg_tier: float     # 出战等级平均值（所有对局的坦克等级平均）
    win_rate: float     # 胜率 = 胜利场次 / 总场次（保留2位小数）
    total_count: int    # 总场次
    win_count: int      # 胜利场次
    lose_count: int     # 失败场次
    draw_count: int     # 平局场次
    avg_power: float    # 场均效率（所有对局power的平均值）
    avg_damage: float   # 场均伤害（所有对局damage_dealt的平均值）
    avg_assist_total: float  # 场均总协助（点亮+断带+弹震的总和平均值）
    avg_block: float    # 场均抵挡（所有对局blocked的平均值）
    avg_exp: float      # 场均经验（所有对局exp的平均值）
    avg_credits: float  # 场均收益（所有对局credits的平均值）
    avg_life_time: int # 场均存活时间（所有对局lifetime的平均值）

@dataclass
class TankSummary:
    """单坦克数据汇总（按坦克维度分组计算）"""
    tank_info: Tank    # 坦克详细信息
    gun_marks: int     # 坦克环线数（0-3环）
    win_rate: float    # 胜率 = 该坦克胜利场次 / 该坦克总场次
    total_count: int   # 该坦克总场次
    win_count: int     # 该坦克胜利场次
    lose_count: int    # 该坦克失败场次
    draw_count: int    # 该坦克平局场次
    avg_power: float   # 该坦克场均效率
    avg_damage: float  # 该坦克场均伤害
    avg_assist_total: float  # 该坦克场均总协助
    avg_block: float   # 该坦克场均抵挡
    avg_exp: float     # 该坦克场均经验
    avg_credits: float # 该坦克场均收益
    avg_life_time: int # 该坦克场均存活时间

@dataclass
class FinalSummary:
    summary_title: str
    query_time: Optional[str] = None
    last_battle_time:Optional[str] = None
    overall_summary: Optional[OverallSummary] = None
    tank_summary: Optional[list[TankSummary]]=None

@dataclass
class WotRenderContext:
    """最终交给页面渲染的总上下文对象"""
    player_stats: PlayerStats
    frequent_tank: list[FrequentTank]
    final_summary: FinalSummary
