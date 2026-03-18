"""飞书 Webhook 群通知"""

from __future__ import annotations

import logging

import httpx

from config.settings import settings

logger = logging.getLogger(__name__)


async def send_webhook_text(text: str) -> bool:
    """通过 Webhook 发送文本消息到群"""
    url = settings.feishu_bot_webhook_url
    if not url:
        logger.warning("FEISHU_BOT_WEBHOOK_URL 未配置")
        return False
    payload = {"msg_type": "text", "content": {"text": text}}
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, json=payload)
    if resp.status_code != 200:
        logger.error("Webhook 发送失败: %s", resp.text)
        return False
    return True


async def send_webhook_card(card: dict) -> bool:
    """通过 Webhook 发送卡片消息到群"""
    url = settings.feishu_bot_webhook_url
    if not url:
        logger.warning("FEISHU_BOT_WEBHOOK_URL 未配置")
        return False
    payload = {"msg_type": "interactive", "card": card}
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, json=payload)
    if resp.status_code != 200:
        logger.error("Webhook 卡片发送失败: %s", resp.text)
        return False
    return True
