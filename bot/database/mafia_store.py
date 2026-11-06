"""Партии в отдельном файле внутри существующего Docker-тома database/."""
import json
from pathlib import Path

import aiosqlite
from utils.mafia import Game

PATH = Path('database/mafia_sessions.db')


async def load():
    PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(PATH) as db:
        await db.execute('CREATE TABLE IF NOT EXISTS games (chat_id INTEGER PRIMARY KEY, state TEXT NOT NULL)')
        await db.commit()
        PATH.chmod(0o600)
        async with db.execute('SELECT state FROM games') as cursor:
            return [Game.loads(json.loads(row[0])) for row in await cursor.fetchall()]


async def save(game):
    async with aiosqlite.connect(PATH) as db:
        await db.execute('INSERT INTO games VALUES (?, ?) ON CONFLICT(chat_id) DO UPDATE SET state=excluded.state',
                         (game.chat_id, json.dumps(game.dumps(), ensure_ascii=False)))
        await db.commit()


async def delete(game):
    async with aiosqlite.connect(PATH) as db:
        await db.execute('DELETE FROM games WHERE chat_id=?', (game.chat_id,))
        await db.commit()
