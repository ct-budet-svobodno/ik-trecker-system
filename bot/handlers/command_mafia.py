"""Мафия в группе: публичные дни, тайные роли и действия в личке."""
import asyncio
import contextlib
import html
import logging
import time

from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import BaseFilter
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from database import mafia_store
from utils.mafia import Game, ROLE_NAMES

mafia_router = Router()
logger = logging.getLogger(__name__)
GAMES: dict[int, Game] = {}
LOCK = asyncio.Lock()
WORKER = None

RULES = (
    '🎭 <b>Мафия в чате</b>\n'
    'От 5 до 16 игроков. <code>!мафия</code> в группе — создать лобби или показать партию.\n'
    'Жми «Вступить»: бот проверит, что может написать тебе в личку. '
    'Если не может — открой его, нажми Start и вернись к кнопке в лобби.\n\n'
    'Ночью мафия выбирает жертву, доктор лечит (можно себя), комиссар проверяет игрока. '
    'Роли и ночные кнопки приходят только в личку. Ночь — 90 секунд.\n'
    'Днём обсуждаем 2 минуты, затем голосуем кнопками в группе 1 минуту. '
    'Равенство голосов или победа «Пропустить» — никто не выбывает. '
    'Пропущенный ход не учитывается. Когда все сделали выбор, этап завершается раньше.\n'
    'Мирные побеждают, когда мафии нет; мафия — когда её не меньше остальных. '
    'Выбывшие не ходят и не голосуют; просим их не подсказывать в чате.\n\n'
    '<code>!мафия старт</code> — раздать роли (создатель лобби).\n'
    '<code>!мафия стоп</code> — отменить (создатель или администратор чата).\n'
    '<code>!мафия правила</code> — эти правила. Лобби ждёт 10 минут. '
    'После двух полных кругов без ходов и голосов партия закроется.'
)


class MafiaCommand(BaseFilter):
    async def __call__(self, message: Message):
        text = (message.text or '').strip().casefold()
        if not text:
            return False
        cmd = text.split(maxsplit=1)[0]
        if '@' in cmd:
            cmd, mention = cmd.split('@', 1)
            if mention != (await message.bot.me()).username.casefold():
                return False
        return cmd in ('!мафия', '/mafia')


def button(game, text, action, target=0):
    return InlineKeyboardButton(text=text, callback_data=f'mf:{game.token}:{game.turn}:{action}:{target}')


def markup(rows):
    return InlineKeyboardMarkup(inline_keyboard=rows)


def name(player):
    return html.escape(player.name)


def public_text(game):
    labels = {'lobby': 'Набор игроков', 'night': 'Ночь', 'day': 'Обсуждение', 'voting': 'Голосование'}
    text = f"🎭 <b>Мафия · {labels.get(game.phase, 'Конец')}</b>\n"
    if game.phase == 'lobby':
        text += f'Игроки: {len(game.players)}/16 (нужно минимум 5).\n'
        text += '\n'.join(f'{i}. {name(p)}' for i, p in enumerate(game.players, 1)) or 'Пока никого.'
        text += '\nПеред вступлением открой личку бота и нажми Start. Начинает создатель лобби.'
    else:
        text += 'В игре: ' + ', '.join(name(p) for p in game.alive)
        text += '\nОсталось: ' + str(max(0, int(game.deadline-time.time()))) + ' сек.'
        if game.phase == 'night':
            text += '\nГород спит. Действия — в личке бота.'
        elif game.phase == 'day':
            text += '\nОбсуждайте, кто может быть мафией.'
        elif game.phase == 'voting':
            text += f'\nГолосов: {len(game.votes)}/{len(game.alive)}. Выбор можно изменить до конца этапа.'
    return text


def public_kb(game):
    if game.phase == 'lobby':
        return markup([[button(game, 'Вступить', 'join'), button(game, 'Выйти', 'leave')],
                       [button(game, 'Начать', 'start'), button(game, 'Отменить', 'stop')],
                       [button(game, 'Правила', 'rules')]])
    if game.phase == 'voting':
        rows = [[button(game, p.name, 'vote', p.uid)] for p in game.alive]
        rows.append([button(game, 'Пропустить', 'vote')])
        return markup(rows)
    if game.phase == 'day':
        return markup([[button(game, 'Перейти к голосованию', 'next')]])
    return None


async def announce(bot, game, text=None, kb=None):
    return await bot.send_message(game.chat_id, text or public_text(game), parse_mode='HTML',
                                  reply_markup=kb, message_thread_id=game.thread_id)


async def show(bot, game):
    await announce(bot, game, kb=public_kb(game))


async def dm(bot, uid, text, kb=None):
    try:
        await bot.send_message(uid, text, parse_mode='HTML', reply_markup=kb)
        return True
    except TelegramAPIError:
        return False


async def remove(game):
    await mafia_store.delete(game)
    GAMES.pop(game.chat_id, None)


