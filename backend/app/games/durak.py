"""Подкидной дурак один на один: чистая механика, без БД и HTTP.

Перенесено из бота (bot/utils/durak.py) и обобщено: оба места — люди или
место 1 — бот. Состояние сериализуется в dict (хранится JSON-ом в БД).

Правила: колода 36, раздача по 6, козырь — масть нижней карты прикупа.
Первым ходит владелец младшего козыря. Нападающий подкидывает карты рангов
со стола, но не больше 6 и не больше карт защитника на начало захода.
Защитник бьёт старшей в масть или козырем либо берёт. Сказал «беру» —
нападающий ещё может подкинуть вдогонку, потом «забирай». Всё побито —
нападающий подкидывает или говорит «бито», атака переходит.
Добор до 6: сначала нападавший, потом защитник. Проигрывает тот, кто
остался с картами при пустом прикупе; оба пустые — ничья.

Карта — число suit*13 + (rank-2): масть 0..3 (♠ ♥ ♦ ♣), ранг 6..14 (14 — туз).
"""
import copy
import random
from dataclasses import asdict, dataclass, field

RANKS = (6, 7, 8, 9, 10, 11, 12, 13, 14)
SUITS = (0, 1, 2, 3)
HAND_SIZE = 6


class IllegalMove(Exception):
    pass


def suit_of(card: int) -> int:
    return card // 13


def rank_of(card: int) -> int:
    return card % 13 + 2


def full_deck() -> list[int]:
    return [s * 13 + (r - 2) for s in SUITS for r in RANKS]


def beats(att: int, dfn: int, trump: int) -> bool:
    """Бьёт ли dfn карту att: старшая в масть или козырь по некозырю."""
    if suit_of(dfn) == suit_of(att):
        return rank_of(dfn) > rank_of(att)
    return suit_of(dfn) == trump and suit_of(att) != trump


@dataclass
class Game:
    talon: list[int] = field(default_factory=list)
    trump: int = 0
    trump_card: int = 0  # нижняя карта прикупа — видна всем до конца прикупа
    hands: list[list[int]] = field(default_factory=lambda: [[], []])
    table: list[list] = field(default_factory=list)  # [атака, защита|None]
    attacker: int = 0
    bout_def_count: int = HAND_SIZE  # карт у защитника на начало захода (лимит)
    taking: bool = False  # защитник сказал «беру», ждём «забирай»
    beaten: int = 0  # карт в отбое
    over: bool = False
    winner: int | None = None  # 0/1; None при over — ничья

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Game":
        # Глубокая копия: иначе ход меняет списки прямо в загруженном из БД
        # JSON, и SQLAlchemy не видит разницы между старым и новым состоянием.
        return cls(**copy.deepcopy(data))


def _sort_key(trump: int, card: int) -> tuple[int, int, int]:
    """Дешёвая карта первой: некозыри по возрастанию, потом козыри."""
    return (int(suit_of(card) == trump), rank_of(card), suit_of(card))


def sort_hand(game: Game, hand: list[int]) -> list[int]:
    return sorted(hand, key=lambda c: _sort_key(game.trump, c))


def new_game(seed: int | None = None) -> Game:
    rng = random.Random(seed)
    deck = full_deck()
    rng.shuffle(deck)
    game = Game(
        talon=deck[12:],
        trump=suit_of(deck[-1]),
        trump_card=deck[-1],
        hands=[deck[0:6], deck[6:12]],
    )
    game.attacker = _first_attacker(game)
    game.bout_def_count = len(game.hands[defender_of(game)])
    return game


def _first_attacker(game: Game) -> int:
    """Владелец младшего козыря; козырей ни у кого — место 0."""
    best: tuple[int, int] | None = None
    for player in (0, 1):
        for card in game.hands[player]:
            if suit_of(card) == game.trump:
                cand = (rank_of(card), player)
                if best is None or cand < best:
                    best = cand
    return best[1] if best is not None else 0


def defender_of(game: Game) -> int:
    return 1 - game.attacker


def attack_limit(game: Game) -> int:
    return min(HAND_SIZE, game.bout_def_count)


def uncovered(game: Game) -> list[int]:
    return [att for att, dfn in game.table if dfn is None]


def all_covered(game: Game) -> bool:
    return bool(game.table) and all(dfn is not None for _, dfn in game.table)


def legal_attacks(game: Game, player: int) -> list[int]:
    """Чем можно напасть/подкинуть. Пусто — нельзя."""
    if game.over or player != game.attacker:
        return []
    hand = sort_hand(game, game.hands[player])
    if not game.table:
        return hand
    if len(game.table) >= attack_limit(game):
        return []
    ranks = {rank_of(c) for row in game.table for c in row if c is not None}
    return [c for c in hand if rank_of(c) in ranks]


def legal_beaters(game: Game, player: int, att: int) -> list[int]:
    """Чем можно побить конкретную карту стола."""
    if game.over or game.taking or player != defender_of(game) or att not in uncovered(game):
        return []
    return sort_hand(game, [c for c in game.hands[player] if beats(att, c, game.trump)])


