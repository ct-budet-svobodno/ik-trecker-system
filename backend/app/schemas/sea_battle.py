from typing import Literal

from pydantic import BaseModel, Field

from app.models.sea_battle_game import SeaBattleStatus
from app.schemas.durak import DurakChatInvite, DurakReady


class SeaBattleCreate(BaseModel):
    vs_bot: bool = False


class SeaBattleMove(BaseModel):
    # place — расставить флот (ships); fire — выстрел в cell; resign — сдаться.
    action: Literal["place", "fire", "resign"]
    ships: list[list[int]] | None = Field(default=None, max_length=10)
    cell: int | None = Field(default=None, ge=0, le=99)
    # Версия партии, которую видел игрок: ход по устаревшей картине — 409.
    version: int


class SeaBattlePlayer(BaseModel):
    id: int | None  # None — бот
    full_name: str
    placed: bool  # флот расставлен
    # Живые корабли по длине — сколько осталось потопить.
    fleet: list[int]


class SeaBattleBoard(BaseModel):
    # Свои корабли — целиком; у соперника — только потопленные (в конце — все).
    ships: list[list[int]]
    # Выстрелы по доске: {клетка: miss|hit}; ключи строкой — так JSON.
    shots: dict[str, Literal["miss", "hit"]]
    # Куда били последней серией (подсветить свежие выстрелы).
    recent: list[int]


class SeaBattleOut(BaseModel):
    """Партия глазами игрока: свой флот видно, чужой — только подбитый."""

    code: str
    status: SeaBattleStatus
    vs_bot: bool
    version: int
    seat: int | None
    can_join: bool
    me: SeaBattlePlayer | None
    opponent: SeaBattlePlayer | None
    my_board: SeaBattleBoard | None
    enemy_board: SeaBattleBoard | None
    my_turn: bool
    result: Literal["win", "lose"] | None
    ready: DurakReady | None
    invite_url: str | None
    chat_invite: DurakChatInvite


class SeaBattleListItem(BaseModel):
    code: str
    status: SeaBattleStatus
    vs_bot: bool
    opponent_name: str | None
    my_turn: bool
