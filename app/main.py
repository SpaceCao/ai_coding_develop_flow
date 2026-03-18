"""FastAPI 应用入口"""

from __future__ import annotations

import logging

from fastapi import FastAPI

from app.api.feishu_events import router as feishu_router
from app.api.webhooks import router as github_router
from app.services.pipeline import get_task, list_tasks
from config.settings import settings

logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

app = FastAPI(
    title="AI Coding Pipeline",
    description="基于飞书的 AI 编码开发流水线",
    version="0.1.0",
)

app.include_router(feishu_router)
app.include_router(github_router)


@app.get("/")
async def root() -> dict:
    return {"service": "ai-coding-pipeline", "status": "running"}


@app.get("/tasks")
async def api_list_tasks() -> list[dict]:
    """查看所有流水线任务"""
    return [t.model_dump() for t in list_tasks()]


@app.get("/tasks/{task_id}")
async def api_get_task(task_id: str) -> dict:
    task = get_task(task_id)
    if not task:
        return {"error": "task not found"}
    return task.model_dump()
