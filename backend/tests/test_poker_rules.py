"""Poker betting regressions; these tests do not require a database."""
import copy
import unittest

from app.games import poker


def table(stacks):
    state = {'players': [dict(id=i, name=str(i), stack=stack) for i, stack in enumerate(stacks)],
             'dealer': -1, 'phase': None}
    return poker.new_hand(state)


class PokerRulesTests(unittest.TestCase):
    def test_short_all_in_does_not_reopen_raise(self):
        for action in ('raise', 'all_in'):
            with self.subTest(action=action):
                state = table([1000, 50, 1000])
                poker.move(state, 0, 'raise', 40)
                poker.move(state, 1, 'all_in')
                poker.move(state, 2, 'call')
                before = copy.deepcopy(state)
                with self.assertRaises(poker.IllegalMove):
                    poker.move(state, 0, action, 100)
                self.assertEqual(state, before)
                poker.move(state, 0, 'call')
                self.assertEqual(state['phase'], 'flop')

    def test_full_raise_reopens_betting(self):
        state = table([1000, 1000, 1000])
        poker.move(state, 0, 'raise', 40)
        poker.move(state, 1, 'raise', 80)
        poker.move(state, 2, 'call')
        self.assertTrue(poker.can_raise(state, 0))
        poker.move(state, 0, 'raise', 120)
        self.assertEqual(state['current_bet'], 120)

    def test_cumulative_short_raises_reopen_betting(self):
        state = table([1000, 50, 60])
        poker.move(state, 0, 'raise', 40)
        poker.move(state, 1, 'all_in')
        poker.move(state, 2, 'all_in')
        self.assertTrue(poker.can_raise(state, 0))

    def test_short_big_blind_keeps_full_bring_in(self):
        state = table([1000, 1000, 5])
        self.assertEqual(state['current_bet'], 20)
        poker.move(state, 0, 'call')
        self.assertEqual(state['players'][0]['bet'], 20)

    def test_no_betting_against_only_all_in_opponents(self):
        state = table([1000, 10])
        self.assertEqual(state['phase'], 'showdown')
        self.assertIsNone(state['turn'])
        self.assertIsNone(state['turn_deadline'])
        self.assertEqual(len(state['board']), 5)
        self.assertEqual(sum(p['stack'] for p in state['players']), 1010)

    def test_last_player_still_has_to_call(self):
        state = table([1000, 20])
        self.assertEqual(state['turn'], 0)
        poker.move(state, 0, 'call')
        self.assertEqual(state['phase'], 'showdown')
        self.assertEqual(sum(p['stack'] for p in state['players']), 1020)

    def test_turn_deadline_and_fold_win(self):
        state = table([1000, 1000])
        self.assertIsNotNone(state['turn_deadline'])
        poker.move(state, state['turn'], 'fold')
        self.assertEqual(state['phase'], 'showdown')
        self.assertIsNone(state['turn_deadline'])
        self.assertEqual(sum(p['stack'] for p in state['players']), 2000)

    def test_check_can_raise_after_short_opening_all_in(self):
        state = table([1000, 30, 1000])
        poker.move(state, 0, 'call')
        poker.move(state, 1, 'call')
        poker.move(state, 2, 'check')
        # Small blind has 10 left; first the big blind checks on the flop.
        # Switch the short stack to the next player to exercise check -> short bet.
        state['players'][1]['stack'], state['players'][2]['stack'] = state['players'][2]['stack'], state['players'][1]['stack']
        poker.move(state, 1, 'check')
        poker.move(state, 2, 'all_in')
        poker.move(state, 0, 'call')
        self.assertTrue(poker.can_raise(state, 1))
        poker.move(state, 1, 'raise', 20)
        self.assertEqual(state['current_bet'], 20)
        self.assertEqual(state['min_raise'], 20)
