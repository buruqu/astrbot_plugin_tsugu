"""
AstrBot 插件: TsuguBangDreamBot
BanG Dream! 游戏助手，基于 tsugu-api-python

功能: 查曲/查卡/查卡面/查角色/查活动/查卡池/抽卡模拟/查谱面/分数表/查试炼/
     ycx/ycxall/lsycx/车牌列表/查玩家/玩家绑定/解除绑定/玩家状态/绑定列表/
     主服务器/显示服务器/选择绑定/随机曲目

重构说明:
- 保留 AstrBot 框架集成、白名单/@唤醒/别名注入等特色功能
- 从原版 tsugu-bangdream-bot 移植 car_keyword.json 车牌关键词过滤
- 从原版移植 checkLeftDigits 左侧5-6位数字检测逻辑
- 补充原版的更多命令别名
- 车牌提交改为静默（不回复），与原版行为一致
"""

from __future__ import annotations

import json
import os
import re
import time
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


# ═══════════════════════════════════════════════════════════════════════════
# 服务器名称工具 (从原版移植)
# ═══════════════════════════════════════════════════════════════════════════

def server_name_to_id(server: str) -> int:
    """服务器名称 -> ID (支持数字/全名/缩写)"""
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
    """服务器 ID -> 全名"""
    names = {0: "日服", 1: "国际服", 2: "台服", 3: "国服", 4: "韩服"}
    name = names.get(server)
    if name is None:
        raise ValueError(f"服务器不存在: {server}")
    return name


def server_id_to_short_name(server: int) -> str:
    """服务器 ID -> 缩写"""
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

# 档位列表 (从原版移植)
TIER_LISTS = {
    "jp": [20, 30, 40, 50, 100, 200, 300, 400, 500, 1000, 2000, 5000, 10000, 20000, 30000, 50000],
    "tw": [100, 500],
    "en": [50, 100, 300, 500, 1000, 2000, 2500],
    "kr": [100],
    "cn": [20, 30, 40, 50, 100, 200, 300, 400, 500, 1000, 2000, 3000, 4000, 5000, 10000, 20000, 30000, 50000],
}


def tier_list_to_string() -> str:
    results = []
    for server, tiers in TIER_LISTS.items():
        results.append(server + " : " + ", ".join(str(t) for t in tiers))
    return "\n".join(results)


# ═══════════════════════════════════════════════════════════════════════════
# 车牌关键词过滤 (从原版 car_keyword.json 移植)
# ═══════════════════════════════════════════════════════════════════════════

def _load_car_keywords(plugin_dir: str) -> tuple[set[str], set[str]]:
    """加载车牌关键词配置"""
    config_path = os.path.join(plugin_dir, "car_keyword.json")
    default_car = {
        "q1", "q2", "q3", "q4", "缺1", "缺2", "缺3", "缺4",
        "差1", "差2", "差3", "差4", "3火", "三火", "3把", "三把",
        "打满", "清火", "奇迹", "中途", "大e", "大分e", "exi",
        "大分跳", "大跳", "大a", "大s", "大分a", "大分s",
        "长途", "e3", "e长", "s3", "s长", "5级", "满级",
        "130", "150", "生日车", "军训", "禁fc"
    }
    default_fake = {
        "🦐", "虾", "melt", "孜然", "孑然妒火", "周回", "实效", "删语音",
        "114514", "野兽", "恶臭", "1919", "下北泽", "粪", "糞", "臭",
        "11451", "xiabeize", "雀魂", "麻将", "打牌", "maj", "麻",
        "[", "]", "断幺", "qq.com", "腾讯会议", "master",
        "疯狂星期四", "离开了我们", "日元", "av", "bv"
    }
    
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            car = set(data.get("car", []))
            fake = set(data.get("fake", []))
            if car and fake:
                return car, fake
    except Exception as e:
        logger.warning(f"加载 car_keyword.json 失败，使用默认配置: {e}")
    
    return default_car, default_fake


def check_left_digits(text: str) -> int:
    """检查消息左侧是否为 5 或 6 位数字 (从原版移植)
    
    返回: 数字 (5-6位) 或 0 (不匹配)
    """
    # 优先匹配 6 位数字
    match6 = re.match(r"^(\d{6})", text)
    if match6:
        return int(match6.group(1))
    # 再匹配 5 位数字
    match5 = re.match(r"^(\d{5})", text)
    if match5:
        return int(match5.group(1))
    return 0


