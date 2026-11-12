"""Texas hold'em for a private table. Cards use suit * 13 + rank - 2."""

from collections import Counter
from itertools import combinations
import secrets

MIN_PLAYERS = 2
MAX_PLAYERS = 6
START_STACK = 1000
SMALL_BLIND = 10
BIG_BLIND = 20


class IllegalMove(ValueError):
    pass


def score_five(cards: tuple[int, ...]) -> tuple[int, ...]:
    ranks = [card % 13 + 2 for card in cards]
    counts = Counter(ranks)
    groups = sorted(((n, rank) for rank, n in counts.items()), reverse=True)
    unique = set(ranks)
    if 14 in unique:
        unique.add(1)
    straight = max((high for high in range(5, 15) if all(high - i in unique for i in range(5))), default=0)
    flush = len({card // 13 for card in cards}) == 1
    if straight and flush:
        return 8, straight
    if groups[0][0] == 4:
        return 7, groups[0][1], groups[1][1]
    if groups[0][0] == 3 and groups[1][0] == 2:
        return 6, groups[0][1], groups[1][1]
    if flush:
        return (5, *sorted(ranks, reverse=True))
    if straight:
        return 4, straight
    if groups[0][0] == 3:
        return (3, groups[0][1], *sorted((r for r in ranks if r != groups[0][1]), reverse=True))
    if groups[0][0] == 2 and groups[1][0] == 2:
        high, low = sorted((groups[0][1], groups[1][1]), reverse=True)
        return 2, high, low, next(r for r in ranks if r not in (high, low))
    if groups[0][0] == 2:
        return (1, groups[0][1], *sorted((r for r in ranks if r != groups[0][1]), reverse=True))
    return (0, *sorted(ranks, reverse=True))


def score_seven(cards: list[int]) -> tuple[int, ...]:
    return max(score_five(hand) for hand in combinations(cards, 5))


def _live(state: dict) -> list[int]:
    return [i for i, p in enumerate(state['players']) if p['stack'] > 0]


def _next(state: dict, after: int, candidates: list[int]) -> int:
    return min(candidates, key=lambda i: (i - after - 1) % len(state['players']))


def _bet(state: dict, seat: int, amount: int) -> None:
    p = state['players'][seat]
    paid = min(p['stack'], amount)
    p['stack'] -= paid
    p['bet'] += paid
    p['invested'] += paid


def new_hand(state: dict) -> dict:
    if state.get('phase') not in (None, 'showdown'):
        raise IllegalMove('Раздача ещё идёт')
    live = _live(state)
    if len(live) < MIN_PLAYERS:
        raise IllegalMove('Нужно хотя бы два игрока с фишками')
    state['dealer'] = _next(state, state.get('dealer', -1), live)
    dealer = state['dealer']
    small = dealer if len(live) == 2 else _next(state, dealer, live)
    big = _next(state, small, live)
    deck = list(range(52))
    secrets.SystemRandom().shuffle(deck)
    state.update(deck=deck, board=[], phase='preflop', turn=None, current_bet=0,
                 min_raise=BIG_BLIND, result=None)
    for p in state['players']:
        p.update(cards=[], folded=False, bet=0, invested=0, acted=False)
    for i in live:
        state['players'][i]['cards'] = [deck.pop(), deck.pop()]
    _bet(state, small, SMALL_BLIND)
    _bet(state, big, BIG_BLIND)
    state['current_bet'] = state['players'][big]['bet']
    eligible = [i for i in live if state['players'][i]['stack'] > 0]
    state['turn'] = _next(state, big, eligible) if eligible else None
    if state['turn'] is None:
        _advance(state)
    return state


def _advance(state: dict) -> None:
    contenders = [i for i, p in enumerate(state['players']) if p['cards'] and not p['folded']]
    if len(contenders) == 1:
        winner = contenders[0]
        pot = sum(p['invested'] for p in state['players'])
        state['players'][winner]['stack'] += pot
        state.update(phase='showdown', turn=None, result={'winners': [winner], 'payouts': {str(winner): pot}})
        return
    while True:
        phase = state['phase']
        if phase == 'river':
            _showdown(state)
            return
        count = {'preflop': 3, 'flop': 1, 'turn': 1}[phase]
        state['deck'].pop()  # burn card
        state['board'].extend(state['deck'].pop() for _ in range(count))
        state['phase'] = {'preflop': 'flop', 'flop': 'turn', 'turn': 'river'}[phase]
        state['current_bet'] = 0
        state['min_raise'] = BIG_BLIND
        for p in state['players']:
            p['bet'] = 0
            p['acted'] = False
        eligible = [i for i in contenders if state['players'][i]['stack'] > 0]
        if len(eligible) >= 2:
            state['turn'] = _next(state, state['dealer'], eligible)
            return


def _showdown(state: dict) -> None:
    players = state['players']
    contenders = [i for i, p in enumerate(players) if p['cards'] and not p['folded']]
    scores = {i: score_seven(players[i]['cards'] + state['board']) for i in contenders}
    levels = sorted({p['invested'] for p in players if p['invested']})
    previous = 0
    payouts = {i: 0 for i in contenders}
    for level in levels:
        pot = (level - previous) * sum(p['invested'] >= level for p in players)
        eligible = [i for i in contenders if players[i]['invested'] >= level]
        if eligible:
            best = max(scores[i] for i in eligible)
            winners = [i for i in eligible if scores[i] == best]
            for i in winners:
                payouts[i] += pot // len(winners)
            for i in sorted(winners, key=lambda i: (i - state['dealer'] - 1) % len(players))[:pot % len(winners)]:
                payouts[i] += 1
        previous = level
    for i, amount in payouts.items():
        players[i]['stack'] += amount
    state.update(phase='showdown', turn=None, result={
        'winners': [i for i, amount in payouts.items() if amount],
        'payouts': {str(i): amount for i, amount in payouts.items() if amount},
        'scores': {str(i): list(value) for i, value in scores.items()},
    })


def move(state: dict, seat: int, action: str, amount: int | None = None) -> dict:
    if state['phase'] == 'showdown' or state['turn'] != seat:
        raise IllegalMove('Сейчас не ваш ход')
    p = state['players'][seat]
    to_call = max(0, state['current_bet'] - p['bet'])
    if action == 'fold':
        p['folded'] = True
    elif action == 'check':
        if to_call:
            raise IllegalMove('Сначала нужно уравнять ставку')
    elif action == 'call':
        _bet(state, seat, to_call)
    elif action == 'raise':
        if amount is None or amount <= state['current_bet'] or amount > p['bet'] + p['stack']:
            raise IllegalMove('Укажите допустимую итоговую ставку')
        increase = amount - state['current_bet']
        if increase < state['min_raise'] and amount != p['bet'] + p['stack']:
            raise IllegalMove(f'Минимальное повышение: {state["min_raise"]}')
        _bet(state, seat, amount - p['bet'])
        if increase >= state['min_raise']:
            state['min_raise'] = increase
            for other in state['players']:
                other['acted'] = False
        state['current_bet'] = amount
    elif action == 'all_in':
        if p['stack'] <= 0:
            raise IllegalMove('Фишек не осталось')
        target = p['bet'] + p['stack']
        _bet(state, seat, p['stack'])
        if target > state['current_bet']:
            increase = target - state['current_bet']
            if increase >= state['min_raise']:
                state['min_raise'] = increase
                for other in state['players']:
                    other['acted'] = False
            state['current_bet'] = target
    else:
        raise IllegalMove('Неизвестное действие')
    p['acted'] = True
    contenders = [i for i, other in enumerate(state['players']) if other['cards'] and not other['folded']]
    if len(contenders) == 1:
        _advance(state)
        return state
    pending = [i for i in contenders if state['players'][i]['stack'] > 0 and
               (not state['players'][i]['acted'] or state['players'][i]['bet'] < state['current_bet'])]
    if pending:
        state['turn'] = _next(state, seat, pending)
    else:
        _advance(state)
    return state
