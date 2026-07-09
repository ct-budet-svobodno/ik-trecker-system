from fastapi import APIRouter

from app.api.routes import (
    auth,
    directions,
    editorial_posts,
    events,
    leadership_notes,
    leadership_tasks,
    push,
    tasks,
    users,
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
api_router.include_router(push.router, prefix="/push", tags=["push"])
