from sqlalchemy import delete as sa_delete, func, select
from sqlalchemy.orm import Session, joinedload

from app.models.survey import Survey, SurveyRecipient, SurveyResponse, SurveyStatus


def get(db: Session, survey_id: int) -> Survey | None:
    return db.get(Survey, survey_id)


def list_all(db: Session) -> list[Survey]:
    query = select(Survey).options(joinedload(Survey.author)).order_by(Survey.id.desc())
    return list(db.scalars(query))


def counts(db: Session) -> tuple[dict[int, int], dict[int, int]]:
    """Сколько получателей и ответов у каждой анкеты."""
    recipients = dict(db.execute(
        select(SurveyRecipient.survey_id, func.count()).group_by(SurveyRecipient.survey_id)
    ).all())
    responses = dict(db.execute(
        select(SurveyResponse.survey_id, func.count()).group_by(SurveyResponse.survey_id)
    ).all())
    return recipients, responses


def create(db: Session, **fields) -> Survey:
    survey = Survey(**fields)
    db.add(survey)
    db.commit()
    db.refresh(survey)
    return survey


def save(db: Session, survey: Survey, **fields) -> Survey:
    for key, value in fields.items():
        setattr(survey, key, value)
    db.commit()
    db.refresh(survey)
    return survey


def delete(db: Session, survey: Survey) -> None:
    # PRAGMA foreign_keys в SQLite выключен — каскад вручную.
    db.execute(sa_delete(SurveyResponse).where(SurveyResponse.survey_id == survey.id))
    db.execute(sa_delete(SurveyRecipient).where(SurveyRecipient.survey_id == survey.id))
    db.delete(survey)
    db.commit()


def recipients(db: Session, survey_id: int) -> list[SurveyRecipient]:
    query = (
        select(SurveyRecipient)
        .options(joinedload(SurveyRecipient.user))
        .where(SurveyRecipient.survey_id == survey_id)
    )
    return list(db.scalars(query))


def recipient(db: Session, survey_id: int, user_id: int) -> SurveyRecipient | None:
    return db.get(SurveyRecipient, (survey_id, user_id))


def add_recipients(db: Session, survey_id: int, user_ids: list[int]) -> None:
    for user_id in user_ids:
        db.add(SurveyRecipient(survey_id=survey_id, user_id=user_id))
    db.commit()


def responses(db: Session, survey_id: int) -> dict[int, SurveyResponse]:
    rows = db.scalars(select(SurveyResponse).where(SurveyResponse.survey_id == survey_id))
    return {r.user_id: r for r in rows}


def has_responses(db: Session, survey_id: int) -> bool:
    return db.scalar(select(SurveyResponse.id).where(SurveyResponse.survey_id == survey_id).limit(1)) is not None


def response(db: Session, survey_id: int, user_id: int) -> SurveyResponse | None:
    return db.scalar(
        select(SurveyResponse).where(SurveyResponse.survey_id == survey_id, SurveyResponse.user_id == user_id)
    )


def save_response(db: Session, survey_id: int, user_id: int, answers: dict, now) -> SurveyResponse:
    row = response(db, survey_id, user_id)
    if row is None:
        row = SurveyResponse(survey_id=survey_id, user_id=user_id)
        db.add(row)
    row.answers = answers
    row.submitted_at = now
    db.commit()
    db.refresh(row)
    return row


def for_user(db: Session, user_id: int) -> list[tuple[Survey, SurveyRecipient]]:
    """Анкеты, отправленные человеку (кроме черновиков), — свежие сверху."""
    query = (
        select(Survey, SurveyRecipient)
        .join(SurveyRecipient, SurveyRecipient.survey_id == Survey.id)
        .where(SurveyRecipient.user_id == user_id, Survey.status != SurveyStatus.DRAFT)
        .order_by(Survey.id.desc())
    )
    return list(db.execute(query).all())
