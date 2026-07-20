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
from typing import Optional

import tsugu_api_async
from tsugu_api_core.exception import FailedException
from tsugu_api_core._network import Api
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

VALID_SERVER_IDS = {0, 1, 2, 3, 4}
DEFAULT_DISPLAYED_SERVERS = [3, 0]


def server_name_to_id(server: str) -> int:
    """服务器名称 -> ID (支持数字/全名/缩写)"""
    mapping = {
        "0": 0, "1": 1, "2": 2, "3": 3, "4": 4,
        "日": 0, "日本": 0, "日服": 0, "日本服": 0,
        "国际": 1, "英": 1, "英语": 1, "国际服": 1,
        "台": 2, "台湾": 2, "台服": 2, "台湾服": 2,
        "国": 3, "中国": 3, "国服": 3, "国内服": 3,
        "韩": 4, "韩国": 4, "韩服": 4, "韩国服": 4,
        "jp": 0, "en": 1, "tw": 2, "cn": 3, "kr": 4,
    }
    result = mapping.get(server.strip().lower() if server else "")
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
    "简单": 0, "简": 0, "普通": 1, "普": 1,
    "困难": 2, "困": 2, "专家": 3, "专": 3,
    "特殊": 4, "特": 4,
    "0": 0, "1": 1, "2": 2, "3": 3, "4": 4,
}

