from __future__ import annotations

import importlib.util
import json
import sys
import threading
import time
import types
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import AsyncMock, patch


REPO_ROOT = Path(__file__).resolve().parents[1]


class _Logger:
    def __init__(self):
        self.messages = []

    def _record(self, level, message):
        self.messages.append((level, str(message)))

    def debug(self, message):
        self._record("debug", message)

    def info(self, message):
        self._record("info", message)

    def warning(self, message):
        self._record("warning", message)

    def error(self, message):
        self._record("error", message)


class _Filter:
    EventMessageType = types.SimpleNamespace(ALL=object())

    @staticmethod
    def _decorator(*_args, **_kwargs):
        def decorate(function):
            return function

        return decorate

    regex = _decorator
    event_message_type = _decorator


class _Star:
    def __init__(self, context):
        self.context = context


class _Component:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs


class _Image(_Component):
    @classmethod
    def fromBase64(cls, content):
        return cls(content)

    @classmethod
    def fromFileSystem(cls, path):
        return cls(path)


def _register(*_args, **_kwargs):
    def decorate(cls):
        return cls

    return decorate


def _install_astrbot_stubs():
    logger = _Logger()
    modules = {
        "astrbot": types.ModuleType("astrbot"),
        "astrbot.api": types.ModuleType("astrbot.api"),
        "astrbot.api.event": types.ModuleType("astrbot.api.event"),
        "astrbot.api.star": types.ModuleType("astrbot.api.star"),
        "astrbot.api.message_components": types.ModuleType(
            "astrbot.api.message_components"
        ),
        "astrbot.core": types.ModuleType("astrbot.core"),
        "astrbot.core.config": types.ModuleType("astrbot.core.config"),
        "astrbot.core.config.astrbot_config": types.ModuleType(
            "astrbot.core.config.astrbot_config"
        ),
        "astrbot.core.message": types.ModuleType("astrbot.core.message"),
        "astrbot.core.message.components": types.ModuleType(
            "astrbot.core.message.components"
        ),
        "astrbot.core.star": types.ModuleType("astrbot.core.star"),
        "astrbot.core.star.star_handler": types.ModuleType(
            "astrbot.core.star.star_handler"
        ),
    }

    modules["astrbot.api"].logger = logger
    modules["astrbot.api.event"].filter = _Filter
    modules["astrbot.api.event"].AstrMessageEvent = object
    modules["astrbot.api.star"].Context = object
    modules["astrbot.api.star"].Star = _Star
    modules["astrbot.api.star"].register = _register
    modules["astrbot.api.message_components"].Image = _Image
    modules["astrbot.api.message_components"].Plain = _Component
    modules["astrbot.core.config.astrbot_config"].AstrBotConfig = dict
    modules["astrbot.core.message.components"].At = _Component
    modules["astrbot.core.message.components"].Reply = _Component
    modules["astrbot.core.star.star_handler"].star_handlers_registry = []
    sys.modules.update(modules)
    return logger


LOGGER = _install_astrbot_stubs()
SPEC = importlib.util.spec_from_file_location("plugin_main", REPO_ROOT / "main.py")
PLUGIN = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(PLUGIN)


class _Event:
    def __init__(
        self,
        message,
        *,
        platform_id="napcat-main",
        platform_name="aiocqhttp",
        sender_id="10001",
        sender_name="测试用户",
        group_id="20001",
        raw_message=None,
    ):
        self.message_str = message
        self.is_at_or_wake_command = False
        self.message_obj = types.SimpleNamespace(
            message_id="message-1",
            raw_message=raw_message,
        )
        self.results = []
        self._platform_id = platform_id
        self._platform_name = platform_name
        self._sender_id = sender_id
        self._sender_name = sender_name
        self._group_id = group_id

    def get_platform_id(self):
        return self._platform_id

    def get_platform_name(self):
        return self._platform_name

    def get_sender_id(self):
        return self._sender_id

    def get_sender_name(self):
        return self._sender_name

    def get_group_id(self):
        return self._group_id

    def chain_result(self, chain):
        self.results.append(chain)
        return chain


