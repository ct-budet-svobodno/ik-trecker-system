from fastapi import APIRouter

from app.api.routes import (
    auth,
    broadcasts,
    checklists,
    directions,
    editorial_posts,
    events,
    games,
    leadership_notes,
    leadership_tasks,
    personal_todos,
    push,
    surveys,
    tasks,
    users,
    zavod,
)

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(directions.router, prefix="/directions", tags=["directions"])
api_router.include_router(tasks.router, prefix="/tasks", tags=["tasks"])
api_router.include_router(events.router, prefix="/events", tags=["events"])
api_router.include_router(
    leadership_notes.router, prefix="/leadership-notes", tags=["leadership-notes"]
)
api_router.include_router(
    leadership_tasks.router, prefix="/leadership-tasks", tags=["leadership-tasks"]
)
api_router.include_router(
    editorial_posts.router, prefix="/editorial-posts", tags=["editorial-posts"]
)
api_router.include_router(
    personal_todos.router, prefix="/personal-todos", tags=["personal-todos"]
)
api_router.include_router(push.router, prefix="/push", tags=["push"])
api_router.include_router(zavod.router, prefix="/zavod", tags=["zavod"])
api_router.include_router(games.router, prefix="/games", tags=["games"])
api_router.include_router(broadcasts.router, prefix="/broadcasts", tags=["broadcasts"])
api_router.include_router(checklists.router, prefix="/checklists", tags=["checklists"])
api_router.include_router(surveys.router, prefix="/surveys", tags=["surveys"])
