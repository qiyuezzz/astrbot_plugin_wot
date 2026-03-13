from enum import Enum, unique


@unique
class TankNationEnum(Enum):
    """坦克系别枚举"""

    # 格式：常量名 = ("JSON中的原始值", "中文显示名")

    UNKNOWN = ("", "未知")
    USSR = ("ussr", "苏联")
    USA = ("usa", "美国")
    FRANCE = ("france", "法国")
    GERMANY = ("germany", "德国")
    UK = ("uk", "英国")
    JAPAN = ("japan", "日本")
    CZECH = ("czech", "捷克")
    SWEDEN = ("sweden", "瑞典")
    POLAND = ("poland", "波兰")
    ITALY = ("italy", "意大利")
    CHINA = ("china", "中国")

    def __init__(self, code, display_name):
        self.code = code
        self.display_name = display_name

    @classmethod
    def from_code(cls, code):
        for member in cls:
            if member.code == code:
                return member
        return cls.UNKNOWN


@unique
class TankTypeEnum(Enum):
    """坦克类型枚举"""

    # 格式：常量名 = ("JSON中的原始值", "中文显示名")

    UNKNOWN = ("", "未知")
    MEDIUM_TANK = ("mediumTank", "中坦")
    HEAVY_TANK = ("heavyTank", "重坦")
    LIGHT_TANK = ("lightTank", "轻坦")
    AT_SPG = ("AT-SPG", "坦歼")
    SPG = ("SPG", "火炮")

    def __init__(self, code, display_name):
        self.code = code
        self.display_name = display_name

    @classmethod
    def from_code(cls, code):
        for member in cls:
            if member.code == code:
                return member
        return cls.UNKNOWN


@unique
class TankRoleEnum(Enum):
    """坦克定位枚举"""

    # 格式：常量名 = ("JSON中的原始值", "中文显示名")

    # 轻型坦克
    ROLE_LT_UNIVERSAL = ("role_LT_universal", "全能轻坦")
    ROLE_LT_WHEELED = ("role_LT_wheeled", "轮式轻坦")

    # 中型坦克
    ROLE_MT_ASSAULT = ("role_MT_assault", "突击中坦")
    ROLE_MT_UNIVERSAL = ("role_MT_universal", "全能中坦")
    ROLE_MT_SNIPER = ("role_MT_sniper", "狙击中坦")
    ROLE_MT_SUPPORT = ("role_MT_support", "支援中坦")

    # 重型坦克
    ROLE_HT_ASSAULT = ("role_HT_assault", "突击重坦")
    ROLE_HT_UNIVERSAL = ("role_HT_universal", "全能重坦")
    ROLE_HT_BREAK = ("role_HT_break", "突破重坦")
    ROLE_HT_SUPPORT = ("role_HT_support", "支援重坦")

    # 坦克歼击车 (反坦)
    ROLE_AT_SPG_ASSAULT = ("role_ATSPG_assault", "突击反坦")
    ROLE_AT_SPG_UNIVERSAL = ("role_ATSPG_universal", "全能反坦")
    ROLE_AT_SPG_SNIPER = ("role_ATSPG_sniper", "狙击反坦")
    ROLE_AT_SPG_SUPPORT = ("role_ATSPG_support", "支援反坦")

    # 自行火炮
    ROLE_SPG = ("role_SPG", "自行火炮")

    # 特殊情况：部分低等级坦克 role 字段为空
    NONE = ("", "通用/无定位")

    def __init__(self, code, display_name):
        self.code = code
        self.display_name = display_name

    @classmethod
    def from_code(cls, code):
        for member in cls:
            if member.code == code:
                return member
        return cls.NONE
