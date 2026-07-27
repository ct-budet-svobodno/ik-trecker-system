from sqlalchemy import delete as sa_delete
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.zavod import ZavodBoard, ZavodEdge, ZavodNode, ZavodNodeStatus


# --- Доски ---

def list_boards(db: Session) -> list[ZavodBoard]:
    return list(db.scalars(select(ZavodBoard).order_by(ZavodBoard.id)))


def get_board(db: Session, board_id: int) -> ZavodBoard | None:
    return db.get(ZavodBoard, board_id)


def create_board(db: Session, *, title: str, created_by_id: int) -> ZavodBoard:
    board = ZavodBoard(title=title, created_by_id=created_by_id)
    db.add(board)
    db.commit()
    db.refresh(board)
    return board


def delete_board(db: Session, board: ZavodBoard) -> None:
    # SQLite здесь без PRAGMA foreign_keys, каскада на уровне БД нет — чистим руками.
    db.execute(sa_delete(ZavodEdge).where(ZavodEdge.board_id == board.id))
    for node in list_nodes(db, board.id):
        node.assignees.clear()
        db.delete(node)
    db.delete(board)
    db.commit()


# --- Карточки ---

def list_nodes(db: Session, board_id: int) -> list[ZavodNode]:
    return list(
        db.scalars(select(ZavodNode).where(ZavodNode.board_id == board_id).order_by(ZavodNode.id))
    )


def get_node(db: Session, node_id: int) -> ZavodNode | None:
    return db.get(ZavodNode, node_id)


def get_nodes_by_ids(db: Session, node_ids: list[int]) -> list[ZavodNode]:
    if not node_ids:
        return []
    return list(db.scalars(select(ZavodNode).where(ZavodNode.id.in_(node_ids))))


def create_node(
    db: Session,
    *,
    board_id: int,
    title: str,
    content: str | None,
    status: ZavodNodeStatus,
    color: str | None,
    x: float,
    y: float,
    width: float,
    height: float,
    created_by_id: int,
    assignees: list[User],
) -> ZavodNode:
    node = ZavodNode(
        board_id=board_id,
        title=title,
        content=content,
        status=status,
        color=color,
        x=x,
        y=y,
        width=width,
        height=height,
        created_by_id=created_by_id,
    )
    node.assignees = assignees
    db.add(node)
    db.commit()
    db.refresh(node)
    return node


def update_node_fields(db: Session, node: ZavodNode, fields: dict) -> ZavodNode:
    for key, value in fields.items():
        setattr(node, key, value)
    db.commit()
    db.refresh(node)
    return node


def move_nodes(db: Session, positions: dict[int, tuple[float, float]]) -> list[ZavodNode]:
    """Пакетное перемещение: id → (x, y). Один коммит на всю группу."""
    nodes = get_nodes_by_ids(db, list(positions))
    for node in nodes:
        node.x, node.y = positions[node.id]
    db.commit()
    return nodes


def delete_node(db: Session, node: ZavodNode) -> None:
    # Связи, упирающиеся в карточку с любой стороны, уходят вместе с ней.
    db.execute(
        sa_delete(ZavodEdge).where(
            or_(ZavodEdge.source_id == node.id, ZavodEdge.target_id == node.id)
        )
    )
    node.assignees.clear()
    db.delete(node)
    db.commit()


# --- Связи ---

def list_edges(db: Session, board_id: int) -> list[ZavodEdge]:
    return list(
        db.scalars(select(ZavodEdge).where(ZavodEdge.board_id == board_id).order_by(ZavodEdge.id))
    )


def get_edge(db: Session, edge_id: int) -> ZavodEdge | None:
    return db.get(ZavodEdge, edge_id)


def find_edge(db: Session, *, source_id: int, target_id: int) -> ZavodEdge | None:
    return db.scalar(
        select(ZavodEdge).where(
            ZavodEdge.source_id == source_id, ZavodEdge.target_id == target_id
        )
    )


def create_edge(db: Session, *, board_id: int, source_id: int, target_id: int) -> ZavodEdge:
    edge = ZavodEdge(board_id=board_id, source_id=source_id, target_id=target_id)
    db.add(edge)
    db.commit()
    db.refresh(edge)
    return edge


def delete_edge(db: Session, edge: ZavodEdge) -> None:
    db.delete(edge)
    db.commit()
