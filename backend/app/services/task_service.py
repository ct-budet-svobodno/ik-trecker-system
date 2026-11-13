import datetime

from sqlalchemy.orm import Session

from app.models.task import Task, TaskComment, TaskStatus
from app.models.user import LeadershipPosition, User, UserRole
from app.repositories import task_repository
from app.schemas.task import TaskCommentCreate, TaskCreate, TaskOut, TaskUpdate
from app.services import push_service
from app.services.exceptions import (
    PrivateTaskAccessError,
    TaskAccessError,
    TaskAssigneeError,
    TaskCommentNotFoundError,
    TaskFieldNotEditableError,
    TaskNotFoundError,
    TaskReminderError,
)

EMPLOYEE_EDITABLE_FIELDS = {"status"}
# Не чаще раза в столько минут — чтобы кнопка не превращалась в спам.
REMIND_COOLDOWN_MINUTES = 30
STATUS_WORDS = {TaskStatus.IN_REVIEW: "сдал(а) на проверку", TaskStatus.DONE: "выполнил(а)"}


def can_assign_private(user: User) -> bool:
    """Личные поручения выдаёт руководство: админ или держатель должности."""
    return user.role == UserRole.ADMIN or user.leadership_position is not None


def sees_all_private(user: User) -> bool:
    """Кто видит все личные поручения, а не только свои: админы и секретарь."""
    return user.role == UserRole.ADMIN or user.leadership_position == LeadershipPosition.SECRETARY


def _is_leadership(user: User) -> bool:
    return user.role == UserRole.ADMIN or user.leadership_position is not None


def can_issue_to(db: Session, user: User, direction_id: int | None) -> bool:
    """ТЗ выдают в своё направление: руководитель — туда, где он руководитель;
    админы и руководство (должности) — в любое."""
    return _is_leadership(user) or task_repository.heads_direction(db, user.id, direction_id)


def can_manage(task: Task, user: User) -> bool:
    """Кто правит и удаляет задачу. Поручение — только автор. ТЗ — выдавший,
    руководитель его направления, админы и руководство."""
    if task.is_checklist or task.is_private:
        return task.created_by_id == user.id
    if _is_leadership(user) or task.created_by_id == user.id:
        return True
    return task.direction is not None and any(h.id == user.id for h in task.direction.heads)


def _participants(task: Task) -> set[int]:
    """Кого касается задача: выдавший и исполнители."""
    ids = {task.created_by_id, *(a.user_id for a in task.assignees)}
    if task.assignee_id is not None:
        ids.add(task.assignee_id)
    return ids


def can_comment(task: Task, user: User) -> bool:
    """Обсуждают участники и те, кто задачей управляет; остальные только читают."""
    return user.id in _participants(task) or can_manage(task, user)


def list_tasks_for(db: Session, viewer: User) -> list[Task]:
    return task_repository.list_visible_for(
        db, viewer, sees_all_private=sees_all_private(viewer)
    )


def get_visible(db: Session, viewer: User, task_id: int) -> Task:
    # Чужое личное поручение для пользователя не существует: 404, а не 403.
    task = task_repository.get_visible(
        db, viewer, task_id, sees_all_private=sees_all_private(viewer)
    )
    if task is None:
        raise TaskNotFoundError("Задача не найдена")
    return task


def overall_status(statuses: list[TaskStatus]) -> TaskStatus:
    """Сводный статус поручения: готово — когда сделали все; новое — пока никто
    не начал; на проверке — когда все либо сдали, либо уже готовы."""
    if not statuses:
        return TaskStatus.TODO
    if all(s == TaskStatus.DONE for s in statuses):
        return TaskStatus.DONE
    if all(s == TaskStatus.TODO for s in statuses):
        return TaskStatus.TODO
    if all(s in (TaskStatus.IN_REVIEW, TaskStatus.DONE) for s in statuses):
        return TaskStatus.IN_REVIEW
    return TaskStatus.IN_PROGRESS


