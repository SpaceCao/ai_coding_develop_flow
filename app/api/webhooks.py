"""GitHub Webhook 路由"""

from __future__ import annotations

import hashlib
import hmac
import logging

from fastapi import APIRouter, Header, HTTPException, Request

from app.services.pipeline import trigger_review
from app.tasks.deploy_tasks import notify_deploy_status
from config.settings import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/github", tags=["github"])


def _verify_signature(payload: bytes, signature: str) -> bool:
    """验证 GitHub webhook 签名"""
    if not settings.github_webhook_secret:
        return True
    expected = "sha256=" + hmac.new(
        settings.github_webhook_secret.encode(),
        payload,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


@router.post("/webhook")
async def github_webhook(
    request: Request,
    x_github_event: str = Header(""),
    x_hub_signature_256: str = Header(""),
) -> dict:
    """GitHub Webhook 回调"""
    payload = await request.body()
    if not _verify_signature(payload, x_hub_signature_256):
        raise HTTPException(status_code=401, detail="Invalid signature")

    body = await request.json()

    if x_github_event == "pull_request":
        await _handle_pr_event(body)
    elif x_github_event == "workflow_run":
        await _handle_workflow_event(body)

    return {"status": "ok"}


async def _handle_pr_event(body: dict) -> None:
    """处理 PR 事件 — PR 创建时触发 AI 审查"""
    action = body.get("action", "")
    pr = body.get("pull_request", {})
    pr_number = pr.get("number", 0)
    branch = pr.get("head", {}).get("ref", "")

    if action != "opened" or not branch.startswith("ai/"):
        return

    task_id = branch.removeprefix("ai/")
    logger.info("PR #%d opened for task %s, triggering review", pr_number, task_id)
    await trigger_review(task_id, pr_number, pr.get("html_url", ""))


async def _handle_workflow_event(body: dict) -> None:
    """处理 GitHub Actions workflow 事件 — 部署状态通知"""
    workflow_run = body.get("workflow_run", {})
    conclusion = workflow_run.get("conclusion", "")
    branch = workflow_run.get("head_branch", "")

    if not branch.startswith("ai/"):
        return

    task_id = branch.removeprefix("ai/")
    status = "success" if conclusion == "success" else "failure"
    detail = f"Workflow: {workflow_run.get('name', '')}\nConclusion: {conclusion}"

    notify_deploy_status.delay(task_id=task_id, status=status, detail=detail)
