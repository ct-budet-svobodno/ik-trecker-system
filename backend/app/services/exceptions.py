class InvalidCredentialsError(Exception):
    pass


class TelegramAuthError(Exception):
    """initData не прошла проверку или Telegram не настроен."""

    pass


class TelegramNotLinkedError(Exception):
    """Telegram-аккаунт ещё не привязан ни к одному пользователю трекера."""

    pass


class RegistrationPendingError(Exception):
    """Анкета из мини-аппа заполнена, но админ ещё не решил (или отклонил)."""

    def __init__(self, status: str, message: str):
        super().__init__(message)
        self.status = status


class RegistrationError(Exception):
    """Анкету не принять: кривые данные, фото не картинка, аккаунт уже есть."""

    pass


class LinkCodeError(Exception):
    """Код привязки Telegram неверный или устарел."""

    pass


class UsernameTakenError(Exception):
    pass


class TaskFieldNotEditableError(Exception):
    pass


class PrivateTaskAccessError(Exception):
    """Личные поручения выдаёт только руководство (админ или должность)."""

    pass


class TaskNotFoundError(Exception):
    pass


class UserNotFoundError(Exception):
    pass


class DirectionNotFoundError(Exception):
    pass


class LeadershipAccessError(Exception):
    """Нет прав ставить/менять запись в таймлайне руководства для этого направления."""

    pass


class EditorialAccessError(Exception):
    """Нет прав на действие в Редакции (SMM-календарь постов)."""

    pass


class EditorialPostNotFoundError(Exception):
    pass


class ZavodNotFoundError(Exception):
    """Доска, карточка или связь не найдена."""

    pass


class ZavodInvalidEdgeError(Exception):
    """Связь бессмысленна: сама на себя, дубль или между разными досками."""

    pass


class PersonalTodoNotFoundError(Exception):
    """Пункт личного списка не найден или принадлежит другому пользователю."""

    pass


class TaskAssigneeError(Exception):
    """Исполнитель не найден или неактивен."""

    pass


class TaskAccessError(Exception):
    """Нет прав на действие с ТЗ: выдать не в своё направление, править чужое и т. п."""

    pass


class TaskCommentNotFoundError(Exception):
    pass


class TaskReminderError(Exception):
    """Напомнить нельзя: не автор, все уже сделали или напоминали только что."""

    pass


class DurakGameNotFoundError(Exception):
    """Партии нет или она чужая и уже занята — для смотрящего не существует."""

    pass


class DurakMoveError(Exception):
    """Ход не по правилам, не в свою очередь или партия закончена."""

    pass


class DurakVersionConflictError(Exception):
    """Состояние партии поменялось, пока игрок думал: клиенту нужно перечитать."""

    pass


class SeaBattleNotFoundError(Exception):
    """Партии в морской бой нет или она чужая и уже занята."""

    pass


class SeaBattleMoveError(Exception):
    """Выстрел/расстановка не по правилам, не в свою очередь или партия закончена."""

    pass


class SeaBattleVersionConflictError(Exception):
    """Состояние партии поменялось, пока игрок думал: клиенту нужно перечитать."""

    pass


class BunkerNotFoundError(Exception):
    """Партии в «Бункер» нет или она чужая и уже началась."""

    pass


class BunkerMoveError(Exception):
    """Действие не по правилам: не та фаза, не создатель, партия закончена."""

    pass


class BunkerVersionConflictError(Exception):
    """Создатель жмёт «Дальше» по устаревшей картине: клиенту нужно перечитать."""

    pass


class BroadcastError(Exception):
    """Рассылку не отправить: бот выключен, уже идёт другая, нет Telegram у автора."""

    pass


class ChecklistError(Exception):
    """Чек-листы не подготовить или не разослать: уже разосланы, нет картинок, бот выключен."""

    pass


class SurveyError(Exception):
    """Анкету не сохранить, не отправить или не принять ответ: вопросы уже не поменять,
    анкета закрыта, ответ не подходит к вопросам."""

    pass
