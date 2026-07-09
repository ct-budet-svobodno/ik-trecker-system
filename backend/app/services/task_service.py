from sqlalchemy.orm import Session

from app.models.task import Task
from app.models.user import User, UserRole
from app.repositories import task_repository
from app.schemas.task import TaskCreate, TaskUpdate
from app.services import push_service
from app.services.exceptions import TaskFieldNotEditableError

EMPLOYEE_EDITABLE_FIELDS = {"status"}


def list_tasks_for(db: Session, viewer: User) -> list[Task]:
    return task_repository.list_visible_for(db, viewer)


def _notify_assignee(db: Session, task: Task, actor: User) -> None:
    if task.assignee_id and task.assignee_id != actor.id:
        push_service.send_to_user(
            db,
            task.assignee_id,
            title="Вам выдали ТЗ",
            body=task.title,
            url="/",
        )


def create_task(db: Session, task_create: TaskCreate, created_by: User) -> Task:
    task = task_repository.create(
        db,
        title=task_create.title,
        description=task_create.description,
        direction_id=task_create.direction_id,
        priority=task_create.priority,
        assignee_id=task_create.assignee_id,
        due_date=task_create.due_date,
        created_by_id=created_by.id,
    )
    _notify_assignee(db, task, created_by)
    return task


def update_task(db: Session, task: Task, task_update: TaskUpdate, current_user: User) -> Task:
    fields = task_update.model_dump(exclude_unset=True)

    if current_user.role in (UserRole.ADMIN, UserRole.MANAGER):
        reassigned = (
            "assignee_id" in fields and fields["assignee_id"] not in (None, task.assignee_id)
        )
        task = task_repository.update_fields(db, task, fields)
        if reassigned:
            _notify_assignee(db, task, current_user)
        return task

    if task.assignee_id != current_user.id:
        raise TaskFieldNotEditableError("Можно изменять только задачи, назначенные на вас")
    disallowed = set(fields) - EMPLOYEE_EDITABLE_FIELDS
    if disallowed:
        raise TaskFieldNotEditableError(
            f"Сотрудник может изменять только статус задачи (недопустимые поля: {', '.join(sorted(disallowed))})"
        )
    return task_repository.update_fields(db, task, fields)
