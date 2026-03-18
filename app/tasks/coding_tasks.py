"""AI 编码异步任务"""

from __future__ import annotations

import asyncio
import logging
import uuid

from app.models.schemas import AIRequest
from app.services import ai_service, github_service
from app.services.feishu_bot import build_pipeline_card, send_card
from app.services.feishu_bitable import sync_task_status, F_PR_LINK, F_BRANCH
from app.services.feishu_notify import send_webhook_text
from app.prompts.code_gen import CODE_GEN_SYSTEM, CODE_GEN_USER
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.coding_tasks.generate_code")
def generate_code(
    task_id: str,
    tech_plan: str,
    chat_id: str = "",
    record_id: str = "",
) -> dict:
    """AI 生成代码并创建 PR"""
    return asyncio.get_event_loop().run_until_complete(
        _generate_code_async(task_id, tech_plan, chat_id, record_id)
    )


async def _generate_code_async(
    task_id: str,
    tech_plan: str,
    chat_id: str,
    record_id: str,
) -> dict:
    from config.settings import settings

    # 1. AI 生成代码
    prompt = CODE_GEN_USER.format(
        tech_plan=tech_plan,
        repo=settings.github_repo,
        base_branch="main",
    )
    ai_resp = await ai_service.ai_completion(
        AIRequest(
            task_type="code-generation",
            prompt=prompt,
            system_prompt=CODE_GEN_SYSTEM,
            temperature=0.3,
            max_tokens=8192,
        )
    )

    # 2. 解析代码块
    files = github_service.parse_code_blocks(ai_resp.content)
    if not files:
        logger.warning("AI 未生成有效代码块, task_id=%s", task_id)
        return {"status": "no_code", "task_id": task_id}

    # 3. 创建分支 + 提交 + PR
    branch = f"ai/{task_id}"
    github_service.create_branch(branch)
    github_service.commit_files(branch, files, f"feat: AI generated code for {task_id}")
    pr_number, pr_url = github_service.create_pull_request(
        branch=branch,
        title=f"[AI] {task_id}",
        body=f"由 AI 自动生成\n\n技术方案:\n{tech_plan[:500]}",
    )

    # 4. 飞书通知
    if chat_id:
        card = build_pipeline_card(
            title="代码已生成",
            status="PR 已创建",
            detail=f"**PR**: [#{pr_number}]({pr_url})\n**分支**: `{branch}`\n**文件数**: {len(files)}",
            color="green",
        )
        await send_card(chat_id, card)

    await send_webhook_text(f"[AI Pipeline] PR #{pr_number} 已创建: {pr_url}")

    # 5. 多维表格同步
    if record_id:
        await sync_task_status(
            record_id, "编码完成",
            **{F_PR_LINK: pr_url, F_BRANCH: branch},
        )

    return {"status": "pr_created", "pr_number": pr_number, "pr_url": pr_url}