def view(task: Task, viewer: User) -> TaskOut:
    """Задача глазами смотрящего: исполнитель поручения видит свой статус
    (по нему строятся его колонки и прогресс), остальные — сводный."""
    out = TaskOut.model_validate(task)
    out.overall_status = task.status
    out.comments_count = len(task.comments)
    out.can_manage = can_manage(task, viewer)
    out.can_comment = can_comment(task, viewer)
    if task.is_private:
        mine = next((a for a in task.assignees if a.user_id == viewer.id), None)
        if mine is not None:
            out.status = mine.status
    return out


def _notify_assignees(db: Session, task: Task, actor: User, user_ids: list[int]) -> None:
    for user_id in user_ids:
        if user_id is None or user_id == actor.id:
            continue
        push_service.send_to_user(
            db,
            user_id,
            title="Вам выдали чек-лист" if task.is_checklist else "Вам дали личное поручение" if task.is_private else "Вам выдали ТЗ",
            body=task.title,
            url=task_url(task),
        )


def _check_users(db: Session, user_ids: list[int]) -> None:
    if not task_repository.users_exist(db, user_ids):
        raise TaskAssigneeError("Исполнитель не найден")


def create_task(db: Session, task_create: TaskCreate, created_by: User) -> Task:
    if task_create.is_checklist:
        if task_create.assignee_id == created_by.id:
            raise TaskAssigneeError("Назначьте чек-лист другому человеку")
    elif task_create.is_private and not can_assign_private(created_by):
        raise PrivateTaskAccessError("Личные поручения выдаёт только руководство")
    elif not task_create.is_private and not can_issue_to(db, created_by, task_create.direction_id):
        raise TaskAccessError("ТЗ можно выдавать только в направление, которым вы руководите")
    if task_create.assignee_id is not None:
        _check_users(db, task_create.assignee_ids or [task_create.assignee_id])
    task = task_repository.create(
        db,
        title=task_create.title,
        description=task_create.description,
        direction_id=task_create.direction_id,
        priority=task_create.priority,
        assignee_id=task_create.assignee_id,
        due_date=task_create.due_date,
        created_by_id=created_by.id,
        is_private=task_create.is_private,
        is_checklist=task_create.is_checklist,
    )
    if task.is_private:
        task_repository.set_assignees(db, task, task_create.assignee_ids)
        db.commit()
        db.refresh(task)
    _notify_assignees(db, task, created_by, [a.user_id for a in task.assignees] or [task.assignee_id])
    return task


