"""Bot API widget payload limits and safe leaderboard rendering."""

import unittest
import zlib
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from aiogram.exceptions import TelegramBadRequest

from handlers.command_meter import valyny_cmd
from utils.valyny_image import render_valyny_image
from utils.valyny_widget import SendWidget, render_valyny_widget, valyny_caption


class ValynyWidgetTests(unittest.TestCase):
    def test_renders_all_people_in_ten_person_pages_without_interpreting_names_as_html(self):
        rows = [("<script>alert(1)</script> & ИК", 123)] + [
            (f"Участник {i}", i) for i in range(2, 34)
        ]
        source = render_valyny_widget(rows, "12.11.2026")

        self.assertIn("&lt;script&gt;", source)
        self.assertNotIn("<script>alert", source)
        self.assertIn("12.11.2026", source)
        self.assertIn("Участник 10", source)
        self.assertIn("Участник 33", source)
        self.assertEqual(source.count('class="page active"'), 1)
        self.assertEqual(source.count('class="page"'), 3)
        self.assertIn('id="next"', source)
        self.assertIn('1 / 4', source)
        self.assertLessEqual(len(source.encode("utf-8")), 32_768)
        self.assertLessEqual(len(zlib.compress(source.encode("utf-8"), 9)), 4_096)

    def test_fallback_caption_is_plain_text_and_within_limit(self):
        rows = [("А" * 300, 100) for _ in range(10)]
        caption = valyny_caption(rows)
        self.assertLessEqual(len(caption.encode("utf-8")), 1_024)
        self.assertEqual(caption.count("СМ"), 10)

    def test_send_widget_uses_bot_api_method(self):
        method = SendWidget(chat_id=-100123, html="<b>ИК</b>", width=360, caption="Топ")
        self.assertEqual(method.__api_method__, "sendWidget")
        self.assertEqual(method.width, 360)
        self.assertEqual(method.caption, "Топ")

    def test_image_fallback_is_a_png(self):
        image = render_valyny_image([("Участник ИК", 27)], "12.11.2026")
        self.assertTrue(image.startswith(b"\x89PNG\r\n\x1a\n"))
        self.assertLess(len(image), 10_000_000)


class ValynyCommandTests(unittest.IsolatedAsyncioTestCase):
    async def _run_command(self, bot_side_effect=None, photo_side_effect=None):
        @asynccontextmanager
        async def session():
            yield object()

        message = SimpleNamespace(
            bot=AsyncMock(side_effect=bot_side_effect),
            answer=AsyncMock(),
            answer_photo=AsyncMock(side_effect=photo_side_effect),
            reply=AsyncMock(),
            chat=SimpleNamespace(id=-100123),
            message_thread_id=42,
        )
        dao = SimpleNamespace(top=AsyncMock(return_value=[
            SimpleNamespace(display="<ИК>", size=37),
        ]))
        with patch("handlers.command_meter.async_session_maker", session), patch(
            "handlers.command_meter.MeterDAO", return_value=dao
        ):
            await valyny_cmd(message)
        return message, dao

    async def test_sends_widget_in_the_command_topic(self):
        message, dao = await self._run_command()
        dao.top.assert_awaited_once_with(limit=None)
        method = message.bot.await_args.args[0]
        self.assertIsInstance(method, SendWidget)
        self.assertEqual(method.chat_id, -100123)
        self.assertEqual(method.message_thread_id, 42)
        self.assertIn("&lt;ИК&gt;", method.html)
        message.answer_photo.assert_not_awaited()
        message.answer.assert_not_awaited()

    async def test_sends_image_when_widget_method_is_unavailable(self):
        error = TelegramBadRequest(
            method=SendWidget(chat_id=-100123, html="test"), message="Not Found"
        )
        message, _ = await self._run_command(bot_side_effect=error)
        self.assertEqual(message.answer_photo.await_count, 1)
        message.answer.assert_not_awaited()

    async def test_sends_text_if_image_is_also_unavailable(self):
        error = TelegramBadRequest(
            method=SendWidget(chat_id=-100123, html="test"), message="Not Found"
        )
        message, _ = await self._run_command(bot_side_effect=error, photo_side_effect=OSError("no image"))
        self.assertIn("<ИК>", message.answer.await_args.args[0])
        self.assertEqual(message.answer.await_args.kwargs["parse_mode"], None)


if __name__ == "__main__":
    unittest.main()