async def _collect(async_generator):
    return [result async for result in async_generator]


class RoomRecognitionTests(unittest.TestCase):
    def test_accepts_real_five_and_six_digit_rooms(self):
        self.assertEqual(
            PLUGIN.match_room_number("123456 q1", {"q1"}, {"114514"}),
            123456,
        )
        self.assertEqual(
            PLUGIN.match_room_number("12345 缺1", {"缺1"}, {"114514"}),
            12345,
        )

    def test_rejects_invalid_digits_fake_rooms_and_missing_keywords(self):
        cases = (
            "1234567 q1",
            "１２３４５６ q1",
            "114514 q1",
            "123456 随便看看",
        )
        for message in cases:
            with self.subTest(message=message):
                self.assertEqual(
                    PLUGIN.match_room_number(
                        message,
                        {"q1"},
                        {"114514"},
                    ),
                    0,
                )


class RoomSubmissionPayloadTests(unittest.IsolatedAsyncioTestCase):
    async def test_uses_millisecond_timestamp_and_complete_contract(self):
        captured = {}

        class FakeResponse:
            def json(self):
                return {"status": "success", "data": "提交成功"}

        class FakeApi:
            def __init__(self, host, endpoint, proxy):
                captured.update(host=host, endpoint=endpoint, proxy=proxy)

            async def apost(self, data):
                captured["data"] = data
                return FakeResponse()

        before = int(time.time() * 1000)
        with patch.object(PLUGIN, "Api", FakeApi):
            result = await PLUGIN._submit_room_number(
                123456,
                "123456 q1",
                "red",
                "10001",
                "测试用户",
                avatar_url="https://example.com/avatar.png",
                bandori_station_token="station-token",
            )
        after = int(time.time() * 1000)

        self.assertEqual(result["status"], "success")
        self.assertEqual(captured["endpoint"], "/station/submitRoomNumber")
        self.assertEqual(
            captured["data"],
            {
                "number": 123456,
                "rawMessage": "123456 q1",
                "platform": "red",
                "userId": "10001",
                "userName": "测试用户",
                "time": captured["data"]["time"],
                "avatarUrl": "https://example.com/avatar.png",
                "bandoriStationToken": "station-token",
            },
        )
        self.assertGreaterEqual(captured["data"]["time"], before)
        self.assertLessEqual(captured["data"]["time"], after)
        self.assertGreaterEqual(captured["data"]["time"], 1_000_000_000_000)

    async def test_posts_contract_through_real_tsugu_network_layer(self):
        captured = {}

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers["Content-Length"])
                captured["path"] = self.path
                captured["data"] = json.loads(self.rfile.read(length))
                body = json.dumps(
                    {"status": "success", "data": "提交成功"}
                ).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, _format, *_args):
                return

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        original_url = PLUGIN.settings.userdata_backend_url
        original_proxy = PLUGIN.settings.userdata_backend_proxy
        PLUGIN.settings.userdata_backend_url = (
            f"http://127.0.0.1:{server.server_port}"
        )
        PLUGIN.settings.userdata_backend_proxy = False

        try:
            result = await PLUGIN._submit_room_number(
                654321,
                "654321 缺1",
                "red",
                "10002",
                "网络测试",
            )
        finally:
            PLUGIN.settings.userdata_backend_url = original_url
            PLUGIN.settings.userdata_backend_proxy = original_proxy
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

        self.assertEqual(result["status"], "success")
        self.assertEqual(captured["path"], "/station/submitRoomNumber")
        self.assertEqual(captured["data"]["number"], 654321)
        self.assertEqual(captured["data"]["platform"], "red")
        self.assertGreaterEqual(captured["data"]["time"], 1_000_000_000_000)


class PassiveRoomHandlerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        LOGGER.messages.clear()
        self.plugin = PLUGIN.TsuguPlugin(object(), {})

    async def test_plain_unwoken_message_is_submitted(self):
        event = _Event("123456 q1")
        get_user = AsyncMock(return_value={"data": {}, "shareRoomNumber": True})
        submit = AsyncMock(return_value={"status": "success", "data": "提交成功"})

        with (
            patch.object(PLUGIN, "_get_tsugu_user", get_user),
            patch.object(PLUGIN, "_submit_room_number", submit),
        ):
            await self.plugin.handle_room_number(event)

        get_user.assert_awaited_once_with("red", "10001")
        submit.assert_awaited_once_with(
            123456,
            "123456 q1",
            "red",
            "10001",
            "测试用户",
            avatar_url="https://q1.qlogo.cn/g?b=qq&nk=10001&s=640",
            bandori_station_token=None,
        )

    async def test_missing_share_setting_uses_upstream_enabled_default(self):
        event = _Event("12345 缺1")
        submit = AsyncMock(return_value={"status": "success"})

        with (
            patch.object(
                PLUGIN,
                "_get_tsugu_user",
                AsyncMock(return_value={"data": {}}),
            ),
            patch.object(PLUGIN, "_submit_room_number", submit),
        ):
            await self.plugin.handle_room_number(event)

        submit.assert_awaited_once()

    async def test_disabled_share_setting_does_not_submit(self):
        event = _Event("123456 q1")
        submit = AsyncMock()

        with (
            patch.object(
                PLUGIN,
                "_get_tsugu_user",
                AsyncMock(return_value={"shareRoomNumber": False}),
            ),
            patch.object(PLUGIN, "_submit_room_number", submit),
        ):
            await self.plugin.handle_room_number(event)

        submit.assert_not_awaited()

    def test_platform_mapping_supports_current_qq_adapters(self):
        adapters = (
            ("napcat-main", "aiocqhttp"),
            ("llonebot-main", "llonebot"),
            ("chronocat-main", "chronocat"),
            ("qq-official", "qq_official_webhook"),
        )
        for platform_id, platform_name in adapters:
            with self.subTest(platform_name=platform_name):
                event = _Event(
                    "",
                    platform_id=platform_id,
                    platform_name=platform_name,
                )
                self.assertEqual(self.plugin._platform_name(event), "red")

    def test_prefers_adapter_avatar_over_qq_fallback(self):
        event = _Event(
            "",
            raw_message={
                "sender": {"avatar": "https://example.com/adapter-avatar.png"}
            },
        )
        self.assertEqual(
            self.plugin._avatar_url(event, "red"),
            "https://example.com/adapter-avatar.png",
        )


class ArgumentCompatibilityTests(unittest.IsolatedAsyncioTestCase):
    def test_gacha_arguments_follow_upstream_positional_contract(self):
        self.assertEqual(
            PLUGIN._parse_gacha_arguments("抽卡模拟", "300 922", 300),
            (300, 922),
        )
        self.assertEqual(
            PLUGIN._parse_gacha_arguments("抽卡模拟", "", 300),
            (10, None),
        )
        self.assertEqual(
            PLUGIN._parse_gacha_arguments("单抽", "922", 300),
            (1, 922),
        )
        with self.assertRaisesRegex(ValueError, "1-300"):
            PLUGIN._parse_gacha_arguments("抽卡模拟", "301", 300)

    def test_event_stage_rejects_unknown_or_duplicate_parameters(self):
        self.assertEqual(
            PLUGIN._parse_event_stage_arguments("157 -m"),
            (157, True),
        )
        with self.assertRaisesRegex(ValueError, "无法识别"):
            PLUGIN._parse_event_stage_arguments("157 158")

    async def test_server_and_event_parser_supports_fuzzy_response_shape(self):
        fuzzy = AsyncMock(
            return_value={"status": "success", "data": {"server": [4]}}
        )
        with patch.object(PLUGIN.tsugu_api_async, "fuzzy_search", fuzzy):
            self.assertEqual(await PLUGIN._resolve_server_name("韩区"), 4)
            self.assertEqual(
                await PLUGIN._parse_event_server_arguments(["177", "韩区"]),
                (177, 4),
            )

    async def test_difficulty_supports_chinese_and_fuzzy_names(self):
        self.assertEqual(await PLUGIN._resolve_difficulty("专家"), 3)
        fuzzy = AsyncMock(
            return_value={"status": "success", "data": {"difficulty": [4]}}
        )
        with patch.object(PLUGIN.tsugu_api_async, "fuzzy_search", fuzzy):
            self.assertEqual(await PLUGIN._resolve_difficulty("sp难度"), 4)


