"""部署相关异步任务"""

from __future__ import annotations

import asyncio
import logging

from app.services.feishu_bot import build_pipeline_card, send_card
from app.services.feishu_bitable import sync_task_status
from app.services.feishu_notify import send_webhook_text
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.deploy_tasks.notify_deploy_status")
def notify_deploy_status(
    task_id: str,
    status: str,
    detail: str = "",
    chat_id: str = "",
    record_id: str = "",
) -> dict:
    """部署状态通知"""
    return asyncio.get_event_loop().run_until_complete(
        _notify_deploy_async(task_id, status, detail, chat_id, record_id)
    )


async def _notify_deploy_async(
    task_id: str,
    status: str,
    detail: str,
    chat_id: str,
    record_id: str,
) -> dict:
    success = status == "success"
    color = "green" if success else "red"
    status_text = "部署成功" if success else "部署失败"

    if chat_id:
        card = build_pipeline_card(
            title=f"部署通知 - {task_id}",
            status=status_text,
            detail=detail or f"任务 {task_id} {status_text}",
            color=color,
        )
        await send_card(chat_id, card)

    await send_webhook_text(f"[AI Pipeline] {task_id} {status_text}")

    if record_id:
        await sync_task_status(record_id, "已部署" if success else "部署失败")

    return {"status": status_text, "task_id": task_id}
