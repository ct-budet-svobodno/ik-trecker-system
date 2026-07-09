class InvalidCredentialsError(Exception):
    pass


class UsernameTakenError(Exception):
    pass


class TaskFieldNotEditableError(Exception):
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
