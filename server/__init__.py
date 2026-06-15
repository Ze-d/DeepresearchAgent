# server/__init__.py
import logging
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from deepresearch.config import settings
from server.routes import router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动/关闭日志。"""
    logger.info(
        "DeepResearch Server starting on %s:%d",
        settings.server_host,
        settings.server_port,
    )
    yield
    logger.info("DeepResearch Server shutting down")


def create_app() -> FastAPI:
    """创建并配置 FastAPI 应用。"""
    app = FastAPI(
        title="DeepResearch Agent API",
        version="0.2.0",
        description="LangGraph-based DeepResearch Agent — Web API",
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # API routes
    app.include_router(router)

    # 静态文件（Vue 构建产物 — 构建后自动 mount）
    web_dist = Path(__file__).resolve().parent.parent / "web" / "dist"
    if web_dist.exists():
        app.mount(
            "/", StaticFiles(directory=str(web_dist), html=True), name="static"
        )

    return app


app = create_app()
