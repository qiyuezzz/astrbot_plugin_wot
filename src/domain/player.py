from dataclasses import dataclass


@dataclass
class AccountInfo:
    """账户信息"""

    account_id: str  # 用户id
    account_name: str  # 用户名称
    account_battles: int  # 战斗次数
    clan_tag: str = "无"  # 军团名称
