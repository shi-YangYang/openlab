"""FastAPI application instance: lifespan, CORS, and router registration."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import database
from .arxiv import ArxivClient
from .config import settings
from .routes import (
    agent,
    analyses,
    experiments,
    innovations,
    llm,
    papers,
    platforms,
    reviews,
    search,
    servers,
    translation,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    database.init_db()
    app.state.arxiv_client = ArxivClient(
        interval=settings.arxiv_request_interval,
        max_retries=settings.arxiv_max_retries,
    )
    yield
    await app.state.arxiv_client.aclose()


app = FastAPI(title="openlab backend", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok"}


# Registration order below mirrors the former single-module main.py. Greedy
# ``{arxiv_id:path}`` ordering keeps .../translation/pdf (routes/translation.py)
# ahead of .../pdf (routes/papers.py).
app.include_router(papers.download_router, prefix="/api/download")
app.include_router(translation.router, prefix="/api/papers")
app.include_router(papers.router, prefix="/api/papers")
app.include_router(agent.router, prefix="/api/agent")
app.include_router(servers.router, prefix="/api/servers")
app.include_router(experiments.router, prefix="/api/experiments")
app.include_router(experiments.runs_router, prefix="/api/experiment-runs")
app.include_router(llm.router, prefix="/api/llm")
app.include_router(platforms.router, prefix="/api/platforms")
app.include_router(search.router, prefix="/api/search")
app.include_router(innovations.router, prefix="/api/innovations")
app.include_router(analyses.analyze_router, prefix="/api/analyze")
app.include_router(analyses.router, prefix="/api/analyses")
app.include_router(reviews.review_router, prefix="/api/review")
app.include_router(reviews.router, prefix="/api/reviews")
