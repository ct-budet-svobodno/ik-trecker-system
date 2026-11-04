"""Анкеты: админ собирает вопросы, отправляет выбранным людям, смотрит ответы.

Получатели — аккаунты трекера (активные). Об анкете человеку приходит
уведомление (сообщение бота с кнопкой мини-аппа + web push) со ссылкой
/surveys/<id>; без Telegram и push он увидит её только в разделе «Анкеты».
Вопросы правятся, пока никто не ответил: ответы хранятся по id вопроса,
и смена вопросов после ответов перемешала бы смысл. Ответ можно
переотправить, пока анкета открыта.
"""
import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.survey import Survey, SurveyStatus
from app.models.user import RegistrationStatus, User, UserRole
from app.repositories import survey_repository
from app.schemas.survey import SurveyIn
from app.services import push_service
from app.services.exceptions import SurveyError

REMIND_EVERY = datetime.timedelta(minutes=30)
MAX_TEXT_ANSWER = 4000


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.UTC)


def _aware(value: datetime.datetime | None) -> datetime.datetime | None:
    # SQLite отдаёт время без зоны, хранит UTC.
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=datetime.UTC)
    return value


def _link(survey: Survey) -> str:
    return f"/surveys/{survey.id}"


# ── Админ: анкета ──

def create(db: Session, admin: User, data: SurveyIn) -> Survey:
    return survey_repository.create(
        db,
        author_id=admin.id,
        title=data.title.strip(),
        description=data.description.strip(),
        questions=[q.model_dump() for q in data.questions],
        status=SurveyStatus.DRAFT,
    )


def can_edit_questions(db: Session, survey: Survey) -> bool:
    return not survey_repository.has_responses(db, survey.id)


def update(db: Session, survey: Survey, data: SurveyIn) -> Survey:
    questions = [q.model_dump() for q in data.questions]
    if questions != survey.questions and not can_edit_questions(db, survey):
        raise SurveyError("На анкету уже ответили — вопросы менять нельзя, только название и описание")
    return survey_repository.save(
        db, survey, title=data.title.strip(), description=data.description.strip(), questions=questions
    )


def delete(db: Session, survey: Survey) -> None:
    survey_repository.delete(db, survey)


def set_status(db: Session, survey: Survey, status: SurveyStatus) -> Survey:
    if survey.status == SurveyStatus.DRAFT:
        raise SurveyError("Анкету ещё никому не отправили")
    return survey_repository.save(db, survey, status=status)


def send(db: Session, survey: Survey, user_ids: list[int]) -> dict:
    """Добавить получателей и уведомить новых. Уже получавших не дёргаем —
    для них есть «Напомнить»."""
    if survey.status == SurveyStatus.CLOSED:
        raise SurveyError("Анкета закрыта — откройте её, чтобы отправить")
    users = list(db.scalars(select(User).where(
        User.id.in_(set(user_ids)),
        User.is_active.is_(True),
        User.registration_status == RegistrationStatus.APPROVED,
    )))
    if not users:
        raise SurveyError("Некому отправлять: выберите активных пользователей")
    existing = {r.user_id for r in survey_repository.recipients(db, survey.id)}
    new = [u for u in users if u.id not in existing]
    survey_repository.add_recipients(db, survey.id, [u.id for u in new])
    if survey.status == SurveyStatus.DRAFT:
        survey_repository.save(db, survey, status=SurveyStatus.OPEN)
    if new:
        push_service.send_to_users(
            db, [u.id for u in new], title="Новая анкета", body=survey.title, url=_link(survey)
        )
    return {
        "added": len(new),
        "already": len(users) - len(new),
        "without_telegram": sum(1 for u in new if u.telegram_id is None),
    }


