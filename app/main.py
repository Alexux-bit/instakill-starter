from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from app.adapters.encoder import MiniLMEncoder, TextEncoder
from app.api.feed import router as feed_router
from app.api.search import router as search_router
from app.db.database import init_db
from app.repositories.posts import list_posts
from app.services.search import SearchIndex


def create_app(*, encoder: TextEncoder | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        init_db()
        resolved = encoder if encoder is not None else MiniLMEncoder()
        app.state.encoder = resolved
        app.state.search_index = SearchIndex.build(list_posts(), resolved)
        yield

    application = FastAPI(title="InstaKill", lifespan=lifespan)
    application.include_router(search_router)
    application.include_router(feed_router)

    @application.get("/")
    def root() -> RedirectResponse:
        return RedirectResponse(url="/docs")

    @application.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    return application


app = create_app()
