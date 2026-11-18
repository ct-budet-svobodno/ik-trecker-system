import asyncio
import hashlib
import hmac
import io
import json
import os
import unittest
import urllib.error
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from handlers.command_tracker_poll import answer_poll, submit_vote


class TrackerPollTests(unittest.TestCase):
    def test_signed_request(self):
        response = io.BytesIO(json.dumps({'choice': 'Приду'}).encode())
        with patch.dict(os.environ, {'TRACKER_API_URL': 'http://tracker:8000'}), \
             patch('handlers.command_tracker_poll.urllib.request.urlopen', return_value=response) as send:
            self.assertEqual(submit_vote('secret', 42, 7, 1), 'Ваш выбор: Приду')
        request = send.call_args.args[0]
        self.assertEqual(request.full_url, 'http://tracker:8000/api/telegram-polls/vote')
        self.assertEqual(json.loads(request.data), dict(telegram_id=42, poll_id=7, choice=1, chat_id=None))
        stamp = request.get_header('X-poll-time')
        expected = hmac.new(b'secret', stamp.encode() + b'.' + request.data, hashlib.sha256).hexdigest()
        self.assertEqual(request.get_header('X-poll-signature'), expected)

    def test_closed_response(self):
        error = urllib.error.HTTPError('url', 409, 'Conflict', {}, io.BytesIO(json.dumps({'detail': 'Опрос закрыт'}).encode()))
        with patch('handlers.command_tracker_poll.urllib.request.urlopen', side_effect=error):
            self.assertEqual(submit_vote('secret', 42, 7, 1), 'Опрос закрыт')

    def query(self, chat_id=42, kind='private', data='ikpoll:7:1'):
        return SimpleNamespace(message=SimpleNamespace(chat=SimpleNamespace(id=chat_id, type=kind)),
            from_user=SimpleNamespace(id=42), bot=SimpleNamespace(token='secret'), data=data, answer=AsyncMock())

    def test_uses_authenticated_telegram_identity(self):
        query = self.query()
        with patch('handlers.command_tracker_poll.submit_vote', return_value='Ваш выбор: Приду') as submit:
            asyncio.run(answer_poll(query))
        submit.assert_called_once_with('secret', 42, 7, 1, 42)
        query.answer.assert_awaited_once_with('Ваш выбор: Приду', show_alert=True)

    def test_forwarded_private_message_rejected(self):
        for query in [self.query(chat_id=99)]:
            with patch('handlers.command_tracker_poll.submit_vote') as submit:
                asyncio.run(answer_poll(query))
            submit.assert_not_called()

    def test_failure_does_not_claim_vote_saved(self):
        query = self.query()
        with patch('handlers.command_tracker_poll.submit_vote', side_effect=OSError('offline')):
            asyncio.run(answer_poll(query))
        self.assertIn('Не удалось сохранить', query.answer.call_args.args[0])

    def test_group_passes_original_chat_and_clicking_user(self):
        query = self.query(chat_id=-100123, kind='supergroup')
        with patch('handlers.command_tracker_poll.submit_vote', return_value='Ваш выбор: Приду') as submit:
            asyncio.run(answer_poll(query))
        submit.assert_called_once_with('secret', 42, 7, 1, -100123)