# ═══════════════════════════════════════════════════════════════════════════
# API 响应转 AstrBot 消息链
# ═══════════════════════════════════════════════════════════════════════════

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


async def _fuzzy_search_server(text: str) -> int:
    """模糊搜索服务器名 (从原版移植)"""
    try:
        result = await tsugu_api_async.fuzzy_search(text)
        if result and "server" in result and result["server"]:
            return result["server"][0]
    except Exception:
        pass
    return -1


# ═══════════════════════════════════════════════════════════════════════════
# 插件类
# ═══════════════════════════════════════════════════════════════════════════

@register(
    "astrbot_plugin_tsugu",
    "QClaw",
    "BanG Dream! 游戏助手 (TsuguBangDreamBot)",
    "2.0.0",
    "https://github.com/buruqu/astrbot_plugin_tsugu",
)
class TsuguPlugin(Star):
    """Tsugu BanG Dream Bot AstrBot 插件
    
    重构版本:
    - 从原版 tsugu-bangdream-bot 移植 car_keyword.json 车牌关键词过滤
    - 从原版移植 checkLeftDigits 左侧5-6位数字检测逻辑
    - 补充原版的更多命令别名
    - 车牌提交改为静默（不回复），与原版行为一致
    """

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

        # Bandori Station Token 配置
        self._bandori_station_token = config.get("bandori_station_token", "") or None

        # 白名单 / @唤醒 / 别名配置
        self._whitelist_enabled = config.get("whitelist_enabled", False)
        self._whitelist_groups = self._parse_whitelist(config.get("whitelist_groups", []))
        self._at_wake_enabled = config.get("at_wake_enabled", True)
        self._at_sender_enabled = config.get("at_sender_enabled", False)
        self._quote_reply_enabled = config.get("quote_reply_enabled", False)
        raw_aliases = config.get("command_aliases", "{}")
        parsed_aliases = self._parse_aliases(raw_aliases)
        # 默认别名 (从原版移植更多)
        if not parsed_aliases:
            parsed_aliases = {
                # 车牌列表别名
                "ycm": "车牌列表",
                "有车吗": "车牌列表",
                "车来": "车牌列表",
                # 查卡别名
                "查卡牌": "查卡",
                # 查卡面别名
                "查卡插画": "查卡面",
                "查插画": "查卡面",
                # 查玩家别名
                "查询玩家": "查玩家",
                # 主服务器别名
                "服务器模式": "主服务器",
                "切换服务器": "主服务器",
                # 显示服务器别名
                "设置默认服务器": "显示服务器",
                "默认服务器": "显示服务器",
                # 绑定列表别名
                "玩家列表": "绑定列表",
                "玩家信息列表": "绑定列表",
                # 选择绑定别名
                "默认玩家ID": "选择绑定",
                "默认玩家": "选择绑定",
                "玩家ID": "选择绑定",
                # 分数表别名
                "查询分数表": "分数表",
                "查分数表": "分数表",
                "查询分数榜": "分数表",
                "查分数榜": "分数表",
                # 查试炼别名
                "查stage": "查试炼",
                "查舞台": "查试炼",
                "查festival": "查试炼",
                "查5v5": "查试炼",
                # ycxall 别名
                "myycx": "ycxall",
                # 随机曲目别名
                "随机": "随机曲目",
                # 解除绑定别名
                "解绑玩家": "解除绑定",
            }
        self._command_aliases = parsed_aliases
        self._wake_prefix = config.get("wake_prefix", "")

        # 绑定验证会话 {user_key: {verify_code, server, action, player_id, expire}}
        self._bind_sessions: dict = {}

        # 插件目录
        plugin_dir = os.path.dirname(os.path.abspath(__file__))
        self._no_car_image_path = os.path.join(plugin_dir, "assets", "no_car.jpg")

        # 加载车牌关键词 (从原版移植)
        self._car_keywords, self._fake_keywords = _load_car_keywords(plugin_dir)

        logger.info(f"Tsugu 插件已初始化 (白名单={'启用' if self._whitelist_enabled else '关闭'}, "
                     f"@唤醒={'启用' if self._at_wake_enabled else '关闭'}, "
                     f"唤醒前缀='{self._wake_prefix or '无'}', "
                     f"别名数={len(self._command_aliases)}, "
                     f"车牌关键词={len(self._car_keywords)}, "
                     f"假车牌关键词={len(self._fake_keywords)})")

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
            "开启车牌转发": "cmd_share_room_on", "关闭车牌转发": "cmd_share_room_off",
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
        injected_count = 0
        for handler_md in star_handlers_registry:
            mp = handler_md.handler_module_path or ""
            if "astrbot_plugin_tsugu" not in mp:
                continue
            handler_name = handler_md.handler_name
            cmd_name = method_to_cmd.get(handler_name)
            if not cmd_name or cmd_name not in cmd_new_aliases:
                continue

            for event_filter in handler_md.event_filters:
                if not hasattr(event_filter, "regex_str"):
                    continue

                new_aliases = cmd_new_aliases[cmd_name]
                all_cmds = {cmd_name} | new_aliases
                suffix = r"(?:\s|$)"
                if len(all_cmds) == 1:
                    new_pattern = f"^{list(all_cmds)[0]}{suffix}"
                else:
                    new_pattern = f"^(?:{'|'.join(sorted(all_cmds))}){suffix}"

                event_filter.regex_str = new_pattern
                if hasattr(event_filter, "regex"):
                    event_filter.regex = re.compile(new_pattern)

                injected_count += len(new_aliases)
                logger.info(f"命令 '{cmd_name}' 添加别名: {new_aliases}，pattern: {new_pattern}")

        # 自定义唤醒前缀注入
        prefix_injected = 0
        if self._wake_prefix:
            prefix_escaped = re.escape(self._wake_prefix)
            for handler_md in star_handlers_registry:
                mp = handler_md.handler_module_path or ""
                if "astrbot_plugin_tsugu" not in mp:
                    continue
                for event_filter in handler_md.event_filters:
                    if hasattr(event_filter, "regex_str"):
                        old_pattern = event_filter.regex_str
                        if old_pattern.startswith("^"):
                            new_pattern = f"^(?:{prefix_escaped})?{old_pattern[1:]}"
                            event_filter.regex_str = new_pattern
                            if hasattr(event_filter, "regex"):
                                event_filter.regex = re.compile(new_pattern)
                            prefix_injected += 1
            logger.info(f"Tsugu 唤醒前缀注册完成: 前缀='{self._wake_prefix}', 共注入 {prefix_injected} 个 pattern")

        logger.info(f"Tsugu 别名注册完成: 共注入 {injected_count} 个别名")

    # ── 配置解析工具 ──────────────────────────────────────────────

    @staticmethod
    def _parse_whitelist(groups: list | str) -> set[str]:
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
        """获取命令参数（去掉命令名后的文本）"""
        msg = event.message_str.strip()
        parts = msg.split(None, 1)
        return parts[1] if len(parts) > 1 else ""

    # ── 白名单与 @唤醒 检查 ──────────────────────────────────────

    def _is_group_message(self, event: AstrMessageEvent) -> bool:
        return bool(event.get_group_id())

    def _check_whitelist(self, event: AstrMessageEvent) -> bool:
        if not self._whitelist_enabled:
            return True
        if not self._is_group_message(event):
            return True
        group_id = str(event.get_group_id())
        return group_id in self._whitelist_groups

    def _precheck(self, event: AstrMessageEvent) -> bool:
        """统一的命令前置检查。返回 True 表示被拦截（应 return），False 表示通过。"""
        if not self._check_whitelist(event):
            return True
        if self._at_wake_enabled:
            is_at = getattr(event, "is_at_or_wake_command", False)
            if not is_at:
                if self._wake_prefix:
                    msg = event.message_str.strip()
                    if msg.startswith(self._wake_prefix):
                        pass
                    else:
                        return True
                else:
                    return True
        return False

    # ── 回复装饰：@发送人 + 引用 ──────────────────────────────────

    def _wrap_chain(self, event: AstrMessageEvent, chain: list) -> list:
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
        wrapped = self._wrap_chain(event, chain)
        return event.chain_result(wrapped)

    def _yield_plain(self, event: AstrMessageEvent, text: str):
        chain = [Plain(text)]
        wrapped = self._wrap_chain(event, chain)
        return event.chain_result(wrapped)

    # ── 绑定验证拦截器 ────────────────────────────────────────────

    @filter.regex(r"^绑定\s*(\d{5,15})$")
    async def handle_bind_verify(self, event: AstrMessageEvent):
        """拦截 "绑定 <玩家ID>" 格式的消息，完成绑定验证"""
        if self._precheck(event):
            return

        # 定期清理过期会话
        current_time = time.time()
        expired_keys = [
            k for k, v in self._bind_sessions.items()
            if current_time > v.get("expire", 0)
        ]
        for k in expired_keys:
            self._bind_sessions.pop(k, None)
        if expired_keys:
            logger.info(f"已清理 {len(expired_keys)} 个过期绑定会话")

        user_key = self._user_key(event)
        session = self._bind_sessions.get(user_key)

        if not session:
            return
        
        if "expire" in session and time.time() > session["expire"]:
            self._bind_sessions.pop(user_key, None)
            yield self._yield_plain(event, "绑定验证已超时（10分钟），请重新使用 玩家绑定 或 解除绑定 开始新的流程")
            return

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
                platform, user_id, server, player_id, action
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

    # ═══════════════════════════════════════════════════════════════════════════
    # 查询命令
    # ═══════════════════════════════════════════════════════════════════════════

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

    # ═══════════════════════════════════════════════════════════════════════════
    # 档线查询命令
    # ═══════════════════════════════════════════════════════════════════════════

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

    # ═══════════════════════════════════════════════════════════════════════════
    # 车牌相关命令
    # ═══════════════════════════════════════════════════════════════════════════

    @filter.regex(r"^车牌列表\b")
    async def cmd_room_list(self, event: AstrMessageEvent):
        """车牌列表 [关键词] — 获取车牌列表，支持关键词过滤 (从原版移植关键词过滤)"""
        if self._precheck(event):
            return
        raw = self._cmd_args(event)
        keyword = raw.strip() if raw else None
        
        try:
            _response = await tsugu_api_async.station_query_all_room()
            rooms = _response.get("data", [])
            
            # 关键词过滤 (从原版移植)
            if keyword and rooms:
                rooms = [r for r in rooms if keyword in r.get("rawMessage", "")]
                if not rooms:
                    yield self._yield_plain(event, f"没有找到包含 {keyword} 的房间")
                    return
            
            response = await tsugu_api_async.room_list(rooms)
            chain = response_to_chain(response)
            if chain:
                yield self._yield_result(event, chain)
            else:
                if os.path.exists(self._no_car_image_path):
                    img_chain = [Image.fromFileSystem(self._no_car_image_path)]
                    yield self._yield_result(event, img_chain)
                else:
                    yield self._yield_plain(event, "当前没有车牌")
        except FailedException as e:
            yield self._yield_plain(event, e.response.get("data", "查询失败"))
        except Exception as e:
            yield self._yield_plain(event, f"查询出错: {e}")

    @filter.regex(r"^开启车牌转发\b")
    async def cmd_share_room_on(self, event: AstrMessageEvent):
        if self._precheck(event):
            return
        
        platform = self._platform_name(event)
        user_id = event.get_sender_id()
        
        try:
            await tsugu_api_async.change_user_data(platform, user_id, {"shareRoomNumber": True})
            yield self._yield_plain(event, "已开启车牌转发\n开启后，您发送的车牌消息会被提交到公共频道")
        except Exception as e:
            yield self._yield_plain(event, f"开启失败: {e}")
    
    @filter.regex(r"^关闭车牌转发\b")
    async def cmd_share_room_off(self, event: AstrMessageEvent):
        if self._precheck(event):
            return
        
        platform = self._platform_name(event)
        user_id = event.get_sender_id()
        
        try:
            await tsugu_api_async.change_user_data(platform, user_id, {"shareRoomNumber": False})
            yield self._yield_plain(event, "已关闭车牌转发")
        except Exception as e:
            yield self._yield_plain(event, f"关闭失败: {e}")

    # ═══════════════════════════════════════════════════════════════════════════
    # 玩家相关命令
    # ═══════════════════════════════════════════════════════════════════════════

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

    @filter.regex(r"^玩家绑定\b")
    async def cmd_player_bind(self, event: AstrMessageEvent):
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
            "expire": time.time() + 600,
        }

        yield self._yield_plain(event,
            f"正在绑定来自 {server_id_to_full_name(server)} 账号\n\n"
            f"验证方式（二选一）：\n"
            f"1. 将【评论/个性签名】改为：{verify_code}\n"
            f"2. 将【卡组名/乐队编队名称】改为：{verify_code}\n\n"
            f"修改后发送：绑定 <玩家ID>\n"
            f"例如：绑定 10000000\n\n"
            f"验证码：{verify_code}\n"
            f"发送「取消绑定」可取消本次操作"
        )

    @filter.regex(r"^解除绑定\b")
    async def cmd_player_unbind(self, event: AstrMessageEvent):
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
            "expire": time.time() + 600,
        }

        yield self._yield_plain(event,
            f"正在解除绑定来自 {server_id_to_full_name(server)} 账号\n"
            f"玩家ID: {player_id}\n\n"
            f"验证方式（二选一）：\n"
            f"1. 将【评论/个性签名】改为：{verify_code}\n"
            f"2. 将【卡组名/乐队编队名称】改为：{verify_code}\n\n"
            f"修改后发送：绑定 <玩家ID>\n"
            f"例如：绑定 {player_id}\n\n"
            f"验证码：{verify_code}\n"
            f"发送「取消绑定」可取消本次操作"
        )

    @filter.regex(r"^玩家状态(?:\s*(\d+))?(?:\s|$)")
    async def cmd_player_info(self, event: AstrMessageEvent, player_index: str = ""):
        if self._precheck(event):
            return

        raw = self._cmd_args(event).strip()
        platform = self._platform_name(event)
        user_id = event.get_sender_id()

        server = None
        index = None

        if player_index and player_index.isdigit():
            index = int(player_index) - 1
            raw = ""

        if raw:
            if raw.isdigit():
                index = int(raw) - 1
            else:
                try:
                    server = server_name_to_id(raw)
                except ValueError:
                    pass

        try:
            tsugu_user = await _get_tsugu_user(platform, user_id)
        except Exception as e:
            yield self._yield_plain(event, str(e))
            return

        player_list = tsugu_user["userPlayerList"]
        if not player_list:
            yield self._yield_plain(event, "未绑定任何玩家，请先使用 玩家绑定")
            return

        try:
            player = _get_user_player(tsugu_user, server, index)
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

    @filter.regex(r"^绑定列表\b")
    async def cmd_player_list(self, event: AstrMessageEvent):
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

    @filter.regex(r"^主服务器\b")
    async def cmd_switch_main_server(self, event: AstrMessageEvent):
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

    @filter.regex(r"^显示服务器\b")
    async def cmd_displayed_servers(self, event: AstrMessageEvent):
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

    @filter.regex(r"^选择绑定\b")
    async def cmd_switch_player(self, event: AstrMessageEvent):
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

    @filter.regex(r"^随机曲目\b")
    async def cmd_random_song(self, event: AstrMessageEvent):
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

    # ═══════════════════════════════════════════════════════════════════════════
    # 车牌消息拦截器 (从原版移植 checkLeftDigits + car_keyword 逻辑)
    # ═══════════════════════════════════════════════════════════════════════════

    @filter.regex(r".*")
    async def handle_room_number(self, event: AstrMessageEvent):
        """拦截车牌消息，提交到公共频道
        
        逻辑 (从原版移植):
        1. checkLeftDigits 检测左侧 5-6 位数字
        2. 检查消息是否包含 car 关键词且不含 fake 关键词
        3. 检查用户是否开启车牌转发
        4. 提交到 BandoriStation 并回复提交结果
        """
        if self._precheck(event):
            return
        
        msg = event.message_str.strip()
        
        # 1. 检测左侧 5-6 位数字 (从原版移植)
        room_number = check_left_digits(msg)
        if room_number == 0:
            return  # 不是车牌格式
        
        # 2. 检查 car/fake 关键词 (从原版移植)
        msg_lower = msg.lower()
        
        # 检查是否包含 fake 关键词
        for fake_kw in self._fake_keywords:
            if fake_kw.lower() in msg_lower:
                return  # 是假车牌，不处理
        
        # 检查是否包含 car 关键词
        is_car = False
        for car_kw in self._car_keywords:
            if car_kw.lower() in msg_lower:
                is_car = True
                break
        
        if not is_car:
            return  # 不是车牌
        
        platform = self._platform_name(event)
        user_id = event.get_sender_id()
        
        # 3. 检查用户是否开启车牌转发
        try:
            tsugu_user = await _get_tsugu_user(platform, user_id)
            if not tsugu_user.get("shareRoomNumber", False):
                return  # 未开启，不处理
        except Exception:
            return
        
        # 4. 提交车牌到公共频道
        try:
            sender_name = event.get_sender_name() or user_id
            response = await tsugu_api_async.station_submit_room_number(
                room_number,
                msg,
                platform,
                user_id,
                sender_name,
                bandori_station_token=self._bandori_station_token,
            )
            if response.get("status") == "success":
                yield self._yield_plain(event, f"车牌 {room_number} 已提交到公共频道")
            else:
                yield self._yield_plain(event, f"提交失败: {response.get('data', '未知错误')}")
        except FailedException as e:
            yield self._yield_plain(event, e.response.get("data", "提交失败"))
        except Exception as e:
            yield self._yield_plain(event, f"提交出错: {e}")
