"""FastAPI application instance: lifespan, CORS, and router registration."""
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import database
from .agent import sessions
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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    database.init_db()
    # Startup recovery (spec-033 FR-1): a fresh process cannot have live runs,
    # so residual running/status flags are zombie state from a crash.
    sessions.reset_running_states()
    # Startup recovery (spec-035 FR-1/FR-4): residual ``downloading`` papers
    # and ``running``/``paused`` experiment runs are zombie state too.
    database.reset_stale_downloads()
    database.reset_stale_experiment_runs()
    app.state.arxiv_client = ArxivClient(
        interval=settings.arxiv_request_interval,
        max_retries=settings.arxiv_max_retries,
    )
    # Startup backfill (spec-037 NFR-3): build the FTS index off the event
    # loop when the library has papers but the index is empty. Idempotent,
    # never blocks startup, failures only log.
    async def _backfill_fts() -> None:
        try:
            count = await asyncio.to_thread(database.rebuild_paper_fts_if_empty)
            if count:
                logger.info("FTS 索引已自动重建: %d 篇", count)
        except Exception:
            logger.warning("FTS 索引启动重建失败", exc_info=True)

    asyncio.create_task(_backfill_fts())
    logger.info("openlab backend 启动")
    yield
    await app.state.arxiv_client.aclose()
    logger.info("openlab backend 关闭")


app = FastAPI(title="openlab backend", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Catch-all for unhandled errors (spec-034 FR-4).

    HTTPException and validation errors keep FastAPI's own handlers (more
    specific registrations win); this only fires for truly unhandled ones.
    """
    logger.error(
        "未处理异常: %s %s: %r", request.method, request.url.path, exc, exc_info=exc
    )
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


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
