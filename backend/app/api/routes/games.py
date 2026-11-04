from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_role
from app.db.session import get_db
from app.models.user import User, UserRole
from app.schemas.bunker import (
    BunkerListItem,
    BunkerMove,
    BunkerOut,
    BunkerTableIn,
    BunkerTableOut,
    BunkerTableSaved,
)
from app.schemas.durak import DurakCreate, DurakListItem, DurakMove, DurakOut
from app.schemas.sea_battle import SeaBattleCreate, SeaBattleListItem, SeaBattleMove, SeaBattleOut
from app.services import bunker_service, durak_service, sea_battle_service
from app.services.exceptions import (
    BunkerMoveError,
    BunkerNotFoundError,
    BunkerVersionConflictError,
    DurakGameNotFoundError,
    DurakMoveError,
    DurakVersionConflictError,
    SeaBattleMoveError,
    SeaBattleNotFoundError,
    SeaBattleVersionConflictError,
)

# Раздел «Игры»: доступен всем вошедшим.
router = APIRouter(dependencies=[Depends(get_current_user)])


@router.get("/durak", response_model=list[DurakListItem])
def list_durak(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> list[dict]:
    return [
        {
            "code": game.code,
            "status": game.status,
            "vs_bot": game.vs_bot,
            "opponent_name": durak_service.opponent_name(game, current_user),
            "my_turn": durak_service.is_my_turn(game, current_user),
        }
        for game in durak_service.list_active(db, current_user)
    ]


@router.post("/durak", response_model=DurakOut, status_code=status.HTTP_201_CREATED)
def create_durak(
    payload: DurakCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    game = durak_service.create(db, current_user, payload.vs_bot)
    return durak_service.view(game, current_user)


@router.get("/durak/{code}", response_model=DurakOut)
def get_durak(
    code: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> dict:
    try:
        game = durak_service.get_for(db, current_user, code)
    except DurakGameNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return durak_service.view(game, current_user)


@router.post("/durak/{code}/join", response_model=DurakOut)
def join_durak(
    code: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> dict:
    try:
        game = durak_service.join(db, current_user, code)
    except DurakGameNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return durak_service.view(game, current_user)


@router.post("/durak/{code}/ready", response_model=DurakOut)
def ready_durak(
    code: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> dict:
    try:
        game = durak_service.ready(db, current_user, code)
    except DurakGameNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except DurakMoveError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return durak_service.view(game, current_user)


@router.post("/durak/{code}/cancel", response_model=DurakOut)
def cancel_durak(
    code: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> dict:
    try:
        game = durak_service.cancel(db, current_user, code)
    except DurakGameNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except DurakMoveError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return durak_service.view(game, current_user)


@router.post("/durak/{code}/leave", response_model=DurakOut)
def leave_durak(
    code: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> dict:
    try:
        game = durak_service.leave(db, current_user, code)
    except DurakGameNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except DurakMoveError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return durak_service.view(game, current_user)


@router.post("/durak/{code}/invite-chat", response_model=DurakOut)
def invite_durak_to_chat(
    code: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> dict:
    try:
        game = durak_service.invite_to_chat(db, current_user, code)
    except DurakGameNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except DurakMoveError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return durak_service.view(game, current_user)


@router.post("/durak/{code}/move", response_model=DurakOut)
def move_durak(
    code: str,
    payload: DurakMove,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        game = durak_service.move(db, current_user, code, payload)
    except DurakGameNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except DurakVersionConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except DurakMoveError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return durak_service.view(game, current_user)


# ── Морской бой ──

@router.get("/sea", response_model=list[SeaBattleListItem])
def list_sea(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> list[dict]:
    return [
        {
            "code": game.code,
            "status": game.status,
            "vs_bot": game.vs_bot,
            "opponent_name": sea_battle_service.opponent_name(game, current_user),
            "my_turn": sea_battle_service.is_my_turn(game, current_user),
        }
        for game in sea_battle_service.list_active(db, current_user)
    ]


@router.post("/sea", response_model=SeaBattleOut, status_code=status.HTTP_201_CREATED)
def create_sea(
    payload: SeaBattleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    game = sea_battle_service.create(db, current_user, payload.vs_bot)
    return sea_battle_service.view(game, current_user)


@router.get("/sea/{code}", response_model=SeaBattleOut)
def get_sea(
    code: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> dict:
    try:
        game = sea_battle_service.get_for(db, current_user, code)
    except SeaBattleNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return sea_battle_service.view(game, current_user)


@router.post("/sea/{code}/join", response_model=SeaBattleOut)
def join_sea(
    code: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> dict:
    try:
        game = sea_battle_service.join(db, current_user, code)
    except SeaBattleNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return sea_battle_service.view(game, current_user)


@router.post("/sea/{code}/ready", response_model=SeaBattleOut)
def ready_sea(
    code: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> dict:
    try:
        game = sea_battle_service.ready(db, current_user, code)
    except SeaBattleNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except SeaBattleMoveError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return sea_battle_service.view(game, current_user)


@router.post("/sea/{code}/cancel", response_model=SeaBattleOut)
def cancel_sea(
    code: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> dict:
    try:
        game = sea_battle_service.cancel(db, current_user, code)
    except SeaBattleNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except SeaBattleMoveError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return sea_battle_service.view(game, current_user)


@router.post("/sea/{code}/invite-chat", response_model=SeaBattleOut)
def invite_sea_to_chat(
    code: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> dict:
    try:
        game = sea_battle_service.invite_to_chat(db, current_user, code)
    except SeaBattleNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except SeaBattleMoveError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return sea_battle_service.view(game, current_user)


@router.post("/sea/{code}/move", response_model=SeaBattleOut)
def move_sea(
    code: str,
    payload: SeaBattleMove,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        game = sea_battle_service.move(db, current_user, code, payload)
    except SeaBattleNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except SeaBattleVersionConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except SeaBattleMoveError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return sea_battle_service.view(game, current_user)


# ── Бункер ──

@router.get("/bunker", response_model=list[BunkerListItem])
def list_bunker(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> list[dict]:
    return [
        {
            "code": game.code,
            "title": game.title,
            "status": game.status,
            "players": len(game.players),
            "my_turn": bunker_service.is_my_turn(game, current_user),
        }
        for game in bunker_service.list_active(db, current_user)
    ]


@router.post("/bunker", response_model=BunkerOut, status_code=status.HTTP_201_CREATED)
def create_bunker(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> dict:
    game = bunker_service.create(db, current_user)
    return bunker_service.view(game, current_user)


# Открытые столы — всем: сесть можно, пока карты не розданы.
@router.get("/bunker/open-tables", response_model=list[BunkerTableOut])
def list_open_bunker_tables(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> list[dict]:
    return [bunker_service.table_view(game) for game in bunker_service.list_open_tables(db, current_user)]


# Столы для очной игры — только админ.
admin_only = require_role(UserRole.ADMIN)


@router.get("/bunker/tables", response_model=list[BunkerTableOut])
def list_bunker_tables(db: Session = Depends(get_db), admin: User = Depends(admin_only)) -> list[dict]:
    return [bunker_service.table_view(game) for game in bunker_service.list_tables(db)]


@router.post("/bunker/tables", response_model=BunkerTableSaved, status_code=status.HTTP_201_CREATED)
def create_bunker_table(
    payload: BunkerTableIn, db: Session = Depends(get_db), admin: User = Depends(admin_only)
) -> dict:
    try:
        game, missing = bunker_service.create_table(db, admin, payload.title, payload.tags, payload.host_tag)
    except BunkerMoveError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return {"table": bunker_service.table_view(game), "missing": missing}


@router.put("/bunker/tables/{code}", response_model=BunkerTableSaved)
def update_bunker_table(
    code: str, payload: BunkerTableIn, db: Session = Depends(get_db), admin: User = Depends(admin_only)
) -> dict:
    try:
        game, missing = bunker_service.update_table(
            db, admin, code, payload.title, payload.tags, payload.host_tag
        )
    except BunkerNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except BunkerMoveError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return {"table": bunker_service.table_view(game), "missing": missing}


@router.post("/bunker/tables/{code}/start", response_model=BunkerTableOut)
def start_bunker_table(code: str, db: Session = Depends(get_db), admin: User = Depends(admin_only)) -> dict:
    try:
        game = bunker_service.start_table(db, admin, code)
    except BunkerNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except BunkerMoveError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return bunker_service.table_view(game)


@router.delete("/bunker/tables/{code}", response_model=BunkerTableOut)
def cancel_bunker_table(code: str, db: Session = Depends(get_db), admin: User = Depends(admin_only)) -> dict:
    try:
        game = bunker_service.cancel_table(db, admin, code)
    except BunkerNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return bunker_service.table_view(game)


@router.get("/bunker/{code}", response_model=BunkerOut)
def get_bunker(
    code: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> dict:
    try:
        game = bunker_service.get_for(db, current_user, code)
    except BunkerNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return bunker_service.view(game, current_user)


def _bunker_action(action, code: str, db: Session, current_user: User) -> dict:
    try:
        game = action(db, current_user, code)
    except BunkerNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except BunkerMoveError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return bunker_service.view(game, current_user)


@router.post("/bunker/{code}/join", response_model=BunkerOut)
def join_bunker(
    code: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> dict:
    return _bunker_action(bunker_service.join, code, db, current_user)


@router.post("/bunker/{code}/leave", response_model=BunkerOut)
def leave_bunker(
    code: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> dict:
    return _bunker_action(bunker_service.leave, code, db, current_user)


@router.post("/bunker/{code}/start", response_model=BunkerOut)
def start_bunker(
    code: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> dict:
    return _bunker_action(bunker_service.start, code, db, current_user)


@router.post("/bunker/{code}/invite-chat", response_model=BunkerOut)
def invite_bunker_to_chat(
    code: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> dict:
    return _bunker_action(bunker_service.invite_to_chat, code, db, current_user)


@router.post("/bunker/{code}/move", response_model=BunkerOut)
def move_bunker(
    code: str,
    payload: BunkerMove,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        game = bunker_service.move(db, current_user, code, payload)
    except BunkerNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except BunkerVersionConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except BunkerMoveError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return bunker_service.view(game, current_user)
