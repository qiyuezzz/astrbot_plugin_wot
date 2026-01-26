class WotBindMsg:
    @staticmethod
    def success(player_name:str):
        """绑定成功"""
        msg=f'绑定成功，玩家名称为"{player_name}"'
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