from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_zavod
from app.db.session import get_db
from app.models.user import User
from app.models.zavod import ZavodBoard, ZavodEdge, ZavodNode
from app.services import zavod_service
from app.services.exceptions import ZavodInvalidEdgeError, ZavodNotFoundError
from app.schemas.zavod import (
    ZavodBoardCreate,
    ZavodBoardDetail,
    ZavodBoardOut,
    ZavodBoardUpdate,
    ZavodEdgeCreate,
    ZavodEdgeOut,
    ZavodNodeAssignee,
    ZavodNodeCreate,
    ZavodNodeOut,
    ZavodNodesMove,
    ZavodNodeUpdate,
)

# Весь раздел под одним гейтом: внутри ZAVOD все допущенные равны в правах.
router = APIRouter(dependencies=[Depends(require_zavod)])


def _not_found(exc: Exception) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get("/users", response_model=list[ZavodNodeAssignee])
def list_assignable_users(db: Session = Depends(get_db)) -> list[User]:
    return zavod_service.list_assignable_users(db)


# --- Доски ---

@router.get("/boards", response_model=list[ZavodBoardOut])
def list_boards(db: Session = Depends(get_db)) -> list[ZavodBoard]:
    return zavod_service.list_boards(db)


@router.post("/boards", response_model=ZavodBoardOut, status_code=status.HTTP_201_CREATED)
def create_board(
    payload: ZavodBoardCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ZavodBoard:
    return zavod_service.create_board(db, current_user, title=payload.title)


@router.get("/boards/{board_id}", response_model=ZavodBoardDetail)
def get_board(board_id: int, db: Session = Depends(get_db)) -> ZavodBoardDetail:
    try:
        board = zavod_service.get_board(db, board_id)
        nodes, edges = zavod_service.board_contents(db, board_id)
    except ZavodNotFoundError as exc:
        raise _not_found(exc)
    return ZavodBoardDetail(id=board.id, title=board.title, nodes=nodes, edges=edges)


@router.patch("/boards/{board_id}", response_model=ZavodBoardOut)
def rename_board(
    board_id: int, payload: ZavodBoardUpdate, db: Session = Depends(get_db)
) -> ZavodBoard:
    if payload.title is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Укажите название"
        )
    try:
        return zavod_service.rename_board(db, board_id, title=payload.title)
    except ZavodNotFoundError as exc:
        raise _not_found(exc)


@router.delete("/boards/{board_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_board(board_id: int, db: Session = Depends(get_db)) -> None:
    try:
        zavod_service.delete_board(db, board_id)
    except ZavodNotFoundError as exc:
        raise _not_found(exc)


# --- Карточки ---

@router.post(
    "/boards/{board_id}/nodes", response_model=ZavodNodeOut, status_code=status.HTTP_201_CREATED
)
def create_node(
    board_id: int,
    payload: ZavodNodeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ZavodNode:
    try:
        return zavod_service.create_node(db, current_user, board_id, payload)
    except ZavodNotFoundError as exc:
        raise _not_found(exc)


@router.post("/boards/{board_id}/nodes/move", response_model=list[ZavodNodeOut])
def move_nodes(
    board_id: int, payload: ZavodNodesMove, db: Session = Depends(get_db)
) -> list[ZavodNode]:
    try:
        return zavod_service.move_nodes(db, board_id, payload.moves)
    except ZavodNotFoundError as exc:
        raise _not_found(exc)


@router.patch("/nodes/{node_id}", response_model=ZavodNodeOut)
def update_node(
    node_id: int, payload: ZavodNodeUpdate, db: Session = Depends(get_db)
) -> ZavodNode:
    # Только явно переданные поля: null у color означает «снять цвет», а не
    # «не трогать» (тот же приём, что в leadership_tasks).
    fields = {k: getattr(payload, k) for k in payload.model_fields_set}
    if not fields:
        return zavod_service.get_node(db, node_id)
    try:
        return zavod_service.update_node(db, node_id, fields)
    except ZavodNotFoundError as exc:
        raise _not_found(exc)


@router.delete("/nodes/{node_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_node(node_id: int, db: Session = Depends(get_db)) -> None:
    try:
        zavod_service.delete_node(db, node_id)
    except ZavodNotFoundError as exc:
        raise _not_found(exc)


# --- Связи ---

@router.post(
    "/boards/{board_id}/edges", response_model=ZavodEdgeOut, status_code=status.HTTP_201_CREATED
)
def create_edge(
    board_id: int, payload: ZavodEdgeCreate, db: Session = Depends(get_db)
) -> ZavodEdge:
    try:
        return zavod_service.create_edge(
            db, board_id, source_id=payload.source_id, target_id=payload.target_id
        )
    except ZavodNotFoundError as exc:
        raise _not_found(exc)
    except ZavodInvalidEdgeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.delete("/edges/{edge_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_edge(edge_id: int, db: Session = Depends(get_db)) -> None:
    try:
        zavod_service.delete_edge(db, edge_id)
    except ZavodNotFoundError as exc:
        raise _not_found(exc)