def remind(db: Session, survey: Survey) -> dict:
    if survey.status != SurveyStatus.OPEN:
        raise SurveyError("Напомнить можно только об открытой анкете")
    last = _aware(survey.reminded_at)
    if last is not None and _now() - last < REMIND_EVERY:
        minutes = int((REMIND_EVERY - (_now() - last)).total_seconds() // 60) + 1
        raise SurveyError(f"Напоминали недавно — следующее можно через {minutes} мин")
    answered = survey_repository.responses(db, survey.id)
    waiting = [
        r.user_id for r in survey_repository.recipients(db, survey.id)
        if r.user_id not in answered and r.user.is_active
    ]
    if not waiting:
        raise SurveyError("Все уже ответили")
    push_service.send_to_users(
        db, waiting, title="Напоминание: анкета", body=f"Ждём ваши ответы — «{survey.title}»", url=_link(survey)
    )
    survey_repository.save(db, survey, reminded_at=_now())
    return {"reminded": len(waiting)}


def summary(db: Session) -> list[dict]:
    recipients, responses = survey_repository.counts(db)
    return [
        {
            "id": s.id,
            "title": s.title,
            "status": s.status,
            "questions_count": len(s.questions),
            "recipients": recipients.get(s.id, 0),
            "responses": responses.get(s.id, 0),
            "author_name": s.author.full_name if s.author else None,
            "created_at": s.created_at,
        }
        for s in survey_repository.list_all(db)
    ]


def admin_view(db: Session, survey: Survey) -> dict:
    answers = survey_repository.responses(db, survey.id)
    recipients = sorted(survey_repository.recipients(db, survey.id), key=lambda r: r.user.full_name.lower())
    return {
        "id": survey.id,
        "title": survey.title,
        "description": survey.description,
        "questions": survey.questions,
        "status": survey.status,
        "author_name": survey.author.full_name if survey.author else None,
        "created_at": survey.created_at,
        "reminded_at": survey.reminded_at,
        "can_edit_questions": not answers,
        "recipients": [
            {
                "user_id": r.user_id,
                "full_name": r.user.full_name,
                "telegram_username": r.user.telegram_username,
                "telegram_linked": r.user.telegram_id is not None,
                "sent_at": r.sent_at,
                "answers": answers[r.user_id].answers if r.user_id in answers else None,
                "submitted_at": answers[r.user_id].submitted_at if r.user_id in answers else None,
            }
            for r in recipients
        ],
    }


# ── Получатель ──

def _my_view(survey: Survey, sent_at, response) -> dict:
    return {
        "id": survey.id,
        "title": survey.title,
        "description": survey.description,
        "questions": survey.questions,
        "status": survey.status,
        "answers": response.answers if response else None,
        "submitted_at": response.submitted_at if response else None,
        "sent_at": sent_at,
    }


def list_mine(db: Session, user: User) -> list[dict]:
    return [
        _my_view(survey, recipient.sent_at, survey_repository.response(db, survey.id, user.id))
        for survey, recipient in survey_repository.for_user(db, user.id)
    ]


def get_mine(db: Session, survey_id: int, user: User) -> dict | None:
    """Анкета для заполнения. Не получатель — None (404), кроме админа:
    он может открыть и посмотреть, как она выглядит."""
    survey = survey_repository.get(db, survey_id)
    if survey is None:
        return None
    recipient = survey_repository.recipient(db, survey_id, user.id)
    response = survey_repository.response(db, survey_id, user.id)
    if recipient is not None and survey.status != SurveyStatus.DRAFT:
        return _my_view(survey, recipient.sent_at, response)
    if user.role == UserRole.ADMIN:
        return _my_view(survey, None, response)
    return None


def _clean_answers(questions: list[dict], answers: dict) -> dict:
    cleaned = {}
    for q in questions:
        value = answers.get(q["id"])
        title = q["title"]
        if q["type"] in ("text", "textarea"):
            value = value.strip() if isinstance(value, str) else ""
            if len(value) > MAX_TEXT_ANSWER:
                raise SurveyError(f"Ответ на «{title}» слишком длинный")
            value = value or None
        elif q["type"] == "single":
            if value in (None, ""):
                value = None
            elif value not in q["options"]:
                raise SurveyError(f"В вопросе «{title}» нет такого варианта")
        elif q["type"] == "multi":
            if value in (None, ""):
                value = []
            if not isinstance(value, list) or any(v not in q["options"] for v in value):
                raise SurveyError(f"В вопросе «{title}» нет такого варианта")
            value = [o for o in q["options"] if o in value] or None  # порядок — как в анкете
        elif q["type"] == "scale":
            if value in (None, ""):
                value = None
            elif not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= q["max"]:
                raise SurveyError(f"В вопросе «{title}» оценка от 1 до {q['max']}")
        if value is None and q["required"]:
            raise SurveyError(f"Ответьте на вопрос «{title}»")
        if value is not None:
            cleaned[q["id"]] = value
    return cleaned


def submit(db: Session, survey_id: int, user: User, answers: dict) -> dict | None:
    survey = survey_repository.get(db, survey_id)
    if survey is None or survey_repository.recipient(db, survey_id, user.id) is None:
        return None
    if survey.status == SurveyStatus.DRAFT:
        return None
    if survey.status == SurveyStatus.CLOSED:
        raise SurveyError("Анкета закрыта — ответы больше не принимаются")
    survey_repository.save_response(db, survey.id, user.id, _clean_answers(survey.questions, answers), _now())
    return get_mine(db, survey_id, user)
