"""The tracker menu uses Telegram's persistent reply keyboard."""

import unittest
from types import SimpleNamespace

from aiogram.types import ReplyKeyboardMarkup

from handlers.command_tracker import Exact, tracker_kb


class TrackerReplyKeyboardTests(unittest.IsolatedAsyncioTestCase):
    async def test_my_tasks_button_is_a_reply_message(self):
        keyboard = tracker_kb()
        self.assertIsInstance(keyboard, ReplyKeyboardMarkup)
        self.assertTrue(keyboard.is_persistent)
        self.assertEqual(keyboard.keyboard[0][0].text, "✅ Мои задачи")
        self.assertEqual(keyboard.keyboard[1][0].text, "📋 Открыть трекер")
        self.assertIsNotNone(keyboard.keyboard[1][0].web_app)
        self.assertTrue(await Exact("✅ Мои задачи")(SimpleNamespace(text="✅ Мои задачи")))