def update_task(db: Session, task: Task, task_update: TaskUpdate, current_user: User) -> Task:
    fields = task_update.model_dump(exclude_unset=True)

    if task.is_checklist:
        if "status" in fields and fields["status"] not in (TaskStatus.TODO, TaskStatus.IN_PROGRESS, TaskStatus.DONE):
            raise TaskFieldNotEditableError("У чек-листа три статуса: не начато, в работе, сделано")
        if current_user.id == task.assignee_id and current_user.id != task.created_by_id:
            if set(fields) - EMPLOYEE_EDITABLE_FIELDS:
                raise TaskFieldNotEditableError("Исполнитель меняет только статус чек-листа")
            return task_repository.update_fields(db, task, fields)
        if current_user.id != task.created_by_id:
            raise TaskFieldNotEditableError("Чек-лист меняют только автор и исполнитель")
        if "status" in fields and current_user.id != task.assignee_id:
            raise TaskFieldNotEditableError("Статус чек-листа меняет исполнитель")
        if "direction_id" in fields and fields["direction_id"] is not None:
            raise TaskFieldNotEditableError("У чек-листа нет направления")
        if "assignee_ids" in fields or fields.get("assignee_id") is None and "assignee_id" in fields:
            raise TaskFieldNotEditableError("Чек-листу нужен один исполнитель")
        if "due_date" in fields and fields["due_date"] is None:
            raise TaskFieldNotEditableError("Чек-листу нужен дедлайн")
        if fields.get("assignee_id") is not None:
            if fields["assignee_id"] == current_user.id:
                raise TaskAssigneeError("Назначьте чек-лист другому человеку")
            _check_users(db, [fields["assignee_id"]])
        reassigned = "assignee_id" in fields and fields["assignee_id"] != task.assignee_id
        task = task_repository.update_fields(db, task, fields)
        if reassigned:
            _notify_assignees(db, task, current_user, [task.assignee_id])
        return task

    if task.is_private:
        return _update_private(db, task, fields, current_user)

    if "assignee_ids" in fields:
        raise TaskFieldNotEditableError("Несколько исполнителей бывает только у поручения")

    if can_manage(task, current_user):
        if "direction_id" in fields:
            if fields["direction_id"] is None:
                raise TaskFieldNotEditableError("У ТЗ должно быть направление")
            if not can_issue_to(db, current_user, fields["direction_id"]):
                raise TaskAccessError("Перенести ТЗ можно только в своё направление")
        if fields.get("assignee_id") is not None:
            _check_users(db, [fields["assignee_id"]])
        reassigned = (
            "assignee_id" in fields and fields["assignee_id"] not in (None, task.assignee_id)
        )
        task = task_repository.update_fields(db, task, fields)
        if reassigned:
            _notify_assignees(db, task, current_user, [task.assignee_id])
        return task

    if task.assignee_id != current_user.id:
        raise TaskFieldNotEditableError(
            "Менять ТЗ могут исполнитель, выдавший, руководитель направления и админы"
        )
    disallowed = set(fields) - EMPLOYEE_EDITABLE_FIELDS
    if disallowed:
        raise TaskFieldNotEditableError(
            f"Исполнитель может изменять только статус задачи (недопустимые поля: {', '.join(sorted(disallowed))})"
        )
    return task_repository.update_fields(db, task, fields)


def _update_private(db: Session, task: Task, fields: dict, current_user: User) -> Task:
    """Поручение правит его автор (в том числе состав исполнителей); исполнитель
    двигает только свой статус. Направление поручению не назначается."""
    if "direction_id" in fields and fields["direction_id"] is not None:
        raise TaskFieldNotEditableError("У личного поручения нет направления")
    mine = next((a for a in task.assignees if a.user_id == current_user.id), None)

    if current_user.id == task.created_by_id:
        if "assignee_id" in fields:
            assignee_id = fields.pop("assignee_id")
            if assignee_id is None:
                raise TaskFieldNotEditableError("Личному поручению нужен исполнитель")
            fields.setdefault("assignee_ids", [assignee_id])
        added: list[int] = []
        if "assignee_ids" in fields:
            ids = fields.pop("assignee_ids")
            _check_users(db, ids)
            added = task_repository.set_assignees(db, task, ids)
        if "status" in fields:
            # Автор двигает поручение целиком: например, принимает работу у всех.
            status = fields.pop("status")
            for assignee in task.assignees:
                assignee.status = status
        fields["status"] = overall_status([a.status for a in task.assignees])
        task = task_repository.update_fields(db, task, fields)
        _notify_assignees(db, task, current_user, added)
        return task

    # Админы и секретарь поручение видят, но не правят — это дело автора и исполнителей.
    if mine is None:
        raise TaskFieldNotEditableError("Поручение меняют только автор и исполнители")
    disallowed = set(fields) - EMPLOYEE_EDITABLE_FIELDS
    if disallowed:
        raise TaskFieldNotEditableError("В поручении исполнитель может менять только свой статус")
    if "status" in fields and fields["status"] != mine.status:
        mine.status = fields["status"]
        # Автору — весточка, когда исполнитель сдал свою часть.
        if mine.status in STATUS_WORDS:
            push_service.send_to_user(
                db,
                task.created_by_id,
                title=f"{current_user.full_name} {STATUS_WORDS[mine.status]} поручение",
                body=task.title,
                url=task_url(task),
            )
    return task_repository.update_fields(
        db, task, {"status": overall_status([a.status for a in task.assignees])}
    )