# 档位列表 (从原版移植)
TIER_LISTS = {
    "jp": [20, 30, 40, 50, 100, 200, 300, 400, 500, 1000, 2000, 5000, 10000, 20000, 30000, 50000],
    "tw": [100, 500],
    "en": [50, 100, 300, 500, 1000, 2000, 2500],
    "kr": [100],
    "cn": [20, 30, 40, 50, 100, 200, 300, 400, 500, 1000, 1500, 2000, 3000, 4000, 5000, 10000, 20000, 30000, 50000],
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
    """返回消息左侧严格的 5 或 6 位 ASCII 房间号，否则返回 0。"""
    match = re.match(r"^([0-9]{5,6})(?![0-9])", text.strip())
    return int(match.group(1)) if match else 0


def match_room_number(
    text: str,
    car_keywords: set[str],
    fake_keywords: set[str],
) -> int:
    """识别上游定义的车牌消息并返回房间号。"""
    room_number = check_left_digits(text)
    if room_number == 0:
        return 0

    normalized = text.lower()
    if any(keyword.lower() in normalized for keyword in fake_keywords):
        return 0
    if not any(keyword.lower() in normalized for keyword in car_keywords):
        return 0
    return room_number


# ═══════════════════════════════════════════════════════════════════════════
# API 响应转 AstrBot 消息链
# ═══════════════════════════════════════════════════════════════════════════

class TsuguResponseError(RuntimeError):
    """Tsugu API 返回了业务失败或无效结构。"""


def _require_success_response(response: object, fallback: str) -> object:
    if not isinstance(response, dict):
        raise TsuguResponseError(f"{fallback}: 响应格式无效")
    if response.get("status") != "success":
        raise TsuguResponseError(str(response.get("data") or fallback))
    return response.get("data")


def _failed_exception_message(error: Exception, fallback: str) -> str:
    response = getattr(error, "response", None)
    if isinstance(response, dict):
        return str(response.get("data") or fallback)
    return str(error) or fallback


def response_to_chain(response: object) -> list:
    """将 Tsugu 查询响应安全转换为 AstrBot 消息链。"""
    if isinstance(response, dict):
        if response.get("status") == "failed":
            return [Plain(str(response.get("data") or "请求失败"))]
        response = response.get("data", [])
    if not isinstance(response, list):
        return [Plain(str(response))] if response not in (None, "") else []

    chain: list = []
    for item in response:
        if isinstance(item, str):
            chain.append(Plain(item))
            continue
        if not isinstance(item, dict):
            logger.warning(f"忽略无法识别的 Tsugu 响应项: {type(item).__name__}")
            continue
        if item.get("type") == "string":
            chain.append(Plain(str(item.get("string", ""))))
        elif item.get("type") == "base64":
            b64_data = item.get("string", "")
            if b64_data:
                chain.append(Image.fromBase64(b64_data))
    return chain


def _normalize_tsugu_user(data: object) -> dict:
    if not isinstance(data, dict):
        raise TsuguResponseError("用户数据格式无效")

    normalized = dict(data)
    try:
        main_server = int(data.get("mainServer", 3))
    except (TypeError, ValueError):
        main_server = 3
    if main_server not in VALID_SERVER_IDS:
        main_server = 3

    displayed_servers: list[int] = []
    raw_displayed = data.get("displayedServerList", DEFAULT_DISPLAYED_SERVERS)
    if isinstance(raw_displayed, (list, tuple)):
        for value in raw_displayed:
            try:
                server = int(value)
            except (TypeError, ValueError):
                continue
            if server in VALID_SERVER_IDS and server not in displayed_servers:
                displayed_servers.append(server)
    if not displayed_servers:
        displayed_servers = list(DEFAULT_DISPLAYED_SERVERS)

    players: list[dict] = []
    raw_players = data.get("userPlayerList", [])
    if isinstance(raw_players, list):
        for player in raw_players:
            if not isinstance(player, dict):
                continue
            try:
                player_id = int(player.get("playerId"))
                server = int(player.get("server"))
            except (TypeError, ValueError):
                continue
            if player_id > 0 and server in VALID_SERVER_IDS:
                players.append({**player, "playerId": player_id, "server": server})

    try:
        player_index = int(data.get("userPlayerIndex", 0))
    except (TypeError, ValueError):
        player_index = 0
    if not players or player_index < 0 or player_index >= len(players):
        player_index = 0

    normalized.update(
        {
            "mainServer": main_server,
            "displayedServerList": displayed_servers,
            "shareRoomNumber": bool(data.get("shareRoomNumber", True)),
            "userPlayerIndex": player_index,
            "userPlayerList": players,
        }
    )
    return normalized


async def _get_tsugu_user(platform: str, user_id: str) -> dict:
    """获取 tsugu 用户数据"""
    try:
        response = await tsugu_api_async.get_user_data(platform, user_id)
    except FailedException as e:
        raise TsuguResponseError(_failed_exception_message(e, "获取用户数据失败")) from e
    except Exception as e:
        raise TsuguResponseError(f"获取用户数据失败: {e}") from e
    return _normalize_tsugu_user(
        _require_success_response(response, "获取用户数据失败")
    )


async def _change_user_data(platform: str, user_id: str, update: dict) -> None:
    try:
        response = await tsugu_api_async.change_user_data(platform, user_id, update)
    except FailedException as e:
        raise TsuguResponseError(
            _failed_exception_message(e, "更新用户数据失败")
        ) from e
    _require_success_response(response, "更新用户数据失败")


async def _request_bind_code(platform: str, user_id: str) -> str:
    response = await tsugu_api_async.bind_player_request(platform, user_id)
    data = _require_success_response(response, "获取绑定验证码失败")
    if not isinstance(data, dict) or "verifyCode" not in data:
        raise TsuguResponseError("绑定验证码响应格式无效")
    verify_code = str(data["verifyCode"])
    if not re.fullmatch(r"[0-9]{5}", verify_code):
        raise TsuguResponseError("绑定验证码格式无效")
    return verify_code


async def _submit_room_number(
    number: int,
    raw_message: str,
    platform: str,
    user_id: str,
    user_name: str,
    avatar_url: Optional[str] = None,
    bandori_station_token: Optional[str] = None,
) -> dict:
    """按 Tsugu 后端的毫秒时间戳契约提交车牌。

    tsugu-api-python 1.5.10 在此接口使用秒级时间戳，会让后端把新车牌
    立即判定为已过期，因此暂时复用其网络层直接发送正确的请求体。
    """
    data = {
        "number": number,
        "rawMessage": raw_message,
        "platform": platform,
        "userId": str(user_id),
        "userName": str(user_name),
        "time": int(time.time() * 1000),
    }
    if avatar_url:
        data["avatarUrl"] = avatar_url
    if bandori_station_token:
        data["bandoriStationToken"] = bandori_station_token

    response = await Api(
        settings.userdata_backend_url,
        "/station/submitRoomNumber",
        proxy=settings.userdata_backend_proxy,
    ).apost(data)
    result = response.json()
    if not isinstance(result, dict):
        raise ValueError("车牌提交接口返回了无效响应")
    return result


def _get_user_player(tsugu_user: dict, server: Optional[int] = None, index: Optional[int] = None) -> dict:
    """从 tsugu 用户数据中获取指定服务器的绑定玩家"""
    server = server if server is not None else tsugu_user.get("mainServer", 3)
    player_list = tsugu_user.get("userPlayerList", [])
    player_index = index if index is not None else tsugu_user.get("userPlayerIndex", 0)

    if not player_list:
        raise ValueError("用户未绑定玩家")

    if index is not None:
        if index < 0 or index >= len(player_list):
            raise ValueError("无效的绑定信息ID")
        return player_list[index]

    if not isinstance(player_index, int) or not 0 <= player_index < len(player_list):
        player_index = 0

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
        data = result.get("data", result) if isinstance(result, dict) else {}
        servers = data.get("server", []) if isinstance(data, dict) else []
        if servers:
            server = int(servers[0])
            if server in VALID_SERVER_IDS:
                return server
    except Exception:
        pass
    return -1


async def _resolve_server_name(text: str) -> int:
    try:
        return server_name_to_id(text)
    except ValueError:
        server = await _fuzzy_search_server(text)
        if server in VALID_SERVER_IDS:
            return server
        raise ValueError(f"服务器不存在: {text}") from None


async def _resolve_difficulty(text: str) -> int:
    key = text.strip().lower()
    if key in DIFFICULTY_MAP:
        return DIFFICULTY_MAP[key]
    try:
        result = await tsugu_api_async.fuzzy_search(key)
        data = result.get("data", result) if isinstance(result, dict) else {}
        difficulties = data.get("difficulty", []) if isinstance(data, dict) else []
        if difficulties:
            difficulty = int(difficulties[0])
            if difficulty in VALID_SERVER_IDS:
                return difficulty
    except Exception:
        pass
    raise ValueError(f"未知难度: {text}")


def _parse_gacha_arguments(
    invoked_command: str,
    raw: str,
    max_times: int,
) -> tuple[int, Optional[int]]:
    explicit_times = 1 if invoked_command == "单抽" else None
    if invoked_command in {"十连", "新手十连"}:
        explicit_times = 10

    numbers: list[int] = []
    for part in raw.split():
        if part == "单抽":
            explicit_times = 1
        elif part in {"十连", "新手十连"}:
            explicit_times = 10
        elif re.fullmatch(r"[0-9]+", part):
            numbers.append(int(part))
        else:
            raise ValueError(f"无法识别的抽卡参数: {part}")

    if explicit_times is not None:
        if len(numbers) > 1:
            raise ValueError("单抽/十连模式最多指定一个卡池ID")
        times = explicit_times
        gacha_id = numbers[0] if numbers else None
    else:
        if len(numbers) > 2:
            raise ValueError("抽卡模拟最多接受抽卡次数和卡池ID两个数字")
        times = numbers[0] if numbers else 10
        gacha_id = numbers[1] if len(numbers) > 1 else None

    if times < 1 or times > max_times:
        raise ValueError(f"抽卡次数必须在 1-{max_times} 之间")
    return times, gacha_id


def _parse_event_stage_arguments(raw: str) -> tuple[Optional[int], bool]:
    event_id = None
    meta = False
    for part in raw.split():
        if part == "-m":
            meta = True
        elif re.fullmatch(r"[0-9]+", part) and event_id is None:
            event_id = int(part)
        else:
            raise ValueError(f"无法识别的试炼参数: {part}")
    return event_id, meta


async def _parse_event_server_arguments(
    parts: list[str],
) -> tuple[Optional[int], Optional[int]]:
    if len(parts) > 2:
        raise ValueError("参数过多，应为 [活动ID] [服务器名]")
    event_id = None
    server = None
    if parts:
        if re.fullmatch(r"[0-9]+", parts[0]):
            event_id = int(parts[0])
        else:
            server = await _resolve_server_name(parts[0])
    if len(parts) == 2:
        if event_id is None:
            raise ValueError("服务器名前只能填写活动ID")
        server = await _resolve_server_name(parts[1])
    return event_id, server


# ═══════════════════════════════════════════════════════════════════════════
# 插件类
# ═══════════════════════════════════════════════════════════════════════════

@register(
    "astrbot_plugin_tsugu",
    "QClaw",
    "BanG Dream! 游戏助手 (TsuguBangDreamBot)",
    "2.1.0",
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
        settings.timeout = max(1, int(config.get("request_timeout", 60)))
        settings.max_retries = max(0, int(config.get("max_retries", 3)))
        self._max_gacha_draws = max(1, int(config.get("max_gacha_draws", 300)))

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
        default_aliases = {
            "ycm": "车牌列表",
            "有车吗": "车牌列表",
            "车来": "车牌列表",
            "查卡牌": "查卡",
            "查卡插画": "查卡面",
            "查插画": "查卡面",
            "查询玩家": "查玩家",
            "绑定玩家": "玩家绑定",
            "解绑玩家": "解除绑定",
            "服务器模式": "主服务器",
            "切换服务器": "主服务器",
            "设置显示服务器": "显示服务器",
            "设置默认服务器": "显示服务器",
            "默认服务器": "显示服务器",
            "玩家状态列表": "绑定列表",
            "玩家列表": "绑定列表",
            "玩家信息列表": "绑定列表",
            "玩家默认ID": "选择绑定",
            "默认玩家ID": "选择绑定",
            "默认玩家": "选择绑定",
            "玩家ID": "选择绑定",
            "抽卡": "抽卡模拟",
            "单抽": "抽卡模拟",
            "十连": "抽卡模拟",
            "新手十连": "抽卡模拟",
            "查询分数表": "分数表",
            "查分数表": "分数表",
            "查询分数榜": "分数表",
            "查分数榜": "分数表",
            "查stage": "查试炼",
            "查舞台": "查试炼",
            "查festival": "查试炼",
            "查5v5": "查试炼",
            "myycx": "ycxall",
            "随机曲": "随机曲目",
            "随机": "随机曲目",
        }
        default_aliases.update(parsed_aliases)
        self._command_aliases = default_aliases
        self._wake_prefix = config.get("wake_prefix", "")
        self._filters_initialized = False

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
        if self._filters_initialized:
            return
        self._filters_initialized = True

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
            if alias_name in cmd_method_map and alias_name != original_cmd:
                logger.warning(f"命令别名 '{alias_name}' 与现有命令冲突，跳过")
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
                escaped_cmds = [
                    re.escape(name)
                    for name in sorted(all_cmds, key=lambda name: (-len(name), name))
                ]
                new_pattern = f"^(?:{'|'.join(escaped_cmds)}){suffix}"

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
    def _parse_aliases(aliases_value: object) -> dict[str, str]:
        if isinstance(aliases_value, dict):
            aliases = aliases_value
        elif isinstance(aliases_value, str):
            if not aliases_value.strip() or aliases_value.strip() == "{}":
                return {}
            try:
                aliases = json.loads(aliases_value)
            except (json.JSONDecodeError, ValueError):
                logger.warning(f"命令别名配置解析失败: {aliases_value}")
                return {}
        else:
            return {}
        if not isinstance(aliases, dict):
            return {}
        return {
            str(key).strip(): str(value).strip()
            for key, value in aliases.items()
            if str(key).strip() and str(value).strip()
        }

    # ── 通用工具方法 ──────────────────────────────────────────────

    def _user_key(self, event: AstrMessageEvent) -> str:
        return f"{event.get_platform_id()}:{event.get_sender_id()}"

    def _platform_name(self, event: AstrMessageEvent) -> str:
        """获取平台名称，用于 tsugu API
        
        注意: QQ 平台统一使用 'red'，与上游的 OneBot/NapCat 映射保持一致
        """
        platform_id = str(event.get_platform_id() or "")
        get_platform_name = getattr(event, "get_platform_name", None)
        platform_name = (
            str(get_platform_name() or "") if callable(get_platform_name) else ""
        )
        platform_hint = f"{platform_name} {platform_id}".lower()

        qq_adapters = (
            "qq",
            "aiocqhttp",
            "onebot",
            "llonebot",
            "napcat",
            "chronocat",
            "red",
        )
        if any(adapter in platform_hint for adapter in qq_adapters):
            return "red"
        if "weixin" in platform_hint or "wechat" in platform_hint:
            return "weixin"
        if "telegram" in platform_hint:
            return "telegram"
        if "discord" in platform_hint:
            return "discord"
        return platform_name or platform_id

    def _cmd_args(self, event: AstrMessageEvent) -> str:
        """获取命令参数（去掉命令名后的文本）"""
        msg = event.message_str.strip()
        parts = msg.split(None, 1)
        return parts[1] if len(parts) > 1 else ""

    def _message_without_wake_prefix(self, event: AstrMessageEvent) -> str:
        msg = (event.message_str or "").strip()
        if self._wake_prefix and msg.startswith(self._wake_prefix):
            return msg[len(self._wake_prefix):].lstrip()
        return msg

    def _avatar_url(self, event: AstrMessageEvent, platform: str) -> Optional[str]:
        """尽量复用适配器头像；QQ 适配器缺失时回退到公开头像地址。"""
        message_obj = getattr(event, "message_obj", None)
        raw_message = getattr(message_obj, "raw_message", None)

        def find_avatar(value: object, depth: int = 0) -> Optional[str]:
            if not isinstance(value, dict) or depth > 2:
                return None
            for key in ("avatarUrl", "avatar_url", "avatar"):
                avatar = value.get(key)
                if isinstance(avatar, str) and avatar.startswith(("http://", "https://")):
                    return avatar
            for key in ("sender", "user", "author", "member"):
                avatar = find_avatar(value.get(key), depth + 1)
                if avatar:
                    return avatar
            return None

        avatar = find_avatar(raw_message)
        if avatar:
            return avatar
        user_id = str(event.get_sender_id() or "")
        if platform == "red" and user_id.isdigit():
            return f"https://q1.qlogo.cn/g?b=qq&nk={user_id}&s=640"
        return None

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
            message_obj = getattr(event, "message_obj", None)
            msg_id = getattr(message_obj, "message_id", None)
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
        if not self._check_whitelist(event):
            return

        user_key = self._user_key(event)
        session = self._bind_sessions.get(user_key)
        if not session:
            return
        if time.time() > session.get("expire", 0):
            self._bind_sessions.pop(user_key, None)
            yield self._yield_plain(event, "绑定验证已超时（10分钟），请重新使用 玩家绑定 或 解除绑定 开始新的流程")
            return

        # 顺手清理其他用户的过期会话
        current_time = time.time()
        expired_keys = [
            k for k, v in self._bind_sessions.items()
            if k != user_key and current_time > v.get("expire", 0)
        ]
        for k in expired_keys:
            self._bind_sessions.pop(k, None)
        if expired_keys:
            logger.info(f"已清理 {len(expired_keys)} 个过期绑定会话")

        msg = event.message_str.strip()
        m = re.match(r"^绑定\s*(\d{5,15})$", msg)
        if not m:
            return
        player_id = int(m.group(1))
        server = session["server"]
        action = session["action"]
        if action == "unbind" and player_id != session.get("player_id"):
            yield self._yield_plain(
                event,
                f"解除绑定时必须发送原玩家ID: {session['player_id']}",
            )
            return

        platform = self._platform_name(event)
        user_id = event.get_sender_id()

        try:
            _require_success_response(
                await tsugu_api_async.bind_player_verification(
                    platform, user_id, server, player_id, action
                ),
                "验证失败",
            )
        except FailedException as e:
            message = _failed_exception_message(e, "验证失败")
            yield self._yield_plain(event, message)
            if not ("验证码" in message and "不匹配" in message):
                self._bind_sessions.pop(user_key, None)
            return
        except TsuguResponseError as e:
            yield self._yield_plain(event, f"验证出错: {e}")
            if not ("验证码" in str(e) and "不匹配" in str(e)):
                self._bind_sessions.pop(user_key, None)
            return
        except Exception as e:
            yield self._yield_plain(event, f"验证出错: {e}\n会话已保留，请稍后重试")
            return

        self._bind_sessions.pop(user_key, None)

        if action == "bind":
            try:
                await _change_user_data(platform, user_id, {"mainServer": server})
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

    @filter.regex(r"^取消绑定$")
    async def handle_cancel_bind(self, event: AstrMessageEvent):
        """取消正在进行的绑定流程"""
        if not self._check_whitelist(event):
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

    @filter.regex(r"^(?:抽卡|抽卡模拟)\b")
    async def cmd_gacha_simulate(self, event: AstrMessageEvent):
        if self._precheck(event):
            return
        raw = self._cmd_args(event)
        invoked_command = self._message_without_wake_prefix(event).split(None, 1)[0]
        try:
            times, gacha_id = _parse_gacha_arguments(
                invoked_command,
                raw,
                self._max_gacha_draws,
            )
        except ValueError as e:
            yield self._yield_plain(
                event,
                f"{e}\n用法: 抽卡模拟 [次数] [卡池ID]\n示例: 抽卡模拟 300 922",
            )
            return

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
        if len(parts) > 2:
            yield self._yield_plain(event, "参数过多，用法: 查谱面 <曲目ID> [难度]")
            return

        song_id = int(parts[0])
        difficulty_id = None
        if len(parts) > 1:
            try:
                difficulty_id = await _resolve_difficulty(parts[1])
            except ValueError as e:
                yield self._yield_plain(
                    event,
                    f"{e}\n可选: 简单/普通/困难/专家/特殊，或 easy/normal/hard/expert/special",
                )
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
                server = await _resolve_server_name(raw)
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
        try:
            event_id, meta = _parse_event_stage_arguments(raw)
        except ValueError as e:
            yield self._yield_plain(
                event,
                f"{e}\n用法: 查试炼 [活动ID] [-m]",
            )
            return

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
        try:
            event_id, server = await _parse_event_server_arguments(parts[1:])
        except ValueError as e:
            yield self._yield_plain(event, str(e))
            return

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
        try:
            event_id, server = await _parse_event_server_arguments(parts)
        except ValueError as e:
            yield self._yield_plain(event, str(e))
            return

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
        try:
            event_id, server = await _parse_event_server_arguments(parts[1:])
        except ValueError as e:
            yield self._yield_plain(event, str(e))
            return

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
            station_response = await tsugu_api_async.station_query_all_room()
            rooms = _require_success_response(station_response, "获取车牌失败")
            if not isinstance(rooms, list):
                raise TsuguResponseError("获取车牌失败: 响应格式无效")
            if any(not isinstance(room, dict) for room in rooms):
                raise TsuguResponseError("获取车牌失败: 房间数据格式无效")
            
            # 关键词过滤 (从原版移植)
            if keyword and rooms:
                rooms = [r for r in rooms if keyword in r.get("rawMessage", "")]
                if not rooms:
                    yield self._yield_plain(event, f"没有找到包含 {keyword} 的房间")
                    return
            if not rooms:
                if os.path.exists(self._no_car_image_path):
                    yield self._yield_result(
                        event,
                        [Image.fromFileSystem(self._no_car_image_path)],
                    )
                else:
                    yield self._yield_plain(event, "当前没有车牌")
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
            yield self._yield_plain(event, _failed_exception_message(e, "查询失败"))
        except Exception as e:
            yield self._yield_plain(event, f"查询出错: {e}")

    @filter.regex(r"^开启车牌转发\b")
    async def cmd_share_room_on(self, event: AstrMessageEvent):
        if self._precheck(event):
            return
        
        platform = self._platform_name(event)
        user_id = event.get_sender_id()
        
        try:
            await _change_user_data(platform, user_id, {"shareRoomNumber": True})
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
            await _change_user_data(platform, user_id, {"shareRoomNumber": False})
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
        if len(parts) > 2:
            yield self._yield_plain(event, "参数过多，用法: 查玩家 <玩家ID> [服务器名]")
            return

        player_id = int(parts[0])
        server = None
        if len(parts) > 1:
            try:
                server = await _resolve_server_name(parts[1])
            except ValueError as e:
                yield self._yield_plain(event, str(e))
                return

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
                server = await _resolve_server_name(raw)
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
            verify_code = await _request_bind_code(platform, user_id)
        except FailedException as e:
            yield self._yield_plain(event, _failed_exception_message(e, "绑定请求失败"))
            return
        except Exception as e:
            yield self._yield_plain(event, f"绑定请求出错: {e}")
            return

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
                server = await _resolve_server_name(raw)
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
            verify_code = await _request_bind_code(platform, user_id)
        except FailedException as e:
            yield self._yield_plain(event, _failed_exception_message(e, "请求失败"))
            return
        except Exception as e:
            yield self._yield_plain(event, f"请求出错: {e}")
            return

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

    async def _player_info_result(
        self,
        event: AstrMessageEvent,
        server: Optional[int] = None,
        index: Optional[int] = None,
    ):
        platform = self._platform_name(event)
        user_id = event.get_sender_id()

        try:
            tsugu_user = await _get_tsugu_user(platform, user_id)
        except Exception as e:
            return self._yield_plain(event, str(e))

        player_list = tsugu_user["userPlayerList"]
        if not player_list:
            return self._yield_plain(event, "未绑定任何玩家，请先使用 玩家绑定")

        try:
            player = _get_user_player(tsugu_user, server, index)
        except Exception as e:
            return self._yield_plain(event, str(e))

        try:
            response = await tsugu_api_async.search_player(player["playerId"], player["server"])
            chain = response_to_chain(response)
            if chain:
                return self._yield_result(event, chain)
            return self._yield_plain(event, "查询玩家信息失败")
        except FailedException as e:
            return self._yield_plain(event, _failed_exception_message(e, "查询失败"))
        except Exception as e:
            return self._yield_plain(event, f"查询出错: {e}")

    @filter.regex(r"^玩家状态(?:\s*(\d+))?(?:\s|$)")
    async def cmd_player_info(self, event: AstrMessageEvent, player_index: str = ""):
        if self._precheck(event):
            return

        raw = self._cmd_args(event).strip()
        server = None
        index = None
        if player_index and player_index.isdigit():
            index = int(player_index) - 1
        elif raw:
            if raw.isdigit():
                index = int(raw) - 1
            else:
                try:
                    server = await _resolve_server_name(raw)
                except ValueError as e:
                    yield self._yield_plain(event, str(e))
                    return

        yield await self._player_info_result(event, server=server, index=index)

    @filter.regex(r"^.+服玩家状态$")
    async def shortcut_player_info(self, event: AstrMessageEvent):
        if self._precheck(event):
            return
        server_name = self._message_without_wake_prefix(event).removesuffix("玩家状态")
        try:
            server = await _resolve_server_name(server_name)
        except ValueError as e:
            yield self._yield_plain(event, str(e))
            return
        yield await self._player_info_result(event, server=server)

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

    async def _switch_main_server_result(
        self,
        event: AstrMessageEvent,
        server: int,
    ):
        platform = self._platform_name(event)
        user_id = event.get_sender_id()
        try:
            await _change_user_data(platform, user_id, {"mainServer": server})
            return self._yield_plain(event, f"已切换到{server_id_to_full_name(server)}模式")
        except Exception as e:
            return self._yield_plain(event, f"切换出错: {e}")

    @filter.regex(r"^主服务器\b")
    async def cmd_switch_main_server(self, event: AstrMessageEvent):
        if self._precheck(event):
            return
        raw = self._cmd_args(event)
        if not raw:
            yield self._yield_plain(event, "用法: 主服务器 <服务器名>\n可选: 日服/国际服/台服/国服/韩服 (或 jp/en/tw/cn/kr)")
            return

        try:
            server = await _resolve_server_name(raw)
        except ValueError as e:
            yield self._yield_plain(event, str(e))
            return
        yield await self._switch_main_server_result(event, server)

    @filter.regex(r"^.+服模式$")
    async def shortcut_switch_main_server(self, event: AstrMessageEvent):
        if self._precheck(event):
            return
        server_name = self._message_without_wake_prefix(event).removesuffix("模式")
        try:
            server = await _resolve_server_name(server_name)
        except ValueError as e:
            yield self._yield_plain(event, str(e))
            return
        yield await self._switch_main_server_result(event, server)

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
                sid = await _resolve_server_name(part)
            except ValueError as e:
                yield self._yield_plain(event, str(e))
                return
            if sid in server_list:
                yield self._yield_plain(event, f"指定了重复的服务器: {part}")
                return
            server_list.append(sid)

        if not server_list:
            yield self._yield_plain(event, "请至少指定一个服务器")
            return

        platform = self._platform_name(event)
        user_id = event.get_sender_id()

        try:
            await _change_user_data(platform, user_id, {"displayedServerList": server_list})
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
            await _change_user_data(platform, user_id, {"userPlayerIndex": index})
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

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def handle_room_number(self, event: AstrMessageEvent):
        """被动识别车牌消息并静默提交到公共频道。
        
        逻辑 (从原版移植):
        1. checkLeftDigits 检测左侧 5-6 位数字
        2. 检查消息是否包含 car 关键词且不含 fake 关键词
        3. 检查用户是否开启车牌转发
        4. 使用毫秒时间戳提交到 Tsugu 车站
        """
        # 被动转发不应依赖命令的 @/唤醒词，只遵守插件白名单。
        if not self._check_whitelist(event):
            return
        
        msg = (event.message_str or "").strip()
        room_number = match_room_number(
            msg,
            self._car_keywords,
            self._fake_keywords,
        )
        if room_number == 0:
            return
        
        platform = self._platform_name(event)
        user_id = str(event.get_sender_id())
        
        try:
            tsugu_user = await _get_tsugu_user(platform, user_id)
            if not tsugu_user.get("shareRoomNumber", True):
                return
        except Exception as e:
            logger.debug(f"读取车牌转发设置失败 ({platform}:{user_id}): {e}")
            return
        
        try:
            sender_name = event.get_sender_name() or user_id
            response = await _submit_room_number(
                room_number,
                msg,
                platform,
                user_id,
                sender_name,
                avatar_url=self._avatar_url(event, platform),
                bandori_station_token=self._bandori_station_token,
            )
            if response.get("status") == "success":
                logger.info(f"车牌 {room_number} 已静默提交到公共频道")
            else:
                logger.warning(
                    f"车牌 {room_number} 提交失败: "
                    f"{response.get('data', '未知错误')}"
                )
        except FailedException as e:
            logger.warning(
                f"车牌 {room_number} 提交失败: "
                f"{_failed_exception_message(e, '未知错误')}"
            )
        except Exception as e:
            logger.warning(f"车牌 {room_number} 提交出错: {e}")
