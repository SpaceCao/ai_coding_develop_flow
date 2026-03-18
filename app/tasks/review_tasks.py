"""AI 代码审查异步任务"""

from __future__ import annotations

import asyncio
import logging

from app.models.schemas import AIRequest
from app.services import ai_service, github_service
from app.services.feishu_approval import build_code_merge_form, create_approval_instance
from app.services.feishu_bot import build_pipeline_card, send_card
from app.services.feishu_bitable import sync_task_status, F_REVIEW_RESULT, F_REVIEW_DOC, F_APPROVAL_CODE
from app.services.feishu_doc import create_and_write_doc
from app.services.feishu_notify import send_webhook_text
from app.prompts.code_review import CODE_REVIEW_SYSTEM, CODE_REVIEW_USER
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.review_tasks.review_pr")
def review_pr(
    task_id: str,
    pr_number: int,
    chat_id: str = "",
    record_id: str = "",
    feishu_user_id: str = "",
) -> dict:
    """AI 审查 PR 代码"""
    return asyncio.get_event_loop().run_until_complete(
        _review_pr_async(task_id, pr_number, chat_id, record_id, feishu_user_id)
    )


async def _review_pr_async(
    task_id: str,
    pr_number: int,
    chat_id: str,
    record_id: str,
    feishu_user_id: str,
) -> dict:
    # 1. 获取 PR diff
    diff = github_service.get_pr_diff(pr_number)

    # 2. AI 审查
    prompt = CODE_REVIEW_USER.format(
        pr_title=f"[AI] {task_id}",
        pr_description="AI 自动生成的代码",
        diff=diff,
    )
    ai_resp = await ai_service.ai_completion(
        AIRequest(
            task_type="code-review",
            prompt=prompt,
            system_prompt=CODE_REVIEW_SYSTEM,
            temperature=0.2,
            max_tokens=4096,
        )
    )
    review_content = ai_resp.content
    passed = "✅ 通过" in review_content

    # 3. 审查报告写入飞书云文档
    _, review_doc_url = await create_and_write_doc(
        title=f"代码审查报告 - {task_id} PR #{pr_number}",
        content=review_content,
    )

    # 4. 添加 PR Comment
    github_service.add_pr_comment(pr_number, review_content)

    # 5. 飞书通知审查结果（含文档链接）
    if chat_id:
        color = "green" if passed else "orange"
        doc_link = f"\n\n[查看完整审查报告]({review_doc_url})" if review_doc_url else ""
        card = build_pipeline_card(
            title=f"代码审查 - PR #{pr_number}",
            status="审查通过" if passed else "需要修改",
            detail=review_content[:400] + doc_link,
            color=color,
        )
        await send_card(chat_id, card)

    # 6. 审查通过 → 触发飞书审批
    instance_code = ""
    if passed and feishu_user_id:
        form = build_code_merge_form(task_id, f"PR #{pr_number}", review_content[:200])
        instance_code = await create_approval_instance(feishu_user_id, form) or ""

    # 7. 多维表格同步
    if record_id:
        status = "审查通过" if passed else "审查未通过"
        extra: dict = {F_REVIEW_RESULT: "通过" if passed else "需修改"}
        if review_doc_url:
            extra[F_REVIEW_DOC] = {"text": "审查报告", "link": review_doc_url}
        if instance_code:
            extra[F_APPROVAL_CODE] = instance_code
        await sync_task_status(record_id, status, **extra)

    await send_webhook_text(
        f"[AI Pipeline] PR #{pr_number} 审查{'通过' if passed else '未通过'}"
    )

    return {
        "status": "review_passed" if passed else "review_failed",
        "pr_number": pr_number,
        "passed": passed,
        "approval_instance": instance_code,
    }
