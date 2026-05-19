"""
AstrBot 插件: TsuguBangDreamBot
BanG Dream! 游戏助手，基于 tsugu-api-python

功能: 查曲/查卡/查卡面/查角色/查活动/查卡池/抽卡模拟/查谱面/分数表/查试炼/
     ycx/ycxall/lsycx/车牌列表/查玩家/玩家绑定/解除绑定/玩家状态/绑定列表/
     主服务器/显示服务器/选择绑定/随机曲目
"""

from __future__ import annotations

import json
import re
from typing import List, Optional

import tsugu_api_async
from tsugu_api_core.exception import FailedException
from tsugu_api_core._settings import settings

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from astrbot.api.message_components import Image, Plain
from astrbot.core.config.astrbot_config import AstrBotConfig
from astrbot.core.message.components import At, Reply
from astrbot.core.star.star_handler import star_handlers_registry


# ── 服务器名称工具 ──────────────────────────────────────────────

def server_name_to_id(server: str) -> int:
    mapping = {
        "0": 0, "1": 1, "2": 2, "3": 3, "4": 4,
        "日服": 0, "国际服": 1, "台服": 2, "国服": 3, "韩服": 4,
        "jp": 0, "en": 1, "tw": 2, "cn": 3, "kr": 4,
    }
    result = mapping.get(server.lower() if server else "")
    if result is None:
        raise ValueError(f"服务器不存在: {server}")
    return result


def server_id_to_full_name(server: int) -> str:
    names = {0: "日服", 1: "国际服", 2: "台服", 3: "国服", 4: "韩服"}
    name = names.get(server)
    if name is None:
        raise ValueError(f"服务器不存在: {server}")
    return name


def server_id_to_short_name(server: int) -> str:
    names = {0: "jp", 1: "en", 2: "tw", 3: "cn", 4: "kr"}
    name = names.get(server)
    if name is None:
        raise ValueError(f"服务器不存在: {server}")
    return name


# 难度名称到 ID
DIFFICULTY_MAP = {
    "easy": 0, "normal": 1, "hard": 2, "expert": 3, "special": 4,
    "ez": 0, "nm": 1, "hd": 2, "ex": 3, "sp": 4,
    "0": 0, "1": 1, "2": 2, "3": 3, "4": 4,
}

# 档位列表
TIER_LISTS = {
    "jp": [20, 30, 40, 50, 100, 200, 300, 400, 500, 1000, 2000, 5000, 10000, 20000, 30000, 50000],
    "tw": [100, 500],
    "en": [50, 100, 300, 500, 1000, 2000, 2500],
    "kr": [100],
    "cn": [20, 30, 40, 50, 100, 200, 300, 400, 500, 1000, 2000, 3000, 4000, 5000, 10000, 20000, 30000, 50000],
}

# 服务器全名 -> ID (用于"显示服务器"命令解析)
SERVER_FULL_NAMES = {
    "日服": 0, "国际服": 1, "台服": 2, "国服": 3, "韩服": 4,
    "jp": 0, "en": 1, "tw": 2, "cn": 3, "kr": 4,
}


def tier_list_to_string() -> str:
    results = []
    for server, tiers in TIER_LISTS.items():
        results.append(server + " : " + ", ".join(str(t) for t in tiers))
    return "\n".join(results)


# ── API 响应转 AstrBot 消息链 ────────────────────────────────────

def response_to_chain(response: list) -> list:
    """tsugu _Response -> AstrBot MessageChain"""
    chain: list = []
    for item in response:
        if item.get("type") == "string":
            chain.append(Plain(item["string"]))
        elif item.get("type") == "base64":
            b64_data = item.get("string", "")
            if b64_data:
                chain.append(Image.fromBase64(b64_data))
    return chain


async def _get_tsugu_user(platform: str, user_id: str) -> dict:
    """获取 tsugu 用户数据"""
    try:
        response = await tsugu_api_async.get_user_data(platform, user_id)
    except FailedException as e:
        raise Exception(e.response.get("data", str(e))) from e
    except Exception as e:
        raise Exception(f"获取用户数据失败: {e}") from e
    return response["data"]


def _get_user_player(tsugu_user: dict, server: Optional[int] = None, index: Optional[int] = None) -> dict:
    """从 tsugu 用户数据中获取指定服务器的绑定玩家"""
    server = server if server is not None else tsugu_user["mainServer"]
    player_list = tsugu_user["userPlayerList"]
    player_index = index if index is not None else tsugu_user["userPlayerIndex"]

    if not player_list:
        raise ValueError("用户未绑定玩家")

    if index is not None:
        if index < 0 or index >= len(player_list):
            raise ValueError("无效的绑定信息ID")
        return player_list[index]

    if player_list[player_index]["server"] == server:
        return player_list[player_index]

    for player in player_list:
        if player["server"] == server:
            return player

    raise ValueError(f"用户在{server_id_to_full_name(server)}未绑定玩家")


def _parse_server_args(args_str: str) -> tuple[Optional[int], list[str]]:
    """从参数字符串中解析服务器名，返回 (server_id, remaining_parts)"""
    parts = args_str.split() if args_str else []
    server = None
    remaining = []
    for p in parts:
        try:
            server = server_name_to_id(p)
        except ValueError:
            remaining.append(p)
    return server, remaining


# ── 插件类 ────────────────────────────────────────────────────────