class UserDataCompatibilityTests(unittest.IsolatedAsyncioTestCase):
    async def test_normalizes_legacy_or_malformed_user_data(self):
        get_user = AsyncMock(
            return_value={
                "status": "success",
                "data": {
                    "mainServer": "99",
                    "displayedServerList": ["3", 3, "bad", 0],
                    "userPlayerIndex": 9,
                    "userPlayerList": [
                        {"playerId": "12345678", "server": "3"},
                        {"playerId": "bad", "server": 0},
                    ],
                },
            }
        )
        with patch.object(PLUGIN.tsugu_api_async, "get_user_data", get_user):
            user = await PLUGIN._get_tsugu_user("red", "10001")

        self.assertEqual(user["mainServer"], 3)
        self.assertEqual(user["displayedServerList"], [3, 0])
        self.assertEqual(user["userPlayerIndex"], 0)
        self.assertEqual(
            user["userPlayerList"],
            [{"playerId": 12345678, "server": 3}],
        )
        self.assertTrue(user["shareRoomNumber"])

    async def test_rejects_business_failure_and_malformed_bind_code(self):
        with patch.object(
            PLUGIN.tsugu_api_async,
            "get_user_data",
            AsyncMock(return_value={"status": "failed", "data": "数据库不可用"}),
        ):
            with self.assertRaisesRegex(PLUGIN.TsuguResponseError, "数据库不可用"):
                await PLUGIN._get_tsugu_user("red", "10001")

        with patch.object(
            PLUGIN.tsugu_api_async,
            "bind_player_request",
            AsyncMock(return_value={"status": "success", "data": {}}),
        ):
            with self.assertRaisesRegex(PLUGIN.TsuguResponseError, "格式无效"):
                await PLUGIN._request_bind_code("red", "10001")

    def test_out_of_range_saved_player_index_falls_back_safely(self):
        user = {
            "mainServer": 3,
            "userPlayerIndex": 99,
            "userPlayerList": [{"playerId": 12345678, "server": 3}],
        }
        self.assertEqual(
            PLUGIN._get_user_player(user),
            {"playerId": 12345678, "server": 3},
        )


class CommandBehaviorTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        LOGGER.messages.clear()
        self.plugin = PLUGIN.TsuguPlugin(
            object(),
            {"at_wake_enabled": False},
        )

    async def test_empty_room_list_does_not_call_backend_renderer(self):
        event = _Event("车牌列表")
        room_list = AsyncMock()
        with (
            patch.object(
                PLUGIN.tsugu_api_async,
                "station_query_all_room",
                AsyncMock(return_value={"status": "success", "data": []}),
            ),
            patch.object(PLUGIN.tsugu_api_async, "room_list", room_list),
        ):
            results = await _collect(self.plugin.cmd_room_list(event))

        room_list.assert_not_awaited()
        self.assertEqual(len(results), 1)

    async def test_bind_followup_works_without_wake_and_unbind_checks_id(self):
        plugin = PLUGIN.TsuguPlugin(object(), {"at_wake_enabled": True})
        event = _Event("绑定 12345678")
        user_key = plugin._user_key(event)
        plugin._bind_sessions[user_key] = {
            "verify_code": "12345",
            "server": 3,
            "action": "unbind",
            "player_id": 87654321,
            "expire": time.time() + 600,
        }
        verification = AsyncMock()
        with patch.object(
            PLUGIN.tsugu_api_async,
            "bind_player_verification",
            verification,
        ):
            results = await _collect(plugin.handle_bind_verify(event))
            verification.assert_not_awaited()
            self.assertIn(user_key, plugin._bind_sessions)
            self.assertIn("87654321", results[0][0].args[0])

            event.message_str = "绑定 87654321"
            verification.return_value = {"status": "success", "data": "ok"}
            results = await _collect(plugin.handle_bind_verify(event))
            verification.assert_awaited_once_with(
                "red",
                "10001",
                3,
                87654321,
                "unbind",
            )
            self.assertNotIn(user_key, plugin._bind_sessions)
            self.assertIn("解除绑定成功", results[0][0].args[0])

    async def test_duplicate_display_servers_are_rejected(self):
        event = _Event("显示服务器 国服 cn")
        change_user = AsyncMock()
        with patch.object(PLUGIN, "_change_user_data", change_user):
            results = await _collect(self.plugin.cmd_displayed_servers(event))

        change_user.assert_not_awaited()
        self.assertIn("重复", results[0][0].args[0])

    async def test_upstream_mode_shortcut_updates_main_server(self):
        event = _Event("日本服模式")
        change_user = AsyncMock()
        with patch.object(PLUGIN, "_change_user_data", change_user):
            results = await _collect(
                self.plugin.shortcut_switch_main_server(event)
            )

        change_user.assert_awaited_once_with("red", "10001", {"mainServer": 0})
        self.assertIn("日服模式", results[0][0].args[0])

    async def test_expired_and_network_failed_binding_sessions_are_safe(self):
        plugin = PLUGIN.TsuguPlugin(object(), {"at_wake_enabled": True})
        event = _Event("绑定 12345678")
        user_key = plugin._user_key(event)
        plugin._bind_sessions[user_key] = {
            "verify_code": "12345",
            "server": 3,
            "action": "bind",
            "expire": time.time() - 1,
        }
        results = await _collect(plugin.handle_bind_verify(event))
        self.assertNotIn(user_key, plugin._bind_sessions)
        self.assertIn("超时", results[0][0].args[0])

        plugin._bind_sessions[user_key] = {
            "verify_code": "12345",
            "server": 3,
            "action": "bind",
            "expire": time.time() + 600,
        }
        with patch.object(
            PLUGIN.tsugu_api_async,
            "bind_player_verification",
            AsyncMock(side_effect=TimeoutError("temporary")),
        ):
            results = await _collect(plugin.handle_bind_verify(event))

        self.assertIn(user_key, plugin._bind_sessions)
        self.assertIn("会话已保留", results[0][0].args[0])


class AliasInitializationTests(unittest.IsolatedAsyncioTestCase):
    async def test_defaults_merge_custom_alias_and_escape_regex(self):
        regex_filter = types.SimpleNamespace(
            regex_str=r"^查曲\b",
            regex=None,
        )
        handler = types.SimpleNamespace(
            handler_module_path="data.plugins.astrbot_plugin_tsugu.main",
            handler_name="cmd_search_song",
            event_filters=[regex_filter],
        )
        PLUGIN.star_handlers_registry.append(handler)
        try:
            plugin = PLUGIN.TsuguPlugin(
                object(),
                {
                    "command_aliases": json.dumps(
                        {
                            "": "查曲",
                            "查曲": "查卡",
                            "搜(歌)": "查曲",
                        },
                        ensure_ascii=False,
                    )
                },
            )
            await plugin.initialize()
            first_pattern = regex_filter.regex_str
            await plugin.initialize()
        finally:
            PLUGIN.star_handlers_registry.remove(handler)

        self.assertIn("绑定玩家", plugin._command_aliases)
        self.assertIn("随机曲", plugin._command_aliases)
        self.assertIn(r"搜\(歌\)", first_pattern)
        self.assertNotIn("(?:|", first_pattern)
        self.assertEqual(regex_filter.regex_str, first_pattern)
        self.assertIsNotNone(regex_filter.regex)


class QueryCommandContractTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.plugin = PLUGIN.TsuguPlugin(
            object(),
            {"at_wake_enabled": False},
        )
        self.user = {
            "mainServer": 3,
            "displayedServerList": [3, 0],
            "shareRoomNumber": True,
            "userPlayerIndex": 0,
            "userPlayerList": [
                {"playerId": 12345678, "server": 3},
                {"playerId": 87654321, "server": 0},
            ],
        }

    async def test_all_query_commands_call_sdk_with_expected_contract(self):
        cases = (
            (
                "cmd_search_song",
                "查曲 ag lv27",
                "search_song",
                ([3, 0],),
                {"text": "ag lv27"},
            ),
            (
                "cmd_search_card",
                "查卡 1399",
                "search_card",
                ([3, 0],),
                {"text": "1399"},
            ),
            (
                "cmd_card_illustration",
                "查卡面 1399",
                "get_card_illustration",
                (1399,),
                {},
            ),
            (
                "cmd_search_character",
                "查角色 10",
                "search_character",
                ([3, 0],),
                {"text": "10"},
            ),
            (
                "cmd_search_event",
                "查活动 177",
                "search_event",
                ([3, 0],),
                {"text": "177"},
            ),
            (
                "cmd_search_gacha",
                "查卡池 922",
                "search_gacha",
                ([3, 0], 922),
                {},
            ),
            (
                "cmd_gacha_simulate",
                "抽卡模拟 300 922",
                "gacha_simulate",
                (3,),
                {"times": 300, "gacha_id": 922},
            ),
            (
                "cmd_song_chart",
                "查谱面 1 专家",
                "song_chart",
                ([3, 0], 1, 3),
                {},
            ),
            (
                "cmd_song_meta",
                "分数表 日服",
                "song_meta",
                ([3, 0], 0),
                {},
            ),
            (
                "cmd_event_stage",
                "查试炼 157 -m",
                "event_stage",
                (3,),
                {"event_id": 157, "meta": True},
            ),
            (
                "cmd_ycx",
                "ycx 1000 177 jp",
                "cutoff_detail",
                (0, 1000),
                {"event_id": 177},
            ),
            (
                "cmd_ycxall",
                "ycxall 177 jp",
                "cutoff_all",
                (0,),
                {"event_id": 177},
            ),
            (
                "cmd_lsycx",
                "lsycx 1000 177 jp",
                "cutoff_list_of_recent_event",
                (0, 1000),
                {"event_id": 177},
            ),
            (
                "cmd_search_player",
                "查玩家 40474621 jp",
                "search_player",
                (40474621, 0),
                {},
            ),
            (
                "cmd_player_info",
                "玩家状态 2",
                "search_player",
                (87654321, 0),
                {},
            ),
            (
                "cmd_random_song",
                "随机曲目 lv24 ag",
                "song_random",
                (3,),
                {"text": "lv24 ag"},
            ),
        )

        for handler_name, message, api_name, args, kwargs in cases:
            with self.subTest(handler=handler_name):
                event = _Event(message)
                api_mock = AsyncMock(
                    return_value=[{"type": "string", "string": "ok"}]
                )
                with (
                    patch.object(
                        PLUGIN,
                        "_get_tsugu_user",
                        AsyncMock(return_value=self.user),
                    ),
                    patch.object(PLUGIN.tsugu_api_async, api_name, api_mock),
                ):
                    results = await _collect(
                        getattr(self.plugin, handler_name)(event)
                    )

                api_mock.assert_awaited_once_with(*args, **kwargs)
                self.assertEqual(len(results), 1)

    def test_complete_active_command_surface_is_present(self):
        handlers = {
            "cmd_share_room_on",
            "cmd_share_room_off",
            "cmd_player_bind",
            "cmd_player_unbind",
            "cmd_switch_main_server",
            "shortcut_switch_main_server",
            "cmd_displayed_servers",
            "cmd_player_info",
            "shortcut_player_info",
            "cmd_player_list",
            "cmd_switch_player",
            "cmd_room_list",
            "cmd_search_player",
            "cmd_search_card",
            "cmd_card_illustration",
            "cmd_search_character",
            "cmd_search_event",
            "cmd_search_song",
            "cmd_song_chart",
            "cmd_random_song",
            "cmd_song_meta",
            "cmd_event_stage",
            "cmd_search_gacha",
            "cmd_ycx",
            "cmd_ycxall",
            "cmd_lsycx",
            "cmd_gacha_simulate",
            "handle_bind_verify",
            "handle_cancel_bind",
            "handle_room_number",
        }
        for handler in handlers:
            with self.subTest(handler=handler):
                self.assertTrue(callable(getattr(self.plugin, handler, None)))


if __name__ == "__main__":
    unittest.main()
