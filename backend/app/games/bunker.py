"""«Бункер»: чистая логика партии (без БД), состояние — JSON-словарь.

Мест в бункере вдвое меньше, чем игроков. У каждого семь характеристик,
вначале открыта только профессия. Партия идёт ROUNDS раундов:

  reveal  — каждый открывает одну свою карту;
  discuss — обсуждают вживую; создатель жмёт «Дальше»;
  vote    — тайное голосование, кого не пускать (если в этом раунде есть изгнание);
  result  — итог голосования: кто выбыл или ничья (тогда переголосование среди
            лидеров; повторная ничья — жребий).

Сколько изгнаний в каком раунде — schedule(): к концу остаётся ровно seats
игроков. После последнего раунда партия закончена, все карты открыты.
Места игроков — индексы в state["players"] (порядок входа в лобби).
"""
import random

from app.games.bunker_cards import BUNKER_ROOMS, BUNKER_SUPPLIES, CATASTROPHES, DECKS

MIN_PLAYERS = 4
MAX_PLAYERS = 16
ROUNDS = 5

# Порядок характеристик на карточке игрока.
CATEGORIES = ["profession", "biology", "health", "hobby", "phobia", "baggage", "fact"]


class IllegalMove(Exception):
    pass


def seats_for(players: int) -> int:
    return players // 2


def schedule(players: int) -> list[int]:
    """Изгнаний по раундам: первые раунды — на знакомство, выгоняют ближе к концу."""
    base, extra = divmod(players - seats_for(players), ROUNDS)
    return [base + (1 if i >= ROUNDS - extra else 0) for i in range(ROUNDS)]


def _biology(rng: random.Random) -> tuple[str, int]:
    age = rng.randint(18, 75)
    sex = rng.choice(["Мужчина", "Женщина"])
    return f"{sex}, {age} {_years(age)}", age


def _years(n: int) -> str:
    if n % 10 == 1 and n % 100 != 11:
        return "год"
    if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14):
        return "года"
    return "лет"


def new_game(players: int, rng: random.Random | None = None) -> dict:
    if not MIN_PLAYERS <= players <= MAX_PLAYERS:
        raise IllegalMove(f"Нужно от {MIN_PLAYERS} до {MAX_PLAYERS} игроков")
    rng = rng or random.Random()
    title, text, duration = rng.choice(CATASTROPHES)
    decks = {cat: rng.sample(cards, players) for cat, cards in DECKS.items()}
    seats = []
    for i in range(players):
        biology, age = _biology(rng)
        experience = rng.randint(0, min(40, age - 18))
        profession = decks["profession"][i]
        if experience:
            profession += f", стаж {experience} {_years(experience)}"
        cards = {"profession": profession, "biology": biology}
        cards.update({cat: decks[cat][i] for cat in DECKS if cat != "profession"})
        seats.append({"cards": cards, "revealed": ["profession"], "out": False, "out_round": None})
    return {
        "catastrophe": {"title": title, "text": text, "duration": duration},
        "bunker": {
            "area": rng.randrange(40, 301, 10),
            "supplies": rng.choice(BUNKER_SUPPLIES),
            "rooms": rng.sample(BUNKER_ROOMS, 3),
        },
        "seats": seats_for(players),
        "schedule": schedule(players),
        "players": seats,
        "round": 1,
        "phase": "reveal",
        # Кто уже открыл карту в этом раунде.
        "revealed_round": [],
        "excluded_round": 0,
        "votes": {},
        # Переголосование: голосуют только за лидеров ничьей.
        "candidates": None,
        "last_vote": None,
    }


def active(state: dict) -> list[int]:
    return [i for i, p in enumerate(state["players"]) if not p["out"]]


def over(state: dict) -> bool:
    return state["phase"] == "over"


def _check_active(state: dict, seat: int) -> None:
    if over(state):
        raise IllegalMove("Партия закончена")
    if seat not in active(state):
        raise IllegalMove("Вы уже не в игре")


def reveal(state: dict, seat: int, category: str) -> None:
    _check_active(state, seat)
    if state["phase"] != "reveal":
        raise IllegalMove("Сейчас карты не открывают")
    if seat in state["revealed_round"]:
        raise IllegalMove("В этом раунде вы уже открыли карту")
    player = state["players"][seat]
    if category not in CATEGORIES or category in player["revealed"]:
        raise IllegalMove("Эта карта уже открыта")
    player["revealed"].append(category)
    state["revealed_round"].append(seat)
    if all(i in state["revealed_round"] for i in active(state)):
        state["phase"] = "discuss"


def vote(state: dict, seat: int, target: int, rng: random.Random | None = None) -> None:
    _check_active(state, seat)
    if state["phase"] != "vote":
        raise IllegalMove("Сейчас не голосуют")
    allowed = state["candidates"] or active(state)
    if target == seat or target not in allowed or target not in active(state):
        raise IllegalMove("За этого игрока голосовать нельзя")
    state["votes"][str(seat)] = target
    if all(str(i) in state["votes"] for i in active(state)):
        _tally(state, rng)


def to_exclude(state: dict) -> int:
    """Сколько ещё выгнать в этом раунде."""
    if over(state):
        return 0
    return state["schedule"][state["round"] - 1] - state["excluded_round"]


def advance(state: dict, rng: random.Random | None = None) -> None:
    """«Дальше» от создателя: ведёт партию, если ждать больше некого или нечего."""
    phase = state["phase"]
    if phase == "over":
        raise IllegalMove("Партия закончена")
    if phase == "reveal":
        # Кто-то отошёл и не открывает — идём дальше без него.
        state["phase"] = "discuss"
    elif phase == "vote":
        if not state["votes"]:
            raise IllegalMove("Пока никто не проголосовал")
        _tally(state, rng)  # не проголосовавшие — воздержались
    elif state["candidates"] or to_exclude(state) > 0:
        state["phase"], state["votes"] = "vote", {}
    else:
        _next_round(state)


def _tally(state: dict, rng: random.Random | None) -> None:
    counts: dict[int, int] = {}
    for target in state["votes"].values():
        counts[target] = counts.get(target, 0) + 1
    top = max(counts.values())
    leaders = sorted(t for t, c in counts.items() if c == top)
    result = {"votes": dict(state["votes"]), "leaders": leaders, "out": None, "tie": False, "lot": False}
    if len(leaders) == 1:
        result["out"] = leaders[0]
    elif state["candidates"] is None:
        result["tie"] = True
    else:
        # Повторная ничья — решает жребий.
        result["out"], result["lot"] = (rng or random.Random()).choice(leaders), True
    state["votes"] = {}
    state["last_vote"] = result
    state["phase"] = "result"
    if result["out"] is None:
        state["candidates"] = leaders
        return
    player = state["players"][result["out"]]
    player["out"], player["out_round"] = True, state["round"]
    player["revealed"] = list(CATEGORIES)
    state["candidates"] = None
    state["excluded_round"] += 1


def _next_round(state: dict) -> None:
    if state["round"] >= ROUNDS:
        state["phase"] = "over"
        for player in state["players"]:
            player["revealed"] = list(CATEGORIES)
        return
    state["round"] += 1
    state["phase"] = "reveal"
    state["revealed_round"] = []
    state["excluded_round"] = 0
    state["last_vote"] = None