def task_url(task: Task) -> str:
    """Ссылка, открывающая карточку задачи (TasksView понимает ?task=)."""
    return f"/tasks?task={task.id}"


def _utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.UTC).replace(tzinfo=None)


def remind(db: Session, task: Task, current_user: User) -> Task:
    """Напомнить исполнителям поручения, кто ещё не сдал свою часть
    (сдавшим на проверку и сделавшим напоминать нечего)."""
    if not task.is_private or task.created_by_id != current_user.id:
        raise TaskReminderError("Напомнить о поручении может только его автор")
    waiting = (TaskStatus.IN_REVIEW, TaskStatus.DONE)
    targets = [a.user_id for a in task.assignees if a.status not in waiting]
    if not targets:
        raise TaskReminderError("Все исполнители уже сдали поручение")
    if task.reminded_at is not None:
        wait = task.reminded_at + datetime.timedelta(minutes=REMIND_COOLDOWN_MINUTES) - _utcnow()
        if wait.total_seconds() > 0:
            minutes = max(1, round(wait.total_seconds() / 60))
            raise TaskReminderError(f"Уже напомнили — снова можно через {minutes} мин")
    body = task.title
    if task.due_date:
        body += f" · срок {task.due_date.strftime('%d.%m')}"
    push_service.send_to_users(
        db,
        targets,
        title=f"Напоминание от {current_user.full_name}",
        body=body,
        url=task_url(task),
    )
    return task_repository.update_fields(db, task, {"reminded_at": _utcnow()})


def delete_task(db: Session, task: Task, current_user: User) -> None:
    """Удалить ТЗ или поручение. Исполнителям — весточка, что делать не нужно."""
    if not can_manage(task, current_user):
        raise TaskAccessError("Удалить может выдавший, руководитель направления или админ")
    title = "Поручение отменено" if task.is_private else "ТЗ отменено"
    targets = [uid for uid in {*(a.user_id for a in task.assignees), task.assignee_id}
               if uid is not None and uid != current_user.id]
    body = task.title
    task_repository.delete_task(db, task)
    if targets:
        push_service.send_to_users(db, targets, title=title, body=body, url="/")


# ── Обсуждение ──

def list_comments(db: Session, task: Task) -> list[TaskComment]:
    return task_repository.list_comments(db, task.id)


def add_comment(db: Session, task: Task, payload: TaskCommentCreate, author: User) -> TaskComment:
    if not can_comment(task, author):
        raise TaskAccessError("Обсуждать ТЗ могут исполнитель, выдавший и руководители")
    parent_id = payload.parent_id
    if parent_id is not None:
        parent = task_repository.get_comment(db, task.id, parent_id)
        if parent is None:
            raise TaskCommentNotFoundError("Комментарий не найден")
        parent_id = parent.parent_id or parent.id  # ответы — один уровень
    comment = task_repository.add_comment(db, task, author.id, payload.body.strip(), parent_id)
    targets = [uid for uid in _participants(task) if uid != author.id]
    if targets:
        preview = comment.body if len(comment.body) <= 120 else comment.body[:117] + "…"
        push_service.send_to_users(
            db,
            targets,
            title=f"{author.full_name} · {task.title}",
            body=preview,
            url=task_url(task),
        )
    return comment


def delete_comment(db: Session, task: Task, comment_id: int, current_user: User) -> None:
    comment = task_repository.get_comment(db, task.id, comment_id)
    if comment is None:
        raise TaskCommentNotFoundError("Комментарий не найден")
    if comment.author_id != current_user.id and not can_manage(task, current_user):
        raise TaskAccessError("Удалить можно только свой комментарий")
    task_repository.delete_comment(db, comment)
