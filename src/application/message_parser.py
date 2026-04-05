from __future__ import annotations

import astrbot.api.message_components as Comp


def extract_plain_text_from_chain(message_chain: list) -> str:
    """从消息链中提取纯文本（拼接所有 Plain 组件）"""
    return " ".join(item.text for item in message_chain if isinstance(item, Comp.Plain))


def extract_arg_after_command(message_str: str, commands: list[str]) -> str:
    """从消息文本中提取命令后的参数部分"""
    normalized = message_str.lstrip("/").strip()
    for cmd in commands:
        if normalized.startswith(cmd):
            after_cmd = normalized[len(cmd) :].lstrip()
            if len(normalized) == len(cmd) or normalized[len(cmd)].isspace():
                return after_cmd
    return ""

def extract_at_target_id(message_chain: list, self_id: str | None = None) -> str:
    """从消息链中提取 @目标用户ID，排除 @机器人自身"""
    for item in message_chain:
        if isinstance(item, Comp.At):
            target = str(item.qq)
            if target and target != "all" and target != self_id:
                return target
    return ""


def extract_text_after_leading_at(message_chain: list) -> str:
    """提取第一个 @ 之后的所有纯文本内容（用于 command_router 匹配 @某人+命令）"""
    parts: list[str] = []
    seen_at = False
    for item in message_chain:
        if isinstance(item, Comp.At):
            if not seen_at:
                seen_at = True
                continue
        if not seen_at:
            continue
        if isinstance(item, Comp.Plain):
            parts.append(item.text)
    return "".join(parts).strip()


def extract_player_name(message_str: str) -> str:
    """从绑定命令中提取玩家名称"""
    normalized = message_str.lstrip("/").strip()
    command_bind_prefix = "wot绑定 "
    if not normalized.startswith(command_bind_prefix):
        return ""
    parts = normalized.split(command_bind_prefix, maxsplit=1)
    return parts[1].strip() if len(parts) > 1 else ""


class CommandInput:
    """从事件中一次性解析出的命令输入，避免多层透传"""

    def __init__(
        self,
        send_id: str,
        message_chain: list,
        explicit_name: str | None,
        self_id: str | None = None,
    ):
        self.send_id = send_id
        self.message_chain = message_chain
        self.explicit_name = explicit_name
        self.self_id = self_id

    @classmethod
    def from_event(
        cls,
        event,
        commands: list[str],
        message_text: str | None = None,
    ) -> CommandInput:
        """从 AstrMessageEvent 中一次性提取所有需要的输入信息"""
        send_id = event.get_sender_id()
        message_chain = event.get_messages()
        self_id = event.get_self_id()

        # 优先使用显式传入的 message_text，其次用 event.message_str，最后 fallback 到 message_chain 纯文本
        explicit_name = extract_arg_after_command(
            message_text or event.message_str, commands
        )
        if not explicit_name and message_chain:
            explicit_name = extract_arg_after_command(
                extract_plain_text_from_chain(message_chain), commands
            )

        return cls(send_id, message_chain, explicit_name or None, self_id)
