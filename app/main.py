import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from app.adapters.encoder import MiniLMEncoder, TextEncoder
from app.api.feed import router as feed_router
from app.api.posts import router as posts_router
from app.api.search import router as search_router
from app.api.social import router as social_router
from app.api.users import router as users_router
from app.db.database import init_db
from app.learned import load_model
from app.repositories.posts import list_posts
from app.services.search import SearchIndex

logger = logging.getLogger(__name__)


def create_app(*, encoder: TextEncoder | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        init_db()
        resolved = encoder if encoder is not None else MiniLMEncoder()
        app.state.encoder = resolved
        app.state.search_index = SearchIndex.build(list_posts(), resolved)
        try:
            app.state.learned_model = load_model()
        except FileNotFoundError:
            app.state.learned_model = None
            logger.warning("Learned feed is unavailable: model file is missing.")
        yield

    application = FastAPI(title="InstaKill", lifespan=lifespan)
    application.include_router(search_router)
    application.include_router(feed_router)
    application.include_router(users_router)
    application.include_router(posts_router)
    application.include_router(social_router)

    @application.get("/")
    def root() -> RedirectResponse:
        return RedirectResponse(url="/docs")

    @application.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    return application


app = create_app()
