"""Морской бой 10 на 10: чистая логика без БД и HTTP.

Классика: флот 1×4, 2×3, 3×2, 4×1, корабли не касаются даже углами.
Попал — стреляешь ещё, промахнулся — ход соперника. Потопленный корабль
обводится промахами: там кораблей быть не может.

Клетка — int 0..99 (row * 10 + col). Перенесено из бота flood
(bot/utils/seabattle.py); бот здесь без памяти — цели выводит из выстрелов
на доске, чтобы партия целиком жила в JSON.
"""
import random
from dataclasses import dataclass, field

N = 10
FLEET = (4, 3, 3, 2, 2, 2, 1, 1, 1, 1)

MISS, HIT = "miss", "hit"


class IllegalMove(Exception):
    pass


def row_of(cell: int) -> int:
    return cell // N


def col_of(cell: int) -> int:
    return cell % N


def neighbours(cell: int) -> list[int]:
    """Ортогональные соседи внутри поля."""
    r, c = row_of(cell), col_of(cell)
    return [
        (r + dr) * N + c + dc
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1))
        if 0 <= r + dr < N and 0 <= c + dc < N
    ]


def halo(cells: set[int]) -> set[int]:
    """Клетки и все 8 их соседей (зона, где другой корабль стоять не может)."""
    out = set(cells)
    for cell in cells:
        r, c = row_of(cell), col_of(cell)
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                if 0 <= r + dr < N and 0 <= c + dc < N:
                    out.add((r + dr) * N + c + dc)
    return out


def ship_cells(start: int, size: int, vertical: bool) -> set[int] | None:
    """Клетки корабля от носа вправо/вниз. None — вылезает за поле."""
    r, c = row_of(start), col_of(start)
    if vertical:
        return {start + i * N for i in range(size)} if r + size <= N else None
    return {start + i for i in range(size)} if c + size <= N else None


def is_straight(cells: set[int]) -> bool:
    """Клетки идут подряд в одну линию."""
    ordered = sorted(cells)
    if len(ordered) == 1:
        return True
    rows = {row_of(c) for c in ordered}
    if len(rows) == 1:
        return ordered[-1] - ordered[0] == len(ordered) - 1
    cols = {col_of(c) for c in ordered}
    return len(cols) == 1 and ordered[-1] - ordered[0] == (len(ordered) - 1) * N


def validate_fleet(ships: list[list[int]]) -> list[list[int]]:
    """Проверить расстановку игрока; вернуть её в каноническом виде."""
    fleet = [sorted(set(ship)) for ship in ships]
    if sorted((len(s) for s in fleet), reverse=True) != list(FLEET):
        raise IllegalMove("Нужен полный флот: 4, 3, 3, 2, 2, 2, 1, 1, 1, 1")
    taken: set[int] = set()
    for ship in fleet:
        if any(not 0 <= c < N * N for c in ship) or not is_straight(set(ship)):
            raise IllegalMove("Корабль должен стоять ровно в линию внутри поля")
        if set(ship) & taken:
            raise IllegalMove("Корабли не должны касаться друг друга")
        taken |= halo(set(ship))
    return fleet


def random_fleet(rng: random.Random | None = None) -> list[list[int]]:
    rng = rng or random.Random()
    while True:  # почти всегда с первой попытки; тупик — просто перебрасываем
        ships, blocked = [], set()
        for size in FLEET:
            options = [
                cells
                for start in range(N * N)
                for vertical in (False, True)
                if (cells := ship_cells(start, size, vertical)) is not None and not cells & blocked
            ]
            if not options:
                break
            cells = rng.choice(options)
            ships.append(sorted(cells))
            blocked |= halo(cells)
        else:
            return ships


@dataclass
class Board:
    ships: list[list[int]] = field(default_factory=list)
    # Выстрелы по этой доске: клетка → miss/hit. Ключи — int (в JSON строкой).
    shots: dict[int, str] = field(default_factory=dict)

    def ship_at(self, cell: int) -> list[int] | None:
        return next((ship for ship in self.ships if cell in ship), None)

    def is_sunk(self, ship: list[int]) -> bool:
        return all(self.shots.get(c) == HIT for c in ship)

    def sunk_ships(self) -> list[list[int]]:
        return [ship for ship in self.ships if self.is_sunk(ship)]

    def alive_sizes(self) -> list[int]:
        return sorted((len(s) for s in self.ships if not self.is_sunk(s)), reverse=True)

    def all_sunk(self) -> bool:
        return bool(self.ships) and all(self.is_sunk(s) for s in self.ships)


