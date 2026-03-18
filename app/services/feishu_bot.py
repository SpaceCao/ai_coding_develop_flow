"""飞书 Bot 消息服务"""

from __future__ import annotations

import json
import logging

import lark_oapi as lark
from lark_oapi.api.im.v1 import (
    CreateMessageRequest,
    CreateMessageRequestBody,
    CreateMessageResponse,
)

from config.settings import settings

logger = logging.getLogger(__name__)

_client: lark.Client | None = None


def get_feishu_client() -> lark.Client:
    global _client
    if _client is None:
        _client = (
            lark.Client.builder()
            .app_id(settings.feishu_app_id)
            .app_secret(settings.feishu_app_secret)
            .domain(lark.FEISHU_DOMAIN)
            .log_level(lark.LogLevel.DEBUG if settings.is_dev else lark.LogLevel.INFO)
            .build()
        )
    return _client


async def send_text(chat_id: str, text: str) -> bool:
    """发送文本消息到群聊"""
    client = get_feishu_client()
    req = (
        CreateMessageRequest.builder()
        .receive_id_type("chat_id")
        .request_body(
            CreateMessageRequestBody.builder()
            .receive_id(chat_id)
            .msg_type("text")
            .content(json.dumps({"text": text}))
            .build()
        )
        .build()
    )
    resp: CreateMessageResponse = await client.im.v1.message.acreate(req)
    if not resp.success():
        logger.error("发送文本消息失败: code=%s msg=%s", resp.code, resp.msg)
        return False
    return True


async def send_card(chat_id: str, card: dict) -> bool:
    """发送卡片消息到群聊"""
    client = get_feishu_client()
    req = (
        CreateMessageRequest.builder()
        .receive_id_type("chat_id")
        .request_body(
            CreateMessageRequestBody.builder()
            .receive_id(chat_id)
            .msg_type("interactive")
            .content(json.dumps(card))
            .build()
        )
        .build()
    )
    resp: CreateMessageResponse = await client.im.v1.message.acreate(req)
    if not resp.success():
        logger.error("发送卡片消息失败: code=%s msg=%s", resp.code, resp.msg)
        return False
    return True


def build_pipeline_card(
    title: str,
    status: str,
    detail: str,
    color: str = "blue",
    actions: list[dict] | None = None,
) -> dict:
    """构建流水线状态卡片"""
    elements = [
        {
            "tag": "div",
            "text": {"tag": "lark_md", "content": f"**状态**: {status}\n\n{detail}"},
        }
    ]
    if actions:
        elements.append({"tag": "action", "actions": actions})
    return {
        "header": {"title": {"tag": "plain_text", "content": title}, "template": color},
        "elements": elements,
    }


def build_confirm_button(task_id: str) -> list[dict]:
    """构建确认/拒绝按钮"""
    return [
        {
            "tag": "button",
            "text": {"tag": "plain_text", "content": "确认方案"},
            "type": "primary",
            "value": {"action": "confirm_plan", "task_id": task_id},
        },
        {
            "tag": "button",
            "text": {"tag": "plain_text", "content": "修改需求"},
            "type": "default",
            "value": {"action": "revise_plan", "task_id": task_id},
        },
    ]
