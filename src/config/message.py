from data.plugins.astrbot_plugin_wot.src.domain.models.player import AccountInfo


class WotBindMsg:
    @staticmethod
    def success(account_info:AccountInfo):
        """绑定成功"""
        msg=f'绑定成功，玩家名称为"{account_info.account_name}"\n军团:"{account_info.clan_tag}"\n玩家id:"{account_info.account_id}"'
        return msg
    @staticmethod
    def fail(player_name:str):
        """绑定失败"""
        msg = f'绑定失败，玩家{player_name}不存在 \n请检查玩家名称是否正确'
        return msg

#校验是否绑定游戏内名称
class CheckBindMsg:
    @staticmethod
    def failed():
        msg="未查询到绑定信息，请先绑定\n绑定方式：'/wot绑定 玩家名称'"
        return msg
