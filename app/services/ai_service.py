"""AI 服务封装 - 基于 LiteLLM Router 的多模型调用"""

from __future__ import annotations

import logging

from litellm import Router

from app.models.schemas import AIRequest, AIResponse
from config.litellm_config import create_router

logger = logging.getLogger(__name__)

_router: Router | None = None


def get_router() -> Router:
    global _router
    if _router is None:
        _router = create_router()
    return _router


async def ai_completion(req: AIRequest) -> AIResponse:
    """统一 AI 调用入口"""
    router = get_router()
    messages = []
    if req.system_prompt:
        messages.append({"role": "system", "content": req.system_prompt})
    messages.append({"role": "user", "content": req.prompt})

    try:
        response = await router.acompletion(
            model=req.task_type,
            messages=messages,
            temperature=req.temperature,
            max_tokens=req.max_tokens,
        )
        return AIResponse(
            content=response.choices[0].message.content,
            model=response.model or "",
            usage=dict(response.usage) if response.usage else {},
        )
    except Exception:
        logger.exception("AI completion failed for task_type=%s", req.task_type)
        raise