def can_take(game: Game, player: int) -> bool:
    return not game.over and not game.taking and player == defender_of(game) and bool(uncovered(game))


def can_finish_bout(game: Game, player: int) -> bool:
    """«Бито» (всё покрыто) или «забирай» (защитник берёт) — решает нападающий."""
    if game.over or player != game.attacker:
        return False
    return game.taking or all_covered(game)


def attack(game: Game, player: int, card: int) -> None:
    if card not in legal_attacks(game, player):
        raise IllegalMove("Этой картой сейчас ходить нельзя")
    game.hands[player].remove(card)
    game.table.append([card, None])


def defend(game: Game, player: int, att: int, card: int) -> None:
    if card not in legal_beaters(game, player, att):
        raise IllegalMove("Эта карта не бьёт")
    for row in game.table:
        if row[0] == att and row[1] is None:
            game.hands[player].remove(card)
            row[1] = card
            return


def take(game: Game, player: int) -> None:
    if not can_take(game, player):
        raise IllegalMove("Сейчас брать нечего")
    game.taking = True


def finish_bout(game: Game, player: int) -> None:
    """Нападающий закрывает заход: «забирай» при взятии, иначе «бито»."""
    if not can_finish_bout(game, player):
        raise IllegalMove("Заход ещё не закончен")
    old_attacker = game.attacker
    if game.taking:
        cards = [c for row in game.table for c in row if c is not None]
        game.hands[defender_of(game)].extend(cards)
        # Взявший пропускает ход — атакует тот же.
    else:
        game.beaten += sum(2 for _ in game.table)
        game.attacker = defender_of(game)
    game.table.clear()
    game.taking = False
    _draw_up(game, old_attacker)
    game.bout_def_count = len(game.hands[defender_of(game)])
    _check_over(game)


def resign(game: Game, player: int) -> None:
    if game.over:
        raise IllegalMove("Партия уже закончена")
    game.over, game.winner = True, 1 - player


def _draw_up(game: Game, first: int) -> None:
    for player in (first, 1 - first):
        hand = game.hands[player]
        while len(hand) < HAND_SIZE and game.talon:
            hand.append(game.talon.pop(0))


def _check_over(game: Game) -> None:
    if game.talon:
        return
    empty = [not game.hands[p] for p in (0, 1)]
    if empty[0] and empty[1]:
        game.over, game.winner = True, None
    elif empty[0]:
        game.over, game.winner = True, 0
    elif empty[1]:
        game.over, game.winner = True, 1


def card_count(game: Game) -> int:
    """Карты в игре — для проверки инварианта (всегда 36)."""
    return (
        len(game.talon) + game.beaten + sum(len(h) for h in game.hands)
        + sum(1 for row in game.table for c in row if c is not None)
    )


# ── Бот (место 1). Эвристики из бота flood. ──

def _ai_defense_plan(game: Game, bot: int) -> dict[int, int] | None:
    """План на все непокрытые карты: {атака: защита}. None — брать."""
    def cost(att: int):
        opts = legal_beaters(game, bot, att)
        return _sort_key(game.trump, opts[0]) if opts else (2, 99, 0)

    plan: dict[int, int] = {}
    used: set[int] = set()
    for att in sorted(uncovered(game), key=cost, reverse=True):
        opts = [c for c in legal_beaters(game, bot, att) if c not in used]
        if not opts:
            return None
        plan[att] = opts[0]
        used.add(opts[0])
    return plan


def _ai_toss(game: Game, bot: int) -> int | None:
    """Подкинуть самую дешёвую. Козыри бережём, пока стол мал."""
    opts = legal_attacks(game, bot)
    if not opts:
        return None
    plain = [c for c in opts if suit_of(c) != game.trump]
    if plain:
        return plain[0]
    if len(game.table) >= 2 and game.talon:
        return None
    return opts[0]


def bot_step(game: Game, bot: int = 1) -> bool:
    """Один ход бота, если сейчас его очередь. False — бот ждёт человека."""
    if game.over:
        return False
    if game.attacker == bot:
        if not game.table:
            attack(game, bot, sort_hand(game, game.hands[bot])[0])
            return True
        if game.taking or all_covered(game):
            card = _ai_toss(game, bot)
            if card is not None:
                attack(game, bot, card)
            else:
                finish_bout(game, bot)
            return True
        return False  # ждём, пока человек отобьётся
    if uncovered(game) and not game.taking:
        plan = _ai_defense_plan(game, bot)
        if plan is None:
            take(game, bot)
        else:
            for att, card in plan.items():
                defend(game, bot, att, card)
        return True
    return False


def run_bot(game: Game, bot: int = 1) -> None:
    """Бот ходит, пока очередь за ним (с предохранителем от зацикливания)."""
    for _ in range(100):
        if not bot_step(game, bot):
            return
