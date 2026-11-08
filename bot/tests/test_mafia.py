"""Никаких запросов к Telegram: транспорт заменён AsyncMock."""
import json
import random
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from utils.mafia import Game, Player


def game(chat=-100):
    g = Game(chat, 1)
    for uid in range(1, 6):
        g.join(uid, f'Игрок <{uid}>')
    g.start(random.Random(1))
    for p, role in zip(g.players, ['mafia', 'doctor', 'commissar', 'civilian', 'civilian']):
        p.role = role
    return g


class RulesTest(unittest.TestCase):
    def test_role_balance_all_sizes(self):
        for n in range(5, 17):
            g = Game(-1, 1)
            for uid in range(1, n+1):
                g.join(uid, str(uid))
            g.start()
            self.assertEqual(sum(p.role == 'doctor' for p in g.players), 1)
            self.assertEqual(sum(p.role == 'commissar' for p in g.players), 1)
            self.assertLess(sum(p.role == 'mafia' for p in g.players), n/2)
        with self.assertRaises(ValueError):
            Game(-1, 1).start()

    def test_heal_and_check(self):
        g = game()
        for uid, target in [(1, 4), (2, 4), (3, 1)]:
            g.choose(uid, target, turn=g.turn)
        self.assertTrue(g.ready())
        killed, checks = g.advance()
        self.assertIsNone(killed)
        self.assertEqual(checks, [(3, 1, True)])
        self.assertEqual(g.phase, 'day')
        self.assertFalse(g.actions)

    def test_kill_and_dead_cannot_vote(self):
        g = game()
        g.choose(1, 4, turn=g.turn)
        self.assertEqual(g.advance()[0], 4)
        g.advance()
        with self.assertRaises(ValueError):
            g.choose(4, 1, turn=g.turn, voting=True)

    def test_tie_skip_empty(self):
        for votes in ({2: 1, 3: 4}, {2: 0, 3: 0, 4: 1}, {}):
            g = game(); g.set_phase('voting'); g.votes = votes
            self.assertIsNone(g.advance()[0])
            self.assertEqual(len(g.alive), 5)
            self.assertFalse(g.votes)

    def test_two_mafia_must_agree(self):
        g = game(); g.players.append(Player(6, 'Шестой', 'mafia'))
        g.actions = {1: 4, 6: 5}
        self.assertIsNone(g.advance()[0])

    def test_invalid_and_stale_actions(self):
        g = game()
        for uid, target, turn in [(4, 1, g.turn), (1, 1, g.turn), (3, 3, g.turn), (1, 99, g.turn), (1, 4, g.turn-1), (99, 1, g.turn)]:
            with self.assertRaises(ValueError):
                g.choose(uid, target, turn=turn)
        g.choose(2, 2, turn=g.turn)  # Самолечение разрешено.
        g.choose(1, 0, turn=g.turn)
        self.assertEqual(g.actions[1], 0)
        g.choose(1, 4, turn=g.turn)
        self.assertEqual(g.actions[1], 4)

    def test_winners(self):
        g = game(); g.set_phase('voting'); g.votes = {2: 1, 3: 1, 4: 1}
        g.advance()
        self.assertEqual((g.phase, g.winner), ('end', 'civilians'))
        g = game()
        for uid in (3, 4, 5):
            g.player(uid).alive = False
        g.finish_if_won()
        self.assertEqual(g.winner, 'mafia')

    def test_json_roundtrip(self):
        g = game(); g.actions = {1: 4}
        restored = Game.loads(json.loads(json.dumps(g.dumps())))
        self.assertEqual(restored, g)
        restored.advance()
        self.assertFalse(restored.player(4).alive)

    def test_leave_transfers_host_and_bounds(self):
        g = Game(-1, 1); g.join(1, 'Один'); g.join(2, 'Два'); g.leave(1)
        self.assertEqual(g.host_id, 2)
        for uid in range(3, 18):
            g.join(uid, str(uid))
        with self.assertRaises(ValueError):
            g.join(18, 'Лишний')
        with self.assertRaises(ValueError):
            game().leave(1)


class TransportTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        from handlers import command_mafia as h
        from database import mafia_store as store
        self.h, self.store = h, store
        self.tmp = tempfile.TemporaryDirectory()
        self.old_path = store.PATH
        store.PATH = Path(self.tmp.name)/'sessions.db'
        await store.load()
        h.GAMES.clear()
        self.bot = SimpleNamespace(send_message=AsyncMock(), get_chat_member=AsyncMock(),
                                   me=AsyncMock(return_value=SimpleNamespace(username='testbot')))

    async def asyncTearDown(self):
        await self.h.shutdown()
        self.h.GAMES.clear()
        self.store.PATH = self.old_path
        self.tmp.cleanup()

    def query(self, g, uid, action, target=0, private=False, turn=None):
        return SimpleNamespace(
            data=f'mf:{g.token}:{g.turn if turn is None else turn}:{action}:{target}', bot=self.bot,
            from_user=SimpleNamespace(id=uid, full_name=f'Человек {uid}'), answer=AsyncMock(),
            message=SimpleNamespace(chat=SimpleNamespace(id=uid if private else g.chat_id,
                                                        type='private' if private else 'supergroup'), edit_text=AsyncMock()))

    async def put(self, g):
        self.h.GAMES[g.chat_id] = g
        await self.store.save(g)

    async def test_complete_game_and_secrecy(self):
        g = game(); await self.put(g)
        for uid, target in [(1, 4), (2, 4), (3, 1)]:
            await self.h.mafia_callback(self.query(g, uid, 'act', target, private=True))
        self.assertEqual(g.phase, 'day')
        public = [call.args[1] for call in self.bot.send_message.call_args_list if call.args[0] == g.chat_id]
        self.assertFalse(any('Твоя роль' in text or '🔎' in text for text in public))
        private = [call.args for call in self.bot.send_message.call_args_list if call.args[0] == 3]
        self.assertTrue(any('мафия' in args[1] for args in private))
        await self.h.mafia_callback(self.query(g, 1, 'next'))
        for uid, target in [(1, 2), (2, 1), (3, 1), (4, 1), (5, 1)]:
            await self.h.mafia_callback(self.query(g, uid, 'vote', target))
        self.assertNotIn(g.chat_id, self.h.GAMES)
        self.assertFalse(await self.store.load())
        self.assertTrue(any('Победили мирные' in call.args[1] for call in self.bot.send_message.call_args_list))

    async def test_forged_and_outdated_buttons(self):
        g = game(); await self.put(g)
        queries = [self.query(g, 4, 'act', 1, private=True), self.query(g, 99, 'act', 1, private=True),
                   self.query(g, 1, 'act', 4), self.query(g, 1, 'act', 4, private=True, turn=0),
                   self.query(g, 2, 'next')]
        for q in queries:
            await self.h.mafia_callback(q)
            self.assertTrue(q.answer.call_args.kwargs.get('show_alert'))
        self.assertFalse(g.actions)

    async def test_deadline_rejects_late_vote(self):
        g = game(); g.set_phase('voting'); g.deadline = time.time()-1; await self.put(g)
        await self.h.mafia_callback(self.query(g, 2, 'vote', 1))
        self.assertFalse(g.votes)
        await self.h.tick(self.bot)
        self.assertEqual(g.phase, 'night')

    async def test_lobby_join_and_stale_game(self):
        g = Game(-1, 1); await self.put(g)
        await self.h.mafia_callback(self.query(g, 1, 'join'))
        self.assertEqual(len(g.players), 1)
        await self.h.mafia_callback(self.query(g, 1, 'join'))
        self.assertEqual(len(g.players), 1)
        q = self.query(g, 2, 'start')
        await self.h.mafia_callback(q)
        self.assertEqual(g.phase, 'lobby')
        await self.h.mafia_callback(self.query(g, 1, 'leave'))
        self.assertNotIn(g.chat_id, self.h.GAMES)
        q = self.query(g, 1, 'join'); await self.h.mafia_callback(q)
        self.assertTrue(q.answer.call_args.kwargs.get('show_alert'))

    async def test_blocked_dm_does_not_join(self):
        from aiogram.exceptions import TelegramForbiddenError
        from aiogram.methods import SendMessage
        self.bot.send_message.side_effect = TelegramForbiddenError(method=SendMessage(chat_id=1, text='test'), message='blocked')
        g = Game(-1, 1); await self.put(g)
        q = self.query(g, 1, 'join'); await self.h.mafia_callback(q)
        self.assertFalse(g.players)
        self.assertIn('start=mafia', q.answer.call_args.kwargs['url'])

    async def test_start_failed_delivery_cancels(self):
        from aiogram.exceptions import TelegramForbiddenError
        from aiogram.methods import SendMessage
        async def deliver(chat_id, text, **kwargs):
            if chat_id == 2:
                raise TelegramForbiddenError(method=SendMessage(chat_id=2, text='test'), message='blocked')
        self.bot.send_message.side_effect = deliver
        g = Game(-1, 1)
        for uid in range(1, 6): g.join(uid, str(uid))
        await self.put(g)
        await self.h.start_game(self.bot, g, 1)
        self.assertNotIn(g.chat_id, self.h.GAMES)
        self.assertFalse(await self.store.load())

    async def test_recovery_preserves_roles_and_choices(self):
        g = game(); g.actions = {1: 4}; g.deadline = time.time()-100; await self.put(g)
        self.h.GAMES.clear()
        await self.h.startup(self.bot)
        restored = self.h.GAMES[g.chat_id]
        self.assertEqual(restored.actions, {1: 4})
        self.assertEqual([p.role for p in restored.players], [p.role for p in g.players])
        self.assertGreater(restored.deadline, time.time())
        self.assertTrue(self.h.WORKER)

    async def test_timers_and_chat_isolation(self):
        a, b = game(-1), game(-2)
        a.deadline = time.time()-1
        await self.put(a); await self.put(b)
        await self.h.tick(self.bot)
        self.assertEqual(a.phase, 'day'); self.assertEqual(b.phase, 'night')
        self.assertEqual(len(await self.store.load()), 2)

    async def test_lobby_expires_and_html_escaped(self):
        g = Game(-1, 1); g.join(1, '<b>name</b>'); g.deadline = time.time()-1
        self.assertIn('&lt;b&gt;', self.h.public_text(g))
        await self.put(g); await self.h.tick(self.bot)
        self.assertFalse(self.h.GAMES)

    async def test_callback_limits(self):
        g = game()
        for phase in ['lobby', 'day', 'voting']:
            g.phase = phase
            kb = self.h.public_kb(g)
            for row in kb.inline_keyboard:
                for btn in row:
                    self.assertLessEqual(len(btn.callback_data.encode()), 64)

    async def test_abandoned_game_closes_after_two_rounds(self):
        g = game(); await self.put(g)
        for _ in range(6):
            await self.h.advance(self.bot, g)
        self.assertEqual(g.idle_phases, 4)
        self.assertNotIn(g.chat_id, self.h.GAMES)
        self.assertFalse(await self.store.load())

    async def test_command_filter_and_lobby_creation(self):
        f = self.h.MafiaCommand()
        for text in ('!мафия', '!МАФИЯ старт', '/mafia@testbot'):
            self.assertTrue(await f(SimpleNamespace(text=text, bot=self.bot)))
        for text in ('!мафиячего', '/mafia@otherbot', '!кто', None):
            self.assertFalse(await f(SimpleNamespace(text=text, bot=self.bot)))
        msg = SimpleNamespace(text='!мафия', bot=self.bot, from_user=SimpleNamespace(id=1, is_bot=False),
                              sender_chat=None, chat=SimpleNamespace(id=-100, type='supergroup'),
                              message_thread_id=33, answer=AsyncMock())
        await self.h.mafia_command(msg)
        self.assertEqual(self.h.GAMES[-100].thread_id, 33)
        self.assertEqual(len(await self.store.load()), 1)
        msg.text = '!мафия статус'
        await self.h.mafia_command(msg)
        self.assertEqual(len(self.h.GAMES), 1)
        self.assertEqual(self.bot.send_message.call_args.kwargs['message_thread_id'], 33)


if __name__ == '__main__':
    unittest.main()
