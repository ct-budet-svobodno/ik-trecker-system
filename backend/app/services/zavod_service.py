from sqlalchemy.orm import Session

from app.models.user import User
from app.models.zavod import ZavodBoard, ZavodEdge, ZavodNode
from app.repositories import user_repository, zavod_repository
from app.schemas.zavod import ZavodNodeCreate
from app.services.exceptions import ZavodInvalidEdgeError, ZavodNotFoundError


def list_assignable_users(db: Session) -> list[User]:
    """Кого можно назначить ответственным. Отдельный список, а не GET /users:
    тот открыт только админам и руководителям, а в ZAVOD назначают все."""
    return [u for u in user_repository.list_all(db) if u.is_active]


def list_boards(db: Session) -> list[ZavodBoard]:
    return zavod_repository.list_boards(db)


def get_board(db: Session, board_id: int) -> ZavodBoard:
    board = zavod_repository.get_board(db, board_id)
    if board is None:
        raise ZavodNotFoundError("Доска не найдена")
    return board


def create_board(db: Session, viewer: User, *, title: str) -> ZavodBoard:
    return zavod_repository.create_board(db, title=title, created_by_id=viewer.id)


def rename_board(db: Session, board_id: int, *, title: str) -> ZavodBoard:
    board = get_board(db, board_id)
    board.title = title
    db.commit()
    db.refresh(board)
    return board


def delete_board(db: Session, board_id: int) -> None:
    zavod_repository.delete_board(db, get_board(db, board_id))


def board_contents(db: Session, board_id: int) -> tuple[list[ZavodNode], list[ZavodEdge]]:
    board = get_board(db, board_id)
    return (
        zavod_repository.list_nodes(db, board.id),
        zavod_repository.list_edges(db, board.id),
    )


def _resolve_assignees(db: Session, assignee_ids: list[int]) -> list[User]:
    """Молча отбрасываем несуществующих: назначение — не та операция,
    ради которой стоит ронять сохранение всей карточки."""
    users = [user_repository.get_by_id(db, uid) for uid in assignee_ids]
    return [u for u in users if u is not None]


def create_node(db: Session, viewer: User, board_id: int, payload: ZavodNodeCreate) -> ZavodNode:
    board = get_board(db, board_id)
    return zavod_repository.create_node(
        db,
        board_id=board.id,
        title=payload.title,
        content=payload.content,
        status=payload.status,
        color=payload.color,
        x=payload.x,
        y=payload.y,
        width=payload.width,
        height=payload.height,
        created_by_id=viewer.id,
        assignees=_resolve_assignees(db, payload.assignee_ids),
    )


def get_node(db: Session, node_id: int) -> ZavodNode:
    node = zavod_repository.get_node(db, node_id)
    if node is None:
        raise ZavodNotFoundError("Карточка не найдена")
    return node


def update_node(db: Session, node_id: int, fields: dict) -> ZavodNode:
    node = get_node(db, node_id)
    # assignee_ids — не колонка, а связь: разворачиваем в объекты пользователей.
    if "assignee_ids" in fields:
        fields = dict(fields)
        fields["assignees"] = _resolve_assignees(db, fields.pop("assignee_ids") or [])
    return zavod_repository.update_node_fields(db, node, fields)


def move_nodes(db: Session, board_id: int, moves: list) -> list[ZavodNode]:
    board = get_board(db, board_id)
    known = {node.id for node in zavod_repository.list_nodes(db, board.id)}
    # Чужие карточки в пакете игнорируем — доска не должна двигать соседнюю.
    positions = {m.id: (m.x, m.y) for m in moves if m.id in known}
    return zavod_repository.move_nodes(db, positions)


def delete_node(db: Session, node_id: int) -> None:
    zavod_repository.delete_node(db, get_node(db, node_id))


def create_edge(db: Session, board_id: int, *, source_id: int, target_id: int) -> ZavodEdge:
    board = get_board(db, board_id)
    if source_id == target_id:
        raise ZavodInvalidEdgeError("Нельзя связать карточку саму с собой")

    source = get_node(db, source_id)
    target = get_node(db, target_id)
    if source.board_id != board.id or target.board_id != board.id:
        raise ZavodInvalidEdgeError("Обе карточки должны быть с этой доски")

    # Связь ненаправленная по смыслу: A→B и B→A — одно и то же, дубль не заводим.
    existing = zavod_repository.find_edge(db, source_id=source_id, target_id=target_id)
    if existing is None:
        existing = zavod_repository.find_edge(db, source_id=target_id, target_id=source_id)
    if existing is not None:
        raise ZavodInvalidEdgeError("Такая связь уже есть")

    return zavod_repository.create_edge(
        db, board_id=board.id, source_id=source_id, target_id=target_id
    )


def delete_edge(db: Session, edge_id: int) -> None:
    edge = zavod_repository.get_edge(db, edge_id)
    if edge is None:
        raise ZavodNotFoundError("Связь не найдена")
    zavod_repository.delete_edge(db, edge)
