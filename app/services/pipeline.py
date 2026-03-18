"""流水线编排引擎 - 状态机驱动"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime

from app.models.schemas import AIRequest, PipelineStage, PipelineStatus, PipelineTask
from app.prompts.requirement import REQUIREMENT_ANALYSIS_SYSTEM, REQUIREMENT_ANALYSIS_USER
from app.services import ai_service
from app.services.feishu_bitable import (
    F_CREATED_AT,
    F_ITERATION,
    F_OWNER,
    F_REQUIREMENT,
    F_STATUS,
    F_TASK_ID,
    F_TECH_PLAN,
    F_TECH_PLAN_DOC,
    F_UPDATED_AT,
    create_record,
    sync_task_status,
    _now_ms,
)
from app.services.feishu_doc import create_and_write_doc
from app.services.feishu_bot import build_confirm_button, build_pipeline_card, send_card
from app.tasks.coding_tasks import generate_code
from app.tasks.review_tasks import review_pr

logger = logging.getLogger(__name__)

# 内存任务存储（生产环境应替换为数据库）
_tasks: dict[str, PipelineTask] = {}


def get_task(task_id: str) -> PipelineTask | None:
    return _tasks.get(task_id)


def list_tasks() -> list[PipelineTask]:
    return list(_tasks.values())


async def start_pipeline(
    requirement: str,
    chat_id: str = "",
    feishu_user_id: str = "",
    iteration: str = "Backlog",
) -> PipelineTask:
    """启动流水线：接收需求 → AI 分析 → 返回技术方案"""
    task_id = uuid.uuid4().hex[:8]
    task = PipelineTask(
        task_id=task_id,
        requirement=requirement,
        iteration=iteration,
        feishu_chat_id=chat_id,
        feishu_user_id=feishu_user_id,
        status=PipelineStatus.ANALYZING,
    )
    _tasks[task_id] = task

    # 多维表格创建记录
    now = _now_ms()
    record_id = await create_record({
        F_TASK_ID: task_id,
        F_REQUIREMENT: requirement[:500],
        F_ITERATION: iteration,
        F_STATUS: "分析中",
        F_OWNER: [{"id": feishu_user_id}] if feishu_user_id else [],
        F_CREATED_AT: now,
        F_UPDATED_AT: now,
    })
    if record_id:
        task.bitable_record_id = record_id

    # AI 需求分析
    ai_resp = await ai_service.ai_completion(
        AIRequest(
            task_type="requirements-analysis",
            prompt=REQUIREMENT_ANALYSIS_USER.format(requirement=requirement),
            system_prompt=REQUIREMENT_ANALYSIS_SYSTEM,
            temperature=0.5,
        )
    )
    task.tech_plan = ai_resp.content
    task.status = PipelineStatus.PLAN_READY
    task.updated_at = datetime.now()

    # 技术方案写入飞书云文档
    _, doc_url = await create_and_write_doc(
        title=f"技术方案 - {task_id}",
        content=task.tech_plan,
    )
    task.tech_plan_doc_url = doc_url

    # 飞书卡片回复（含文档链接）
    if chat_id:
        doc_link = f"\n\n[查看完整技术方案文档]({doc_url})" if doc_url else ""
        card = build_pipeline_card(
            title=f"技术方案 - {task_id}",
            status="待确认",
            detail=task.tech_plan[:600] + doc_link,
            color="blue",
            actions=build_confirm_button(task_id),
        )
        await send_card(chat_id, card)

    if task.bitable_record_id:
        extra: dict = {F_TECH_PLAN: task.tech_plan[:2000]}
        if doc_url:
            extra[F_TECH_PLAN_DOC] = {"text": "技术方案", "link": doc_url}
        await sync_task_status(
            task.bitable_record_id,
            "方案待确认",
            **extra,
        )

    return task


async def confirm_plan(task_id: str) -> PipelineTask | None:
    """确认技术方案 → 触发 AI 编码"""
    task = _tasks.get(task_id)
    if not task or task.status != PipelineStatus.PLAN_READY:
        return None

    task.status = PipelineStatus.CODING
    task.stage = PipelineStage.CODING
    task.updated_at = datetime.now()

    # 异步触发 AI 编码
    generate_code.delay(
        task_id=task.task_id,
        tech_plan=task.tech_plan,
        chat_id=task.feishu_chat_id,
        record_id=task.bitable_record_id,
    )
    return task


async def trigger_review(task_id: str, pr_number: int, pr_url: str) -> PipelineTask | None:
    """PR 创建后触发 AI 审查"""
    task = _tasks.get(task_id)
    if not task:
        return None

    task.pr_number = pr_number
    task.pr_url = pr_url
    task.status = PipelineStatus.REVIEWING
    task.stage = PipelineStage.REVIEW
    task.updated_at = datetime.now()

    review_pr.delay(
        task_id=task.task_id,
        pr_number=pr_number,
        chat_id=task.feishu_chat_id,
        record_id=task.bitable_record_id,
        feishu_user_id=task.feishu_user_id,
    )
    return task


async def on_approval_result(task_id: str, approved: bool) -> PipelineTask | None:
    """审批结果回调 → 合并 PR 或标记失败"""
    from app.services import github_service

    task = _tasks.get(task_id)
    if not task:
        return None

    if approved and task.pr_number:
        task.status = PipelineStatus.MERGING
        github_service.merge_pull_request(task.pr_number)
        task.status = PipelineStatus.DEPLOYING
        task.stage = PipelineStage.DEPLOY
    else:
        task.status = PipelineStatus.FAILED

    task.updated_at = datetime.now()
    return task
