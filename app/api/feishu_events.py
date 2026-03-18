"""飞书事件回调路由"""

from __future__ import annotations

import json
import logging
import re

from fastapi import APIRouter, Request, Response

from app.services.pipeline import confirm_plan, start_pipeline

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/feishu", tags=["feishu"])

# 匹配 [Sprint-3] 或 [v1.2.0] 等迭代标记
_ITERATION_RE = re.compile(r"^\[([^\]]+)\]\s*")


@router.post("/event")
async def feishu_event(request: Request) -> Response:
    """飞书事件订阅回调（Webhook 模式）"""
    body = await request.json()

    # URL 验证 challenge
    if "challenge" in body:
        return Response(
            content=json.dumps({"challenge": body["challenge"]}),
            media_type="application/json",
        )

    # 事件处理
    event = body.get("event", {})
    event_type = body.get("header", {}).get("event_type", "")

    if event_type == "im.message.receive_v1":
        await _handle_message(event)
    elif event_type == "card.action.trigger":
        await _handle_card_action(event)

    return Response(content="{}", media_type="application/json")


def _parse_iteration(text: str) -> tuple[str, str]:
    """从消息文本中解析迭代标记，返回 (iteration, requirement)

    示例:
        "[Sprint-3] 实现登录功能" -> ("Sprint-3", "实现登录功能")
        "实现登录功能"            -> ("Backlog", "实现登录功能")
    """
    m = _ITERATION_RE.match(text)
    if m:
        return m.group(1), text[m.end():].strip()
    return "Backlog", text


async def _handle_message(event: dict) -> None:
    """处理 Bot 收到的消息"""
    message = event.get("message", {})
    chat_id = message.get("chat_id", "")
    sender_id = event.get("sender", {}).get("sender_id", {}).get("open_id", "")
    msg_type = message.get("message_type", "")

    if msg_type != "text":
        return

    content = json.loads(message.get("content", "{}"))
    text = content.get("text", "").strip()

    if not text:
        return

    iteration, requirement = _parse_iteration(text)

    logger.info("收到需求: %s [%s] (from %s)", requirement[:50], iteration, sender_id)
    await start_pipeline(
        requirement=requirement,
        chat_id=chat_id,
        feishu_user_id=sender_id,
        iteration=iteration,
    )


async def _handle_card_action(event: dict) -> None:
    """处理卡片按钮回调"""
    action = event.get("action", {})
    value = action.get("value", {})
    action_type = value.get("action", "")
    task_id = value.get("task_id", "")

    if not task_id:
        return

    if action_type == "confirm_plan":
        logger.info("方案确认: task_id=%s", task_id)
        await confirm_plan(task_id)
    elif action_type == "revise_plan":
        logger.info("需求修改: task_id=%s", task_id)
