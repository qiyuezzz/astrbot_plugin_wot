class WotBoxBaseException(Exception):
    """WOT盒子基础异常（所有WOT相关异常的父类）"""
    def __init__(self, msg: str, group_msg: str = None):
        self.msg = msg  # 日志/调试用详细信息
        # 群聊返回的简化信息（为空则用msg）
        self.group_msg = group_msg or msg
        super().__init__(self.msg)

class WotBoxCrawlException(WotBoxBaseException):
    """爬取WOT盒子数据异常（如页面解析失败、网络错误）"""
    pass

class WotBoxDataException(WotBoxBaseException):
    """WOT盒子数据处理异常（如数据校验失败、字段缺失）"""
    pass

class WotBoxParamException(WotBoxBaseException):
    """WOT盒子参数异常（如玩家昵称为空、坦克ID错误）"""
    pass