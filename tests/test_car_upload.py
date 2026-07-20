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
    ):
        self.message_str = message
        self.is_at_or_wake_command = False
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
                "station-token",
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
            None,
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


if __name__ == "__main__":
    unittest.main()
