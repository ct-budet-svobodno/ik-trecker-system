from typing import Literal

from pydantic import BaseModel, Field

from app.models.durak_game import DurakGameStatus


class DurakCreate(BaseModel):
    vs_bot: bool = False


class DurakMove(BaseModel):
    # attack — пойти/подкинуть; defend — побить target картой card;
    # take — «беру»; finish — «бито»/«забирай»; resign — сдаться.
    action: Literal["attack", "defend", "take", "finish", "resign"]
    card: int | None = Field(default=None, ge=0, le=51)
    target: int | None = Field(default=None, ge=0, le=51)
    # Версия партии, которую видел игрок: ход по устаревшей картине — 409.
    version: int


class DurakPlayer(BaseModel):
    id: int | None  # None — бот
    full_name: str
    cards: int


class DurakLegal(BaseModel):
    attack: list[int] = []
    # {непокрытая карта: чем её можно побить}; ключи строкой — так JSON.
    defend: dict[str, list[int]] = {}
    take: bool = False
    finish: bool = False


class DurakReady(BaseModel):
    me: bool
    opponent: bool


class DurakChatInvite(BaseModel):
    available: bool  # можно позвать в чат актива (создатель, ждём соперника)
    sent: bool  # приглашение уже висит в чате


class DurakOut(BaseModel):
    """Партия глазами конкретного игрока: свою руку видно, чужую — нет."""

    code: str
    status: DurakGameStatus
    vs_bot: bool
    version: int
    # Место смотрящего: 0/1, None — зритель (может присоединиться, если ждём игрока).
    seat: int | None
    can_join: bool
    me: DurakPlayer | None
    opponent: DurakPlayer | None
    hand: list[int]
    table: list[list[int | None]]
    trump: int
    trump_card: int | None  # None — прикуп кончился, козырь только мастью
    talon: int
    beaten: int
    attacker: int
    taking: bool
    my_turn: bool
    legal: DurakLegal
    # Итог для смотрящего: win / lose / draw, None — партия идёт.
    result: Literal["win", "lose", "draw"] | None
    # Идёт проверка готовности (status=ready_check) — кто уже подтвердил.
    ready: DurakReady | None
    # Ссылка-приглашение: в Telegram открывает партию (пока ждём соперника).
    invite_url: str | None
    chat_invite: DurakChatInvite


class DurakListItem(BaseModel):
    code: str
    status: DurakGameStatus
    vs_bot: bool
    opponent_name: str | None
    my_turn: bool