async def finish(bot, game, cancelled=False):
    if cancelled:
        text = '🎭 Партия отменена. Новая — <code>!мафия</code>.'
    else:
        text = '🎭 <b>Победили ' + ('мирные!' if game.winner == 'civilians' else 'мафия!') + '</b>\n'
        text += '\n'.join(f'{name(p)} — {ROLE_NAMES[p.role]}' for p in game.players)
    await remove(game)
    await announce(bot, game, text)


async def night_prompts(bot, game):
    for p in game.alive:
        if p.role == 'civilian':
            continue
        verb = {'mafia': 'Выбери жертву', 'doctor': 'Кого лечить?', 'commissar': 'Кого проверить?'}[p.role]
        rows = [[button(game, target.name, 'act', target.uid)] for target in game.targets(p.uid)]
        rows.append([button(game, 'Пропустить', 'act')])
        await dm(bot, p.uid, f'🌙 <b>Ночь · {verb}</b>\n90 секунд. До конца этапа выбор можно изменить.', markup(rows))


async def advance(bot, game):
    previous = game.phase
    killed, checks = game.advance()
    await mafia_store.save(game)
    if game.idle_phases >= 4:
        await finish(bot, game, cancelled=True)
        return
    for uid, target, is_mafia in checks:
        await dm(bot, uid, f"🔎 {name(game.player(target))}: <b>{'мафия' if is_mafia else 'не мафия'}</b>.")
    if previous in ('night', 'voting'):
        if killed:
            p = game.player(killed)
            text = f"{'🌅 Ночью погиб' if previous == 'night' else '⚖️ По голосованию выбыл'} {name(p)} — {ROLE_NAMES[p.role]}."
        else:
            text = '🌅 Ночью никто не погиб.' if previous == 'night' else '⚖️ Никто не выбыл: ничья, пропуск или нет голосов.'
        await announce(bot, game, text)
    if game.winner:
        await finish(bot, game)
    else:
        await show(bot, game)
        if game.phase == 'night':
            await night_prompts(bot, game)


async def start_game(bot, game, uid):
    if uid != game.host_id:
        raise ValueError('Начать может только создатель лобби.')
    game.start()
    # Сохраняем до рассылки. При аварии бот восстановит этап без новой раздачи.
    await mafia_store.save(game)
    for p in game.players:
        text = f'🎭 Твоя роль: <b>{ROLE_NAMES[p.role]}</b>.'
        if p.role == 'mafia':
            text += '\nМафия: ' + ', '.join(name(other) for other in game.players if other.role == 'mafia')
        if not await dm(bot, p.uid, text):
            await finish(bot, game, cancelled=True)
            await announce(bot, game, 'Не удалось доставить всем роли. Откройте личку бота, нажмите Start и создайте новую партию.')
            return
    await show(bot, game)
    await night_prompts(bot, game)


async def may_stop(bot, game, uid):
    if uid == game.host_id:
        return True
    member = await bot.get_chat_member(game.chat_id, uid)
    return member.status in ('creator', 'administrator')


@mafia_router.message(MafiaCommand())
async def mafia_command(message: Message):
    if message.from_user is None or message.from_user.is_bot:
        return
    command = (message.text or '').strip().casefold().partition(' ')[2].strip()
    if message.chat.type not in ('group', 'supergroup') or command in ('правила', 'rules'):
        await message.answer(RULES, parse_mode='HTML')
        return
    if message.sender_chat:
        await message.answer('Для игры отправь команду от своего аккаунта, а не от имени канала.')
        return
    async with LOCK:
        game = GAMES.get(message.chat.id)
        try:
            if command in ('стоп', 'stop'):
                if not game:
                    raise ValueError('В этом чате нет партии.')
                if not await may_stop(message.bot, game, message.from_user.id):
                    raise ValueError('Отменить может создатель или администратор чата.')
                await finish(message.bot, game, cancelled=True)
            elif command in ('старт', 'start'):
                if not game:
                    raise ValueError('Сначала создайте лобби: !мафия.')
                await start_game(message.bot, game, message.from_user.id)
            elif command in ('', 'статус', 'status'):
                if not game:
                    game = Game(message.chat.id, message.from_user.id, message.message_thread_id)
                    GAMES[game.chat_id] = game
                    await mafia_store.save(game)
                await show(message.bot, game)
            else:
                raise ValueError('Команды: !мафия, !мафия старт, !мафия стоп, !мафия правила.')
        except ValueError as exc:
            await message.answer(str(exc))


@mafia_router.callback_query(F.data == 'mafia_rules')
async def rules_callback(query: CallbackQuery):
    await query.answer()
    await dm(query.bot, query.from_user.id, RULES)


