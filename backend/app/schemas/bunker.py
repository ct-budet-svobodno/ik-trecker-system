from typing import Literal

from pydantic import BaseModel, Field

from app.models.bunker_game import BunkerStatus
from app.schemas.durak import DurakChatInvite

Category = Literal["profession", "biology", "health", "hobby", "phobia", "baggage", "fact"]


class BunkerMove(BaseModel):
    # reveal — открыть свою карту (category); vote — голос против игрока (target);
    # advance — «Дальше» от создателя; stop — создатель останавливает партию.
    action: Literal["reveal", "vote", "advance", "stop"]
    category: Category | None = None
    target: int | None = None
    # Версия, которую видел игрок. Сверяем только для advance/stop: открытия
    # и голоса игроков друг от друга не зависят.
    version: int


class BunkerPlayerOut(BaseModel):
    seat: int
    id: int
    full_name: str
    is_host: bool
    out: bool
    out_round: int | None
    # Открытые карты; свои игрок видит все — закрытые помечены в hidden.
    cards: dict[str, str]
    hidden: list[str]
    revealed_now: bool  # открыл карту в этом раунде
    voted: bool  # уже проголосовал (за кого — тайна до итога)


class BunkerCatastrophe(BaseModel):
    title: str
    text: str
    duration: str


class BunkerShelter(BaseModel):
    area: int
    supplies: str
    rooms: list[str]


class BunkerVoteResult(BaseModel):
    votes: dict[str, int]  # место голосовавшего → место, против кого
    leaders: list[int]
    out: int | None
    tie: bool
    lot: bool  # повторная ничья решена жребием


class BunkerOut(BaseModel):
    code: str
    status: BunkerStatus
    version: int
    seat: int | None
    is_host: bool
    observer: bool  # ведущий стола, который сам не играет: видит все карты
    title: str | None  # стол из админки
    can_join: bool
    min_players: int
    max_players: int
    players: list[BunkerPlayerOut]
    catastrophe: BunkerCatastrophe | None
    bunker: BunkerShelter | None
    seats: int | None  # мест в бункере
    round: int | None
    rounds: int
    phase: Literal["reveal", "discuss", "vote", "result", "over"] | None
    phase_seconds: float  # сколько идёт текущая фаза
    to_exclude: int  # сколько ещё выгнать в этом раунде
    candidates: list[int] | None  # переголосование: только за них
    my_vote: int | None
    last_vote: BunkerVoteResult | None
    invite_url: str | None
    chat_invite: DurakChatInvite


class BunkerListItem(BaseModel):
    code: str
    title: str | None
    status: BunkerStatus
    players: int
    my_turn: bool


class BunkerTableIn(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    # Telegram-теги игроков: «@tag» или «tag», можно строкой через запятую.
    tags: list[str] = Field(default_factory=list, max_length=64)
    # Ведущий; пусто — тот, кто заводит стол. Не в списке игроков — ведёт, не играя.
    host_tag: str | None = None


class BunkerTablePerson(BaseModel):
    id: int
    full_name: str
    tag: str | None
    out: bool = False


class BunkerTableOut(BaseModel):
    code: str
    title: str
    status: BunkerStatus
    host: BunkerTablePerson
    host_plays: bool
    players: list[BunkerTablePerson]
    round: int | None
    phase: str | None


class BunkerTableSaved(BaseModel):
    table: BunkerTableOut
    missing: list[str]  # теги, которых нет среди одобренных аккаунтов
