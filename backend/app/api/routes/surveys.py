from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_role
from app.db.session import get_db
from app.models.survey import Survey, SurveyStatus
from app.models.user import User, UserRole
from app.repositories import survey_repository
from app.schemas.survey import (
    MySurveyOut,
    SurveyAdminOut,
    SurveyIn,
    SurveyRemindOut,
    SurveyResponseIn,
    SurveySendIn,
    SurveySendOut,
    SurveyStatusIn,
    SurveySummaryOut,
)
from app.services import survey_service
from app.services.exceptions import SurveyError

# Собирает и рассылает анкеты админ; отвечают получатели.
router = APIRouter()
admin_only = require_role(UserRole.ADMIN)


def _survey(db: Session, survey_id: int) -> Survey:
    survey = survey_repository.get(db, survey_id)
    if survey is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Анкета не найдена")
    return survey


def _bad(exc: SurveyError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


# ── Получатель ──

@router.get("/my", response_model=list[MySurveyOut])
def my_surveys(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[dict]:
    return survey_service.list_mine(db, user)


@router.get("/{survey_id}/fill", response_model=MySurveyOut)
def fill(survey_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    view = survey_service.get_mine(db, survey_id, user)
    if view is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Анкета не найдена")
    return view


@router.put("/{survey_id}/response", response_model=MySurveyOut)
def answer(
    survey_id: int,
    payload: SurveyResponseIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    try:
        view = survey_service.submit(db, survey_id, user, payload.answers)
    except SurveyError as exc:
        raise _bad(exc)
    if view is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Анкета не найдена")
    return view


# ── Админ ──

@router.get("", response_model=list[SurveySummaryOut], dependencies=[Depends(admin_only)])
def list_surveys(db: Session = Depends(get_db)) -> list[dict]:
    return survey_service.summary(db)


@router.post("", response_model=SurveyAdminOut, status_code=status.HTTP_201_CREATED)
def create(payload: SurveyIn, db: Session = Depends(get_db), admin: User = Depends(admin_only)) -> dict:
    return survey_service.admin_view(db, survey_service.create(db, admin, payload))


@router.get("/{survey_id}", response_model=SurveyAdminOut, dependencies=[Depends(admin_only)])
def get_one(survey_id: int, db: Session = Depends(get_db)) -> dict:
    return survey_service.admin_view(db, _survey(db, survey_id))


@router.put("/{survey_id}", response_model=SurveyAdminOut, dependencies=[Depends(admin_only)])
def update(survey_id: int, payload: SurveyIn, db: Session = Depends(get_db)) -> dict:
    try:
        survey = survey_service.update(db, _survey(db, survey_id), payload)
    except SurveyError as exc:
        raise _bad(exc)
    return survey_service.admin_view(db, survey)


@router.delete("/{survey_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(admin_only)])
def delete(survey_id: int, db: Session = Depends(get_db)) -> None:
    survey_service.delete(db, _survey(db, survey_id))


@router.post("/{survey_id}/send", response_model=SurveySendOut, dependencies=[Depends(admin_only)])
def send(survey_id: int, payload: SurveySendIn, db: Session = Depends(get_db)) -> dict:
    try:
        return survey_service.send(db, _survey(db, survey_id), payload.user_ids)
    except SurveyError as exc:
        raise _bad(exc)


@router.post("/{survey_id}/remind", response_model=SurveyRemindOut, dependencies=[Depends(admin_only)])
def remind(survey_id: int, db: Session = Depends(get_db)) -> dict:
    try:
        return survey_service.remind(db, _survey(db, survey_id))
    except SurveyError as exc:
        raise _bad(exc)


@router.post("/{survey_id}/status", response_model=SurveyAdminOut, dependencies=[Depends(admin_only)])
def set_status(survey_id: int, payload: SurveyStatusIn, db: Session = Depends(get_db)) -> dict:
    try:
        survey = survey_service.set_status(db, _survey(db, survey_id), SurveyStatus(payload.status))
    except SurveyError as exc:
        raise _bad(exc)
    return survey_service.admin_view(db, survey)