@register(
    "astrbot_plugin_tsugu",
    "QClaw",
    "BanG Dream! 游戏助手 (TsuguBangDreamBot)",
    "1.3.0",
    "https://github.com/Sov8forUs/astrbot_plugin_tsugu",
)
class TsuguPlugin(Star):
    """Tsugu BanG Dream Bot AstrBot 插件"""

    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config

        # tsugu 后端配置
        backend_url = config.get("backend_url", "http://tsugubot.com:8080")
        userdata_backend_url = config.get("userdata_backend_url", "http://tsugubot.com:8080")
        proxy = config.get("proxy", "")

        settings.backend_url = backend_url
        settings.userdata_backend_url = userdata_backend_url
        if proxy:
            settings.proxy = proxy
            settings.backend_proxy = True
            settings.userdata_backend_proxy = True
        else:
            settings.backend_proxy = False
            settings.userdata_backend_proxy = False

        settings.use_easy_bg = config.get("use_easy_bg", True)
        settings.compress = config.get("compress", True)

        # v1.3.0 新功能配置
        self._whitelist_enabled = config.get("whitelist_enabled", False)
        self._whitelist_groups = self._parse_whitelist(config.get("whitelist_groups", []))
        self._at_wake_enabled = config.get("at_wake_enabled", True)
        self._at_sender_enabled = config.get("at_sender_enabled", False)
        self._quote_reply_enabled = config.get("quote_reply_enabled", False)
        raw_aliases = config.get("command_aliases", "{}")
        parsed_aliases = self._parse_aliases(raw_aliases)
        # 如果用户未配置别名（空或仅{}），使用内置默认别名
        if not parsed_aliases:
            parsed_aliases = {"ycm": "车牌列表"}
        self._command_aliases = parsed_aliases
        self._wake_prefix = config.get("wake_prefix", "")

        # 绑定验证会话 {user_key: {verify_code, server, action, player_id, created_at}}
        self._bind_sessions: dict = {}

        logger.info(f"Tsugu 插件已初始化 (白名单={'启用' if self._whitelist_enabled else '关闭'}, "
                     f"@唤醒={'启用' if self._at_wake_enabled else '关闭'}, "
                     f"唤醒前缀='{self._wake_prefix or '无'}', "
                     f"别名数={len(self._command_aliases)})")

    async def initialize(self) -> None:
        """插件激活时，根据配置动态修改 RegexFilter 的 pattern 以支持别名"""
        if not self._command_aliases:
            return

        # 命令名 → handler 方法名映射
        cmd_method_map = {
            "查曲": "cmd_search_song", "查卡": "cmd_search_card",
            "查卡面": "cmd_card_illustration", "查角色": "cmd_search_character",
            "查活动": "cmd_search_event", "查卡池": "cmd_search_gacha",
            "抽卡模拟": "cmd_gacha_simulate", "查谱面": "cmd_song_chart",
            "分数表": "cmd_song_meta", "查试炼": "cmd_event_stage",
            "ycx": "cmd_ycx", "ycxall": "cmd_ycxall", "lsycx": "cmd_lsycx",
            "车牌列表": "cmd_room_list", "查玩家": "cmd_search_player",
            "玩家绑定": "cmd_player_bind", "解除绑定": "cmd_player_unbind",
            "玩家状态": "cmd_player_info", "绑定列表": "cmd_player_list",
            "主服务器": "cmd_switch_main_server", "显示服务器": "cmd_displayed_servers",
            "选择绑定": "cmd_switch_player", "随机曲目": "cmd_random_song",
        }

        # 反向映射: handler 方法名 → 命令名
        method_to_cmd = {v: k for k, v in cmd_method_map.items()}

        # 收集每个命令需要添加的别名
        cmd_new_aliases: dict[str, set[str]] = {}
        for alias_name, original_cmd in self._command_aliases.items():
            if original_cmd not in cmd_method_map:
                logger.warning(f"命令别名 '{alias_name}' 指向的命令 '{original_cmd}' 不存在，跳过")
                continue
            cmd_new_aliases.setdefault(original_cmd, set()).add(alias_name)

        # 遍历 registry，找到对应 handler 的 RegexFilter 并修改 pattern
        module_path = self.__class__.__module__
        injected_count = 0
        for handler_md in star_handlers_registry:
            if handler_md.handler_module_path != module_path:
                continue
            handler_name = handler_md.handler_name
            cmd_name = method_to_cmd.get(handler_name)
            if not cmd_name or cmd_name not in cmd_new_aliases:
                continue

            for event_filter in handler_md.event_filters:
                if hasattr(event_filter, "pattern"):
                    old_pattern = event_filter.pattern
                    # 提取原 pattern 中的命令名
                    m = re.match(r"^\^\(\?:(.+?)\)\\b", old_pattern)
                    if m:
                        existing_cmds = set(m.group(1).split("|"))
                    else:
                        m = re.match(r"^\^(.+?)\\b", old_pattern)
                        if m:
                            existing_cmds = {m.group(1)}
                        else:
                            continue

                    new_aliases = cmd_new_aliases[cmd_name]
                    all_cmds = existing_cmds | new_aliases
                    # 构建新 pattern（使用 \\b 避免转义为 backspace）
                    if len(all_cmds) == 1:
                        new_pattern = f"^{list(all_cmds)[0]}\\b"
                    else:
                        new_pattern = f"^(?:{'|'.join(sorted(all_cmds))})\\b"

                    event_filter.pattern = new_pattern
                    # 如果 RegexFilter 内部编译了正则，需要重新编译
                    if hasattr(event_filter, "_regex"):
                        event_filter._regex = re.compile(new_pattern)

                    injected_count += len(new_aliases)
                    logger.info(f"命令 '{cmd_name}' 添加别名: {new_aliases}，pattern: {new_pattern}")

        # ── 自定义唤醒前缀注入 ──────────────────────────────────────
        prefix_injected = 0
        if self._wake_prefix:
            prefix_escaped = re.escape(self._wake_prefix)
            for handler_md in star_handlers_registry:
                if handler_md.handler_module_path != module_path:
                    continue
                for event_filter in handler_md.event_filters:
                    if hasattr(event_filter, "pattern"):
                        old_pattern = event_filter.pattern
                        # 在 pattern 前面添加可选前缀匹配
                        # 例如 ^查曲\b -> ^(?:/|!)?查曲\b
                        if old_pattern.startswith("^"):
                            new_pattern = f"^(?:{prefix_escaped})?{old_pattern[1:]}"
                            event_filter.pattern = new_pattern
                            if hasattr(event_filter, "_regex"):
                                event_filter._regex = re.compile(new_pattern)
                            prefix_injected += 1
            logger.info(f"Tsugu 唤醒前缀注册完成: 前缀='{self._wake_prefix}', 共注入 {prefix_injected} 个 pattern")

        logger.info(f"Tsugu 别名注册完成: 共注入 {injected_count} 个别名")

    # ── 配置解析工具 ──────────────────────────────────────────────

    @staticmethod
    def _parse_whitelist(groups: list | str) -> set[str]:
        """解析白名单群号列表或字符串"""
        if not groups:
            return set()
        if isinstance(groups, str):
            if not groups.strip():
                return set()
            return {g.strip() for g in groups.split(",") if g.strip()}
        if isinstance(groups, list):
            return {str(g).strip() for g in groups if str(g).strip()}
        return set()

    @staticmethod
    def _parse_aliases(aliases_str: str) -> dict[str, str]:
        """解析命令别名 JSON 字符串"""
        if not aliases_str or aliases_str.strip() == "{}":
            return {}
        try:
            aliases = json.loads(aliases_str)
            if isinstance(aliases, dict):
                return {str(k): str(v) for k, v in aliases.items()}
        except (json.JSONDecodeError, ValueError):
            logger.warning(f"命令别名配置解析失败: {aliases_str}")
        return {}

    # ── 通用工具方法 ──────────────────────────────────────────────

    def _user_key(self, event: AstrMessageEvent) -> str:
        return f"{event.get_platform_id()}:{event.get_sender_id()}"

    def _platform_name(self, event: AstrMessageEvent) -> str:
        """获取平台名称，用于 tsugu API
        
        注意: QQ 平台统一使用 'red'，onebot/chronocat 会被后端处理为 red
        """
        pid = event.get_platform_id()
        if "qq" in pid or "aiocqhttp" in pid:
            return "red"
        elif "weixin" in pid or "wechat" in pid:
            return "weixin"
        elif "telegram" in pid:
            return "telegram"
        elif "discord" in pid:
            return "discord"
        else:
            return pid

    def _cmd_args(self, event: AstrMessageEvent) -> str:
        """获取命令参数（去掉命令名后的文本）
        
        event.message_str 在 waking_check 阶段已去掉 wake_prefix，
        但仍包含命令名本身。需要手动去掉第一个 token。
        """
        msg = event.message_str.strip()
        parts = msg.split(None, 1)
        return parts[1] if len(parts) > 1 else ""

    # ── 白名单与 @唤醒 检查 ──────────────────────────────────────

    def _is_group_message(self, event: AstrMessageEvent) -> bool:
        """判断是否为群消息"""
        return bool(event.get_group_id())

    def _check_whitelist(self, event: AstrMessageEvent) -> bool:
        """检查白名单。返回 True 表示通过，False 表示被拦截。"""
        if not self._whitelist_enabled:
            return True
        # 私聊不受白名单限制
        if not self._is_group_message(event):
            return True
        group_id = str(event.get_group_id())
        return group_id in self._whitelist_groups



    def _precheck(self, event: AstrMessageEvent) -> bool:
        """统一的命令前置检查。返回 True 表示被拦截（应 return），False 表示通过。

        白名单拦截: 静默忽略（不回复）
        @唤醒拦截: 当 at_wake_enabled=True 时，要求 @bot / 全局唤醒前缀 / 自定义唤醒前缀 至少满足其一
        """
        # 白名单检查
        if not self._check_whitelist(event):
            return True
        # @唤醒检查
        if self._at_wake_enabled:
            is_at = getattr(event, "is_at_or_wake_command", False)
            if not is_at:
                # 检查自定义唤醒前缀
                if self._wake_prefix:
                    msg = event.message_str.strip()
                    if msg.startswith(self._wake_prefix):
                        pass  # 匹配自定义前缀，通过
                    else:
                        return True
                else:
                    return True
        return False

    # ── 回复装饰：@发送人 + 引用 ──────────────────────────────────

    def _wrap_chain(self, event: AstrMessageEvent, chain: list) -> list:
        """在消息链前添加 @发送人 和/或 引用原消息"""
        prefix = []
        if self._quote_reply_enabled:
            msg_id = getattr(event.message_obj, "message_id", None)
            sender_id = event.get_sender_id()
            if msg_id:
                prefix.append(Reply(id=msg_id, sender_id=sender_id))
        if self._at_sender_enabled:
            sender_id = event.get_sender_id()
            prefix.append(At(qq=sender_id))
        return prefix + chain if prefix else chain

    def _yield_result(self, event: AstrMessageEvent, chain: list):
        """统一的 yield 封装：自动包装 @发送人/引用，返回 chain_result"""
        wrapped = self._wrap_chain(event, chain)
        return event.chain_result(wrapped)

    def _yield_plain(self, event: AstrMessageEvent, text: str):
        """统一的 yield 封装：纯文本结果，自动包装 @发送人/引用"""
        chain = [Plain(text)]
        wrapped = self._wrap_chain(event, chain)
        return event.chain_result(wrapped)

    # ── 绑定验证拦截器 ────────────────────────────────────────────

    @filter.regex(r"^绑定\s*(\d{5,15})$")
    async def handle_bind_verify(self, event: AstrMessageEvent):
        """拦截 "绑定 <玩家ID>" 格式的消息，完成绑定验证"""
        # 白名单/@唤醒检查
        if self._precheck(event):
            return

        user_key = self._user_key(event)
        session = self._bind_sessions.get(user_key)

        if not session:
            return

        # 从 message_str 中提取玩家 ID
        msg = event.message_str.strip()
        m = re.match(r"^绑定\s*(\d{5,15})$", msg)
        if not m:
            return
        player_id = int(m.group(1))

        platform = self._platform_name(event)
        user_id = event.get_sender_id()
        server = session["server"]
        action = session["action"]

        try:
            response = await tsugu_api_async.bind_player_verification(
                platform, user_id, server, player_id, action  # type: ignore
            )
        except FailedException as e:
            yield self._yield_plain(event, e.response.get("data", "验证失败"))
            self._bind_sessions.pop(user_key, None)
            return
        except Exception as e:
            yield self._yield_plain(event, f"验证出错: {e}")
            self._bind_sessions.pop(user_key, None)
            return

        self._bind_sessions.pop(user_key, None)

        if response.get("status") == "success":
            if action == "bind":
                try:
                    await tsugu_api_async.change_user_data(platform, user_id, {"mainServer": server})
                    yield self._yield_plain(event,
                        f"绑定成功!\n"
                        f"服务器: {server_id_to_full_name(server)}\n"
                        f"玩家ID: {player_id}\n"
                        f"已自动切换到{server_id_to_full_name(server)}模式"
                    )
                except Exception:
                    yield self._yield_plain(event,
                        f"绑定成功!\n"
                        f"服务器: {server_id_to_full_name(server)}\n"
                        f"玩家ID: {player_id}\n"
                        f"(自动切换主服务器失败，请手动使用 主服务器 {server_id_to_short_name(server)})"
                    )
            else:
                yield self._yield_plain(event,
                    f"解除绑定成功!\n"
                    f"服务器: {server_id_to_full_name(server)}\n"
                    f"玩家ID: {player_id}"
                )
        else:
            yield self._yield_plain(event, f"验证失败: {response.get('data', '未知错误')}\n请重新尝试绑定")

    @filter.regex(r"^取消绑定$")
    async def handle_cancel_bind(self, event: AstrMessageEvent):
        """取消正在进行的绑定流程"""
        if self._precheck(event):
            return

        user_key = self._user_key(event)
        session = self._bind_sessions.pop(user_key, None)
        if session:
            action_text = "绑定" if session["action"] == "bind" else "解除绑定"
            yield self._yield_plain(event, f"已取消{action_text}流程")

    # ── 查曲 ──────────────────────────────────────────────────────

    @filter.regex(r"^查曲\b")
    async def cmd_search_song(self, event: AstrMessageEvent):
        if self._precheck(event):
            return
        args = self._cmd_args(event)
        if not args:
            yield self._yield_plain(event, "用法: 查曲 <关键词或曲目ID>\n示例: 查曲 1 / 查曲 ag lv27")
            return

        try:
            tsugu_user = await _get_tsugu_user(self._platform_name(event), event.get_sender_id())
            servers = tsugu_user["displayedServerList"]
        except Exception:
            servers = [3, 0]

        try:
            response = await tsugu_api_async.search_song(servers, text=args)
            chain = response_to_chain(response)
            if chain:
                yield self._yield_result(event, chain)
            else:
                yield self._yield_plain(event, "未找到匹配的曲目")
        except FailedException as e:
            yield self._yield_plain(event, e.response.get("data", "查询失败"))
        except Exception as e:
            yield self._yield_plain(event, f"查询出错: {e}")

    # ── 查卡 ──────────────────────────────────────────────────────

    @filter.regex(r"^查卡\b")
    async def cmd_search_card(self, event: AstrMessageEvent):
        if self._precheck(event):
            return
        args = self._cmd_args(event)
        if not args:
            yield self._yield_plain(event, "用法: 查卡 <关键词或卡牌ID>\n示例: 查卡 1399 / 查卡 绿 tsugu")
            return

        try:
            tsugu_user = await _get_tsugu_user(self._platform_name(event), event.get_sender_id())
            servers = tsugu_user["displayedServerList"]
        except Exception:
            servers = [3, 0]

        try:
            response = await tsugu_api_async.search_card(servers, text=args)
            chain = response_to_chain(response)
            if chain:
                yield self._yield_result(event, chain)
            else:
                yield self._yield_plain(event, "未找到匹配的卡牌")
        except FailedException as e:
            yield self._yield_plain(event, e.response.get("data", "查询失败"))
        except Exception as e:
            yield self._yield_plain(event, f"查询出错: {e}")

    # ── 查卡面 ────────────────────────────────────────────────────

    @filter.regex(r"^查卡面\b")
    async def cmd_card_illustration(self, event: AstrMessageEvent):
        if self._precheck(event):
            return
        args = self._cmd_args(event)
        if not args or not args.isdigit():
            yield self._yield_plain(event, "用法: 查卡面 <卡牌ID>\n示例: 查卡面 1399")
            return

        try:
            response = await tsugu_api_async.get_card_illustration(int(args))
            chain = response_to_chain(response)
            if chain:
                yield self._yield_result(event, chain)
            else:
                yield self._yield_plain(event, "未找到该卡牌插画")
        except FailedException as e:
            yield self._yield_plain(event, e.response.get("data", "查询失败"))
        except Exception as e:
            yield self._yield_plain(event, f"查询出错: {e}")

    # ── 查角色 ────────────────────────────────────────────────────

    @filter.regex(r"^查角色\b")
    async def cmd_search_character(self, event: AstrMessageEvent):
        if self._precheck(event):
            return
        args = self._cmd_args(event)
        if not args:
            yield self._yield_plain(event, "用法: 查角色 <关键词或角色ID>\n示例: 查角色 10 / 查角色 吉他")
            return

        try:
            tsugu_user = await _get_tsugu_user(self._platform_name(event), event.get_sender_id())
            servers = tsugu_user["displayedServerList"]
        except Exception:
            servers = [3, 0]

        try:
            response = await tsugu_api_async.search_character(servers, text=args)
            chain = response_to_chain(response)
            if chain:
                yield self._yield_result(event, chain)
            else:
                yield self._yield_plain(event, "未找到匹配的角色")
        except FailedException as e:
            yield self._yield_plain(event, e.response.get("data", "查询失败"))
        except Exception as e:
            yield self._yield_plain(event, f"查询出错: {e}")

    # ── 查活动 ────────────────────────────────────────────────────

    @filter.regex(r"^查活动\b")
    async def cmd_search_event(self, event: AstrMessageEvent):
        if self._precheck(event):
            return
        args = self._cmd_args(event)
        if not args:
            yield self._yield_plain(event, "用法: 查活动 <关键词或活动ID>\n示例: 查活动 177 / 查活动 绿 tsugu")
            return

        try:
            tsugu_user = await _get_tsugu_user(self._platform_name(event), event.get_sender_id())
            servers = tsugu_user["displayedServerList"]
        except Exception:
            servers = [3, 0]

        try:
            response = await tsugu_api_async.search_event(servers, text=args)
            chain = response_to_chain(response)
            if chain:
                yield self._yield_result(event, chain)
            else:
                yield self._yield_plain(event, "未找到匹配的活动")
        except FailedException as e:
            yield self._yield_plain(event, e.response.get("data", "查询失败"))
        except Exception as e:
            yield self._yield_plain(event, f"查询出错: {e}")

    # ── 查卡池 ────────────────────────────────────────────────────

    @filter.regex(r"^查卡池\b")
    async def cmd_search_gacha(self, event: AstrMessageEvent):
        if self._precheck(event):
            return
        args = self._cmd_args(event)
        if not args or not args.isdigit():
            yield self._yield_plain(event, "用法: 查卡池 <卡池ID>\n示例: 查卡池 922")
            return

        try:
            tsugu_user = await _get_tsugu_user(self._platform_name(event), event.get_sender_id())
            servers = tsugu_user["displayedServerList"]
        except Exception:
            servers = [3, 0]

        try:
            response = await tsugu_api_async.search_gacha(servers, int(args))
            chain = response_to_chain(response)
            if chain:
                yield self._yield_result(event, chain)
            else:
                yield self._yield_plain(event, "未找到该卡池")
        except FailedException as e:
            yield self._yield_plain(event, e.response.get("data", "查询失败"))
        except Exception as e:
            yield self._yield_plain(event, f"查询出错: {e}")

    # ── 抽卡模拟 ──────────────────────────────────────────────────

    @filter.regex(r"^抽卡模拟\b")
    async def cmd_gacha_simulate(self, event: AstrMessageEvent):
        if self._precheck(event):
            return
        raw = self._cmd_args(event)
        parts = raw.split() if raw else []
        times = int(parts[0]) if parts and parts[0].isdigit() else 10
        gacha_id = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None

        try:
            tsugu_user = await _get_tsugu_user(self._platform_name(event), event.get_sender_id())
            server = tsugu_user["mainServer"]
        except Exception:
            server = 3

        try:
            response = await tsugu_api_async.gacha_simulate(server, times=times, gacha_id=gacha_id)
            chain = response_to_chain(response)
            if chain:
                yield self._yield_result(event, chain)
            else:
                yield self._yield_plain(event, "抽卡模拟失败")
        except FailedException as e:
            yield self._yield_plain(event, e.response.get("data", "模拟失败"))
        except Exception as e:
            yield self._yield_plain(event, f"抽卡模拟出错: {e}")

    # ── 查谱面 ────────────────────────────────────────────────────

    @filter.regex(r"^查谱面\b")
    async def cmd_song_chart(self, event: AstrMessageEvent):
        if self._precheck(event):
            return
        raw = self._cmd_args(event)
        parts = raw.split() if raw else []
        if not parts or not parts[0].isdigit():
            yield self._yield_plain(event, "用法: 查谱面 <曲目ID> [难度]\n示例: 查谱面 1 / 查谱面 1 expert")
            return

        song_id = int(parts[0])
        difficulty_id = None
        if len(parts) > 1:
            diff_str = parts[1].lower()
            difficulty_id = DIFFICULTY_MAP.get(diff_str)
            if difficulty_id is None:
                yield self._yield_plain(event, f"未知难度: {parts[1]}\n可选: easy/normal/hard/expert/special (或 ez/nm/hd/ex/sp)")
                return

        try:
            tsugu_user = await _get_tsugu_user(self._platform_name(event), event.get_sender_id())
            servers = tsugu_user["displayedServerList"]
        except Exception:
            servers = [3, 0]

        try:
            if difficulty_id is not None:
                response = await tsugu_api_async.song_chart(servers, song_id, difficulty_id)
            else:
                response = await tsugu_api_async.song_chart(servers, song_id, 3)
            chain = response_to_chain(response)
            if chain:
                yield self._yield_result(event, chain)
            else:
                yield self._yield_plain(event, "未找到该谱面")
        except FailedException as e:
            yield self._yield_plain(event, e.response.get("data", "查询失败"))
        except Exception as e:
            yield self._yield_plain(event, f"查询出错: {e}")

    # ── 分数表 ────────────────────────────────────────────────────

    @filter.regex(r"^分数表\b")
    async def cmd_song_meta(self, event: AstrMessageEvent):
        if self._precheck(event):
            return
        raw = self._cmd_args(event)
        server = None
        if raw:
            try:
                server = server_name_to_id(raw)
            except ValueError as e:
                yield self._yield_plain(event, str(e))
                return

        try:
            tsugu_user = await _get_tsugu_user(self._platform_name(event), event.get_sender_id())
            servers = tsugu_user["displayedServerList"]
            if server is None:
                server = tsugu_user["mainServer"]
        except Exception:
            servers = [3, 0]
            if server is None:
                server = 3

        try:
            response = await tsugu_api_async.song_meta(servers, server)
            chain = response_to_chain(response)
            if chain:
                yield self._yield_result(event, chain)
            else:
                yield self._yield_plain(event, "未找到分数表")
        except FailedException as e:
            yield self._yield_plain(event, e.response.get("data", "查询失败"))
        except Exception as e:
            yield self._yield_plain(event, f"查询出错: {e}")

    # ── 查试炼 ────────────────────────────────────────────────────

    @filter.regex(r"^查试炼\b")
    async def cmd_event_stage(self, event: AstrMessageEvent):
        if self._precheck(event):
            return
        raw = self._cmd_args(event)
        event_id = None
        meta = False
        parts = raw.split() if raw else []

        for part in parts:
            if part == "-m":
                meta = True
            elif part.isdigit():
                event_id = int(part)

        try:
            tsugu_user = await _get_tsugu_user(self._platform_name(event), event.get_sender_id())
            server = tsugu_user["mainServer"]
        except Exception:
            server = 3

        try:
            response = await tsugu_api_async.event_stage(server, event_id=event_id, meta=meta)
            chain = response_to_chain(response)
            if chain:
                yield self._yield_result(event, chain)
            else:
                yield self._yield_plain(event, "未找到试炼信息")
        except FailedException as e:
            yield self._yield_plain(event, e.response.get("data", "查询失败"))
        except Exception as e:
            yield self._yield_plain(event, f"查询出错: {e}")

    # ── ycx (指定档位预测线) ─────────────────────────────────────

    @filter.regex(r"^ycx\b")
    async def cmd_ycx(self, event: AstrMessageEvent):
        if self._precheck(event):
            return
        raw = self._cmd_args(event)
        parts = raw.split() if raw else []
        if not parts or not parts[0].isdigit():
            yield self._yield_plain(event,
                f"用法: ycx <档位> [活动ID] [服务器名]\n"
                f"可用档线:\n{tier_list_to_string()}\n"
                f"示例: ycx 1000 / ycx 1000 177 jp"
            )
            return

        tier = int(parts[0])
        event_id = None
        server = None

        for p in parts[1:]:
            if p.isdigit() and event_id is None:
                event_id = int(p)
            else:
                try:
                    server = server_name_to_id(p)
                    break
                except ValueError:
                    pass

        try:
            tsugu_user = await _get_tsugu_user(self._platform_name(event), event.get_sender_id())
            if server is None:
                server = tsugu_user["mainServer"]
        except Exception:
            if server is None:
                server = 3

        try:
            response = await tsugu_api_async.cutoff_detail(server, tier, event_id=event_id)
            chain = response_to_chain(response)
            if chain:
                yield self._yield_result(event, chain)
            else:
                yield self._yield_plain(event, "未找到预测线数据")
        except FailedException as e:
            yield self._yield_plain(event, e.response.get("data", "查询失败"))
        except Exception as e:
            yield self._yield_plain(event, f"查询出错: {e}")

    # ── ycxall (所有档位预测线) ───────────────────────────────────

    @filter.regex(r"^ycxall\b")
    async def cmd_ycxall(self, event: AstrMessageEvent):
        if self._precheck(event):
            return
        raw = self._cmd_args(event)
        parts = raw.split() if raw else []
        event_id = None
        server = None

        for part in parts:
            if part.isdigit() and event_id is None:
                event_id = int(part)
            else:
                try:
                    server = server_name_to_id(part)
                except ValueError:
                    pass

        try:
            tsugu_user = await _get_tsugu_user(self._platform_name(event), event.get_sender_id())
            if server is None:
                server = tsugu_user["mainServer"]
        except Exception:
            if server is None:
                server = 3

        try:
            response = await tsugu_api_async.cutoff_all(server, event_id=event_id)
            chain = response_to_chain(response)
            if chain:
                yield self._yield_result(event, chain)
            else:
                yield self._yield_plain(event, "未找到预测线数据")
        except FailedException as e:
            yield self._yield_plain(event, e.response.get("data", "查询失败"))
        except Exception as e:
            yield self._yield_plain(event, f"查询出错: {e}")

    # ── lsycx (历史档线) ─────────────────────────────────────────

    @filter.regex(r"^lsycx\b")
    async def cmd_lsycx(self, event: AstrMessageEvent):
        if self._precheck(event):
            return
        raw = self._cmd_args(event)
        parts = raw.split() if raw else []
        if not parts or not parts[0].isdigit():
            yield self._yield_plain(event,
                f"用法: lsycx <档位> [活动ID] [服务器名]\n"
                f"可用档线:\n{tier_list_to_string()}"
            )
            return

        tier = int(parts[0])
        event_id = None
        server = None

        for part in parts[1:]:
            if part.isdigit() and event_id is None:
                event_id = int(part)
            else:
                try:
                    server = server_name_to_id(part)
                except ValueError:
                    pass

        try:
            tsugu_user = await _get_tsugu_user(self._platform_name(event), event.get_sender_id())
            if server is None:
                server = tsugu_user["mainServer"]
        except Exception:
            if server is None:
                server = 3

        try:
            response = await tsugu_api_async.cutoff_list_of_recent_event(server, tier, event_id=event_id)
            chain = response_to_chain(response)
            if chain:
                yield self._yield_result(event, chain)
            else:
                yield self._yield_plain(event, "未找到历史档线数据")
        except FailedException as e:
            yield self._yield_plain(event, e.response.get("data", "查询失败"))
        except Exception as e:
            yield self._yield_plain(event, f"查询出错: {e}")

    # ── 车牌列表 ──────────────────────────────────────────────────

    @filter.regex(r"^车牌列表\b")
    async def cmd_room_list(self, event: AstrMessageEvent):
        if self._precheck(event):
            return
        try:
            _response = await tsugu_api_async.station_query_all_room()
            response = await tsugu_api_async.room_list(_response["data"])
            chain = response_to_chain(response)
            if chain:
                yield self._yield_result(event, chain)
            else:
                yield self._yield_plain(event, "当前没有车牌")
        except FailedException as e:
            yield self._yield_plain(event, e.response.get("data", "查询失败"))
        except Exception as e:
            yield self._yield_plain(event, f"查询出错: {e}")

    # ── 查玩家 ────────────────────────────────────────────────────

    @filter.regex(r"^查玩家\b")
    async def cmd_search_player(self, event: AstrMessageEvent):
        if self._precheck(event):
            return
        raw = self._cmd_args(event)
        parts = raw.split() if raw else []
        if not parts or not parts[0].isdigit():
            yield self._yield_plain(event, "用法: 查玩家 <玩家ID> [服务器名]\n示例: 查玩家 10000000 / 查玩家 40474621 jp")
            return

        player_id = int(parts[0])
        server = None
        if len(parts) > 1:
            try:
                server = server_name_to_id(parts[1])
            except ValueError:
                pass

        if server is None:
            try:
                tsugu_user = await _get_tsugu_user(self._platform_name(event), event.get_sender_id())
                server = tsugu_user["mainServer"]
            except Exception:
                server = 3

        try:
            response = await tsugu_api_async.search_player(player_id, server)
            chain = response_to_chain(response)
            if chain:
                yield self._yield_result(event, chain)
            else:
                yield self._yield_plain(event, "未找到该玩家")
        except FailedException as e:
            yield self._yield_plain(event, e.response.get("data", "查询失败"))
        except Exception as e:
            yield self._yield_plain(event, f"查询出错: {e}")

    # ── 玩家绑定 ──────────────────────────────────────────────────

    @filter.regex(r"^玩家绑定\b")
    async def cmd_player_bind(self, event: AstrMessageEvent):
        """玩家绑定 [服务器名] — 开始绑定流程"""
        if self._precheck(event):
            return
        raw = self._cmd_args(event)
        server = None
        if raw:
            try:
                server = server_name_to_id(raw)
            except ValueError as e:
                yield self._yield_plain(event, str(e))
                return

        if server is None:
            try:
                tsugu_user = await _get_tsugu_user(self._platform_name(event), event.get_sender_id())
                server = tsugu_user["mainServer"]
            except Exception:
                server = 3

        platform = self._platform_name(event)
        user_id = event.get_sender_id()

        try:
            response = await tsugu_api_async.bind_player_request(platform, user_id)
        except FailedException as e:
            yield self._yield_plain(event, e.response.get("data", "绑定请求失败"))
            return
        except Exception as e:
            yield self._yield_plain(event, f"绑定请求出错: {e}")
            return

        verify_code = str(response["data"]["verifyCode"])

        self._bind_sessions[self._user_key(event)] = {
            "verify_code": verify_code,
            "server": server,
            "action": "bind",
        }

        yield self._yield_plain(event,
            f"正在绑定来自 {server_id_to_full_name(server)} 账号，\n"
            f"请将你的\n评论(个性签名)\n或者\n你的当前使用的卡组的卡组名(乐队编队名称)\n"
            f"改为以下数字后，发送 绑定<玩家ID> 完成绑定\n"
            f"例如: 绑定10000000\n"
            f"验证码: {verify_code}\n\n"
            f"发送 取消绑定 可取消本次操作"
        )

    # ── 解除绑定 ──────────────────────────────────────────────────

    @filter.regex(r"^解除绑定\b")
    async def cmd_player_unbind(self, event: AstrMessageEvent):
        """解除绑定 [服务器名] — 开始解绑流程"""
        if self._precheck(event):
            return
        raw = self._cmd_args(event)
        server = None
        if raw:
            try:
                server = server_name_to_id(raw)
            except ValueError as e:
                yield self._yield_plain(event, str(e))
                return

        platform = self._platform_name(event)
        user_id = event.get_sender_id()

        try:
            tsugu_user = await _get_tsugu_user(platform, user_id)
        except Exception as e:
            yield self._yield_plain(event, str(e))
            return

        if server is None:
            server = tsugu_user["mainServer"]

        try:
            player = _get_user_player(tsugu_user, server)
        except Exception as e:
            yield self._yield_plain(event, str(e))
            return

        player_id = player["playerId"]

        try:
            response = await tsugu_api_async.bind_player_request(platform, user_id)
        except FailedException as e:
            yield self._yield_plain(event, e.response.get("data", "请求失败"))
            return
        except Exception as e:
            yield self._yield_plain(event, f"请求出错: {e}")
            return

        verify_code = str(response["data"]["verifyCode"])

        self._bind_sessions[self._user_key(event)] = {
            "verify_code": verify_code,
            "server": server,
            "action": "unbind",
            "player_id": player_id,
        }

        yield self._yield_plain(event,
            f"正在解除绑定来自 {server_id_to_full_name(server)} 账号 玩家ID: {player_id}\n"
            f"请将你的\n评论(个性签名)\n或者\n你的当前使用的卡组的卡组名(乐队编队名称)\n"
            f"改为以下数字后，发送 绑定<玩家ID> 完成解绑\n"
            f"验证码: {verify_code}\n\n"
            f"发送 取消绑定 可取消本次操作"
        )

    # ── 玩家状态 ──────────────────────────────────────────────────

    @filter.regex(r"^玩家状态\b")
    async def cmd_player_info(self, event: AstrMessageEvent):
        """玩家状态 [服务器名] — 查询自己的玩家状态"""
        if self._precheck(event):
            return
        raw = self._cmd_args(event)
        server = None
        if raw:
            try:
                server = server_name_to_id(raw)
            except ValueError:
                pass

        platform = self._platform_name(event)
        user_id = event.get_sender_id()

        try:
            tsugu_user = await _get_tsugu_user(platform, user_id)
        except Exception as e:
            yield self._yield_plain(event, str(e))
            return

        player_list = tsugu_user["userPlayerList"]
        if not player_list:
            yield self._yield_plain(event, "未绑定任何玩家，请先使用 玩家绑定")
            return

        if server is None:
            server = tsugu_user["mainServer"]

        try:
            player = _get_user_player(tsugu_user, server)
        except Exception as e:
            yield self._yield_plain(event, str(e))
            return

        try:
            response = await tsugu_api_async.search_player(player["playerId"], player["server"])
            chain = response_to_chain(response)
            if chain:
                yield self._yield_result(event, chain)
            else:
                yield self._yield_plain(event, "查询玩家信息失败")
        except FailedException as e:
            yield self._yield_plain(event, e.response.get("data", "查询失败"))
        except Exception as e:
            yield self._yield_plain(event, f"查询出错: {e}")

    # ── 绑定列表 ──────────────────────────────────────────────────

    @filter.regex(r"^绑定列表\b")
    async def cmd_player_list(self, event: AstrMessageEvent):
        """绑定列表 — 查看已绑定玩家列表和当前设置"""
        if self._precheck(event):
            return
        platform = self._platform_name(event)
        user_id = event.get_sender_id()

        try:
            tsugu_user = await _get_tsugu_user(platform, user_id)
        except Exception as e:
            yield self._yield_plain(event, str(e))
            return

        lines = []
        player_list = tsugu_user["userPlayerList"]
        if not player_list:
            lines.append("未绑定任何玩家")
        else:
            lines.append("已绑定玩家列表:")
            for i, player in enumerate(player_list):
                marker = " <- 当前" if i == tsugu_user["userPlayerIndex"] else ""
                lines.append(f"  {i + 1}. {server_id_to_full_name(player['server'])}: {player['playerId']}{marker}")

        lines.append(f"当前主服务器: {server_id_to_full_name(tsugu_user['mainServer'])}")
        lines.append(f"显示服务器: {', '.join(server_id_to_full_name(s) for s in tsugu_user['displayedServerList'])}")

        yield self._yield_plain(event, "\n".join(lines))

    # ── 主服务器 ──────────────────────────────────────────────────

    @filter.regex(r"^主服务器\b")
    async def cmd_switch_main_server(self, event: AstrMessageEvent):
        """主服务器 <服务器名> — 设置主服务器"""
        if self._precheck(event):
            return
        raw = self._cmd_args(event)
        if not raw:
            yield self._yield_plain(event, "用法: 主服务器 <服务器名>\n可选: 日服/国际服/台服/国服/韩服 (或 jp/en/tw/cn/kr)")
            return

        try:
            server = server_name_to_id(raw)
        except ValueError as e:
            yield self._yield_plain(event, str(e))
            return

        platform = self._platform_name(event)
        user_id = event.get_sender_id()

        try:
            await tsugu_api_async.change_user_data(platform, user_id, {"mainServer": server})
            yield self._yield_plain(event, f"已切换到{server_id_to_full_name(server)}模式")
        except Exception as e:
            yield self._yield_plain(event, f"切换出错: {e}")

    # ── 显示服务器 ────────────────────────────────────────────────

    @filter.regex(r"^显示服务器\b")
    async def cmd_displayed_servers(self, event: AstrMessageEvent):
        """显示服务器 <服务器1> <服务器2> ... — 设置默认显示的服务器列表（空参查看当前）"""
        if self._precheck(event):
            return
        raw = self._cmd_args(event)

        if not raw:
            platform = self._platform_name(event)
            user_id = event.get_sender_id()
            try:
                tsugu_user = await _get_tsugu_user(platform, user_id)
            except Exception as e:
                yield self._yield_plain(event, str(e))
                return

            servers = tsugu_user["displayedServerList"]
            yield self._yield_plain(event,
                f"当前显示服务器顺序:\n"
                f"{', '.join(f'{server_id_to_full_name(s)}({server_id_to_short_name(s)})' for s in servers)}\n\n"
                f"修改方法: 显示服务器 <服务器1> <服务器2> ...\n"
                f"示例: 显示服务器 国服 日服\n"
                f"可选: 日服/国际服/台服/国服/韩服 (或 jp/en/tw/cn/kr)"
            )
            return

        server_list: list[int] = []
        for part in raw.split():
            try:
                sid = server_name_to_id(part)
                if sid not in server_list:
                    server_list.append(sid)
            except ValueError:
                yield self._yield_plain(event, f"无法识别的服务器: {part}\n可选: 日服/国际服/台服/国服/韩服 (或 jp/en/tw/cn/kr)")
                return

        if not server_list:
            yield self._yield_plain(event, "请至少指定一个服务器")
            return

        platform = self._platform_name(event)
        user_id = event.get_sender_id()

        try:
            await tsugu_api_async.change_user_data(platform, user_id, {"displayedServerList": server_list})
            names = ", ".join(server_id_to_full_name(s) for s in server_list)
            yield self._yield_plain(event, f"显示服务器已更新为: {names}")
        except Exception as e:
            yield self._yield_plain(event, f"更新出错: {e}")

    # ── 选择绑定 ──────────────────────────────────────────────────

    @filter.regex(r"^选择绑定\b")
    async def cmd_switch_player(self, event: AstrMessageEvent):
        """选择绑定 <编号> — 切换默认使用的绑定玩家"""
        if self._precheck(event):
            return
        raw = self._cmd_args(event)
        if not raw or not raw.isdigit():
            yield self._yield_plain(event, "用法: 选择绑定 <编号>\n使用 绑定列表 查看编号")
            return

        index = int(raw) - 1

        platform = self._platform_name(event)
        user_id = event.get_sender_id()

        try:
            tsugu_user = await _get_tsugu_user(platform, user_id)
        except Exception as e:
            yield self._yield_plain(event, str(e))
            return

        player_list = tsugu_user["userPlayerList"]
        if not player_list:
            yield self._yield_plain(event, "未绑定任何玩家")
            return

        if index < 0 or index >= len(player_list):
            yield self._yield_plain(event, f"编号无效，请输入 1-{len(player_list)}")
            return

        try:
            await tsugu_api_async.change_user_data(platform, user_id, {"userPlayerIndex": index})
            player = player_list[index]
            yield self._yield_plain(event,
                f"已切换默认绑定:\n"
                f"  {server_id_to_full_name(player['server'])}: {player['playerId']}"
            )
        except Exception as e:
            yield self._yield_plain(event, f"切换出错: {e}")

    # ── 随机曲目 ──────────────────────────────────────────────────

    @filter.regex(r"^随机曲目\b")
    async def cmd_random_song(self, event: AstrMessageEvent):
        """随机曲目 [关键词...] — 随机一首曲目，可加关键词筛选"""
        if self._precheck(event):
            return
        raw = self._cmd_args(event)

        try:
            tsugu_user = await _get_tsugu_user(self._platform_name(event), event.get_sender_id())
            server = tsugu_user["mainServer"]
        except Exception:
            server = 3

        try:
            response = await tsugu_api_async.song_random(server, text=raw if raw else None)
            chain = response_to_chain(response)
            if chain:
                yield self._yield_result(event, chain)
            else:
                yield self._yield_plain(event, "未找到匹配的曲目")
        except FailedException as e:
            yield self._yield_plain(event, e.response.get("data", "查询失败"))
        except Exception as e:
            yield self._yield_plain(event, f"查询出错: {e}")
    # ── 开启车牌转发 ──────────────────────────────────────────────
    
    @filter.regex(r"^开启车牌转发\b")
    async def cmd_share_room_on(self, event: AstrMessageEvent):
        """开启车牌转发 — 开启后发送的车牌会被提交到公共频道"""
        if self._precheck(event):
            return
        
        platform = self._platform_name(event)
        user_id = event.get_sender_id()
        
        try:
            await tsugu_api_async.change_user_data(platform, user_id, {"shareRoomNumber": True})
            yield self._yield_plain(event, "已开启车牌转发\n开启后，您发送的车牌消息会被提交到公共频道")
        except Exception as e:
            yield self._yield_plain(event, f"开启失败: {e}")
    
    # ── 关闭车牌转发 ──────────────────────────────────────────────
    
    @filter.regex(r"^关闭车牌转发\b")
    async def cmd_share_room_off(self, event: AstrMessageEvent):
        """关闭车牌转发"""
        if self._precheck(event):
            return
        
        platform = self._platform_name(event)
        user_id = event.get_sender_id()
        
        try:
            await tsugu_api_async.change_user_data(platform, user_id, {"shareRoomNumber": False})
            yield self._yield_plain(event, "已关闭车牌转发")
        except Exception as e:
            yield self._yield_plain(event, f"关闭失败: {e}")
    
    # ── 车牌消息拦截器 ────────────────────────────────────────────
    
    @filter.regex(r"^[\d★☆]+$")
    async def handle_room_number(self, event: AstrMessageEvent):
        """拦截车牌消息（纯数字+星级），提交到公共频道"""
        if self._precheck(event):
            return
        
        room_number = event.message_str.strip()
        platform = self._platform_name(event)
        user_id = event.get_sender_id()
        
        try:
            tsugu_user = await _get_tsugu_user(platform, user_id)
            # 检查用户是否开启了车牌转发
            if not tsugu_user.get("shareRoomNumber", False):
                return  # 未开启，不处理
        except Exception:
            return
        
        # 提交车牌到公共频道
        try:
            response = await tsugu_api_async.station_submit_room_number(room_number, platform, user_id)
            if response.get("status") == "success":
                yield self._yield_plain(event, f"车牌 {room_number} 已提交到公共频道")
            else:
                yield self._yield_plain(event, f"提交失败: {response.get('data', '未知错误')}")
        except FailedException as e:
            yield self._yield_plain(event, e.response.get("data", "提交失败"))
        except Exception as e:
            yield self._yield_plain(event, f"提交出错: {e}")