@mafia_router.callback_query(F.data.startswith('mf:'))
async def mafia_callback(query: CallbackQuery):
    try:
        _, token, turn, action, target = query.data.split(':')
        turn, target = int(turn), int(target)
    except (ValueError, AttributeError):
        await query.answer('Некорректная кнопка.')
        return
    async with LOCK:
        game = next((g for g in GAMES.values() if g.token == token), None)
        if game is None or turn != game.turn:
            await query.answer('Эта кнопка устарела. Напиши !мафия в чате.', show_alert=True)
            return
        uid = query.from_user.id
        try:
            private = query.message and query.message.chat.type == 'private'
            if action == 'act':
                if not private:
                    raise ValueError('Ночные действия — только в личке.')
            elif not query.message or query.message.chat.id != game.chat_id:
                raise ValueError('Эта кнопка работает только в чате партии.')
            if time.time() >= game.deadline:
                raise ValueError('Время этапа истекло. Обнови партию командой !мафия.')
            if action == 'rules':
                await query.answer()
                await dm(query.bot, uid, RULES)
                return
            if action == 'join':
                if game.phase != 'lobby':
                    raise ValueError('Набор уже закрыт.')
                if any(p.uid == uid for p in game.players):
                    await query.answer('Ты уже в лобби.')
                    return
                if len(game.players) >= 16:
                    raise ValueError('Все 16 мест заняты.')
                if any(any(p.uid == uid for p in other.players) for other in GAMES.values() if other is not game):
                    raise ValueError('Сначала закончи партию в другом чате.')
                if not await dm(query.bot, uid, '🎭 Ты вступаешь в мафию. Роль и ночные действия придут сюда после старта.'):
                    me = await query.bot.me()
                    await query.answer(url=f'https://t.me/{me.username}?start=mafia')
                    return
                game.join(uid, query.from_user.full_name)
            elif action == 'leave':
                game.leave(uid)
                if not game.players:
                    await query.answer('Ты вышел. Лобби закрыто.')
                    await finish(query.bot, game, cancelled=True)
                    return
            elif action == 'start':
                if game.phase != 'lobby' or uid != game.host_id or len(game.players) < 5:
                    raise ValueError('Начать может создатель; нужно минимум 5 игроков.')
                await query.answer()
                await start_game(query.bot, game, uid)
                return
            elif action == 'stop':
                if not await may_stop(query.bot, game, uid):
                    raise ValueError('Отменить может создатель или администратор чата.')
                await query.answer()
                await finish(query.bot, game, cancelled=True)
                return
            elif action == 'next':
                if uid != game.host_id or game.phase != 'day':
                    raise ValueError('Начать голосование может создатель во время обсуждения.')
                await query.answer()
                await advance(query.bot, game)
                return
            elif action in ('act', 'vote'):
                game.choose(uid, target, turn=turn, voting=action == 'vote')
                await mafia_store.save(game)
                await query.answer('Выбор принят.')
                if game.ready():
                    await advance(query.bot, game)
                return
            else:
                raise ValueError('Неизвестная кнопка.')
            await mafia_store.save(game)
            await query.answer('Готово.')
            try:
                await query.message.edit_text(public_text(game), parse_mode='HTML', reply_markup=public_kb(game))
            except TelegramAPIError:
                await show(query.bot, game)
        except ValueError as exc:
            await query.answer(str(exc), show_alert=True)


async def tick(bot):
    async with LOCK:
        for game in list(GAMES.values()):
            try:
                if game.phase == 'end':
                    await finish(bot, game)
                elif time.time() >= game.deadline:
                    if game.phase == 'lobby':
                        await finish(bot, game, cancelled=True)
                    else:
                        await advance(bot, game)
            except TelegramAPIError:
                logger.warning('Не удалось отправить этап мафии в чат %s', game.chat_id)


async def worker(bot):
    while True:
        await asyncio.sleep(3)
        try:
            await tick(bot)
        except Exception:
            logger.exception('Ошибка таймера мафии')


@mafia_router.startup()
async def startup(bot):
    global WORKER
    for game in await mafia_store.load():
        GAMES[game.chat_id] = game
        if game.phase not in ('lobby', 'end'):
            # Возвращаем время этапа после простоя; роли не перераздаются.
            from utils.mafia import DURATION
            game.deadline = time.time() + DURATION[game.phase]
            await mafia_store.save(game)
            try:
                for p in game.players:
                    text = f'🎭 Партия восстановлена. Твоя роль: <b>{ROLE_NAMES[p.role]}</b>.'
                    if p.role == 'mafia':
                        text += '\nМафия: ' + ', '.join(name(other) for other in game.players if other.role == 'mafia')
                    await dm(bot, p.uid, text)
                await show(bot, game)
                if game.phase == 'night':
                    await night_prompts(bot, game)
            except TelegramAPIError:
                logger.warning('Не удалось объявить восстановление мафии в чате %s', game.chat_id)
    WORKER = asyncio.create_task(worker(bot))


@mafia_router.shutdown()
async def shutdown():
    if WORKER:
        WORKER.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await WORKER