@dataclass
class Game:
    boards: list[Board] = field(default_factory=lambda: [Board(), Board()])
    turn: int = 0  # кто стреляет
    over: bool = False
    winner: int | None = None
    # Последняя серия выстрелов (кто, клетка) — подсветить, куда бил соперник.
    recent: list[list[int]] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "boards": [
                {"ships": [list(s) for s in b.ships], "shots": {str(k): v for k, v in b.shots.items()}}
                for b in self.boards
            ],
            "turn": self.turn,
            "over": self.over,
            "winner": self.winner,
            "recent": [list(r) for r in self.recent],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Game":
        return cls(
            boards=[
                Board(ships=[list(s) for s in b["ships"]], shots={int(k): v for k, v in b["shots"].items()})
                for b in data["boards"]
            ],
            turn=data["turn"],
            over=data["over"],
            winner=data["winner"],
            recent=[list(r) for r in data.get("recent", [])],
        )


def placed(game: Game, seat: int) -> bool:
    return bool(game.boards[seat].ships)


def place_fleet(game: Game, seat: int, ships: list[list[int]]) -> None:
    if placed(game, seat):
        raise IllegalMove("Флот уже расставлен")
    game.boards[seat].ships = validate_fleet(ships)


def fire(game: Game, seat: int, cell: int) -> str:
    """Выстрел игрока seat по доске соперника: miss / hit / sunk."""
    if game.over:
        raise IllegalMove("Партия окончена")
    if game.turn != seat:
        raise IllegalMove("Сейчас стреляет соперник")
    if not 0 <= cell < N * N:
        raise IllegalMove("Мимо поля")
    board = game.boards[1 - seat]
    if cell in board.shots:
        raise IllegalMove("Сюда уже стреляли")

    if game.recent and game.recent[-1][0] != seat:
        game.recent = []
    game.recent.append([seat, cell])

    ship = board.ship_at(cell)
    if ship is None:
        board.shots[cell] = MISS
        game.turn = 1 - seat
        return MISS
    board.shots[cell] = HIT
    if not board.is_sunk(ship):
        return HIT
    # Вокруг потопленного кораблей нет — обводим, чтобы туда не стреляли.
    for around in halo(set(ship)) - set(ship):
        board.shots.setdefault(around, MISS)
    if board.all_sunk():
        game.over, game.winner = True, seat
    return "sunk"


def resign(game: Game, seat: int) -> None:
    if game.over:
        raise IllegalMove("Партия окончена")
    game.over, game.winner = True, 1 - seat


def bot_target(board: Board, rng: random.Random | None = None) -> int:
    """Куда стрелять по доске board: добивать раненый, иначе искать по шахматке.

    Смотрит только на выстрелы (как человек), расположение кораблей не подглядывает.
    """
    rng = rng or random.Random()
    free = [c for c in range(N * N) if c not in board.shots]
    sunk = {c for ship in board.sunk_ships() for c in ship}
    wounded = sorted(c for c, res in board.shots.items() if res == HIT and c not in sunk)
    if wounded:
        if len(wounded) > 1:
            # Направление известно — продолжаем линию в обе стороны.
            step = 1 if row_of(wounded[0]) == row_of(wounded[-1]) else N
            ends = [wounded[0] - step, wounded[-1] + step]
            line = [
                c for c in ends
                if 0 <= c < N * N and c not in board.shots
                and (step == N or row_of(c) == row_of(wounded[0]))
            ]
            if line:
                return rng.choice(line)
        around = [nb for c in wounded for nb in neighbours(c) if nb not in board.shots]
        if around:
            return rng.choice(around)
    # Шахматка: любой корабль от двух палуб её задевает. Остались одни
    # однопалубные — бьём куда угодно.
    if max(board.alive_sizes(), default=1) > 1:
        parity = [c for c in free if (row_of(c) + col_of(c)) % 2 == 0]
        return rng.choice(parity or free)
    return rng.choice(free)


def run_bot(game: Game, seat: int = 1) -> None:
    """Бот стреляет, пока попадает."""
    while not game.over and game.turn == seat:
        fire(game, seat, bot_target(game.boards[1 - seat]))


def new_game(rng: random.Random | None = None) -> Game:
    rng = rng or random.Random()
    return Game(turn=rng.randrange(2))
