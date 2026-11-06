"""Правила текстовой мафии, без Telegram и доступа к базе."""
import random
import secrets
import time
from collections import Counter
from dataclasses import asdict, dataclass, field

MIN_PLAYERS, MAX_PLAYERS = 5, 16
DURATION = {'lobby': 600, 'night': 90, 'day': 120, 'voting': 60}
ROLE_NAMES = {'mafia': 'Мафия', 'civilian': 'Мирный житель', 'doctor': 'Доктор', 'commissar': 'Комиссар'}


@dataclass
class Player:
    uid: int
    name: str
    role: str = 'civilian'
    alive: bool = True


@dataclass
class Game:
    chat_id: int
    host_id: int
    thread_id: int | None = None
    token: str = field(default_factory=lambda: secrets.token_hex(4))
    phase: str = 'lobby'
    turn: int = 0
    deadline: float = field(default_factory=lambda: time.time() + DURATION['lobby'])
    players: list[Player] = field(default_factory=list)
    actions: dict[int, int] = field(default_factory=dict)
    votes: dict[int, int] = field(default_factory=dict)
    winner: str | None = None
    idle_phases: int = 0

    def dumps(self):
        return asdict(self)

    @classmethod
    def loads(cls, data):
        data = dict(data)
        data['players'] = [Player(**p) for p in data['players']]
        for key in ('actions', 'votes'):
            data[key] = {int(k): v for k, v in data[key].items()}
        return cls(**data)

    def player(self, uid):
        p = next((p for p in self.players if p.uid == uid), None)
        if p is None:
            raise ValueError('Вы не участвуете в этой партии.')
        return p

    @property
    def alive(self):
        return [p for p in self.players if p.alive]

    def join(self, uid, name):
        if self.phase != 'lobby':
            raise ValueError('Партия уже началась.')
        if any(p.uid == uid for p in self.players):
            return
        if len(self.players) >= MAX_PLAYERS:
            raise ValueError('Все 16 мест заняты.')
        self.players.append(Player(uid, name[:48]))

    def leave(self, uid):
        if self.phase != 'lobby':
            raise ValueError('После раздачи ролей выйти нельзя.')
        self.player(uid)
        self.players = [p for p in self.players if p.uid != uid]
        if self.players and uid == self.host_id:
            self.host_id = self.players[0].uid

    def set_phase(self, phase, now=None):
        self.phase = phase
        self.turn += 1
        self.deadline = (time.time() if now is None else now) + DURATION.get(phase, 0)

    def start(self, rng=None):
        if self.phase != 'lobby':
            raise ValueError('Партия уже началась.')
        n = len(self.players)
        if not MIN_PLAYERS <= n <= MAX_PLAYERS:
            raise ValueError('Для начала нужно от 5 до 16 игроков.')
        count = 1 if n < 7 else 2 if n < 11 else 3
        roles = ['mafia'] * count + ['doctor', 'commissar'] + ['civilian'] * (n-count-2)
        (rng or random.SystemRandom()).shuffle(roles)
        for player, role in zip(self.players, roles):
            player.role = role
        self.set_phase('night')

    def targets(self, uid, voting=False):
        player = self.player(uid)
        if not player.alive:
            return []
        if voting:
            return [p for p in self.alive if p.uid != uid]
        if player.role == 'civilian':
            return []
        if player.role == 'mafia':
            return [p for p in self.alive if p.role != 'mafia']
        if player.role == 'commissar':
            return [p for p in self.alive if p.uid != uid]
        return self.alive  # Доктор может лечить себя.

    def choose(self, uid, target, *, turn, voting=False):
        if turn != self.turn or self.phase != ('voting' if voting else 'night'):
            raise ValueError('Эта кнопка от предыдущего этапа.')
        p = self.player(uid)
        if not p.alive:
            raise ValueError('Вы уже выбыли из партии.')
        if not voting and p.role == 'civilian':
            raise ValueError('Мирные жители ночью спят.')
        if target != 0 and target not in {p.uid for p in self.targets(uid, voting)}:
            raise ValueError('Нельзя выбрать этого игрока.')
        (self.votes if voting else self.actions)[uid] = target

    def ready(self):
        if self.phase == 'night':
            return all(p.uid in self.actions for p in self.alive if p.role != 'civilian')
        if self.phase == 'voting':
            return all(p.uid in self.votes for p in self.alive)
        return False

    @staticmethod
    def majority(choices):
        counts = Counter(choices)
        if not counts:
            return 0
        best = max(counts.values())
        winners = [uid for uid, count in counts.items() if count == best]
        return winners[0] if len(winners) == 1 else 0

    def finish_if_won(self):
        count = sum(p.role == 'mafia' for p in self.alive)
        if count == 0:
            self.winner = 'civilians'
        elif count >= len(self.alive) - count:
            self.winner = 'mafia'
        if self.winner:
            self.set_phase('end')

    def advance(self):
        killed, checks = None, []
        if self.phase in ('night', 'voting'):
            choices = self.actions if self.phase == 'night' else self.votes
            self.idle_phases = 0 if choices else self.idle_phases + 1
        if self.phase == 'night':
            target = self.majority(self.actions[p.uid] for p in self.alive
                                   if p.role == 'mafia' and p.uid in self.actions)
            healed = {self.actions[p.uid] for p in self.alive
                      if p.role == 'doctor' and p.uid in self.actions}
            for p in self.alive:
                if p.role == 'commissar' and self.actions.get(p.uid):
                    checked = self.player(self.actions[p.uid])
                    checks.append((p.uid, checked.uid, checked.role == 'mafia'))
            if target and target not in healed:
                self.player(target).alive = False
                killed = target
            self.actions.clear()
            self.set_phase('day')
        elif self.phase == 'day':
            self.votes.clear()
            self.set_phase('voting')
        elif self.phase == 'voting':
            target = self.majority(self.votes.values())
            if target:
                self.player(target).alive = False
                killed = target
            self.votes.clear()
            self.set_phase('night')
        else:
            raise ValueError('Сейчас нельзя сменить этап.')
        self.finish_if_won()
        return killed, checks
