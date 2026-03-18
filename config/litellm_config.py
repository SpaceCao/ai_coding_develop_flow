"""LiteLLM 多模型路由配置"""

from __future__ import annotations

from litellm import Router
from litellm.router import RetryPolicy

from config.settings import settings


def _build_model_list() -> list[dict]:
    return [
        # 需求分析: GPT-4o 主力, Claude 备选
        {
            "model_name": "requirements-analysis",
            "litellm_params": {
                "model": "gpt-4o",
                "api_key": settings.openai_api_key,
                "order": 1,
            },
        },
        {
            "model_name": "requirements-analysis",
            "litellm_params": {
                "model": "claude-sonnet-4-20250514",
                "api_key": settings.anthropic_api_key,
                "order": 2,
            },
        },
        # 代码生成: Claude 主力, GPT-4o 备选
        {
            "model_name": "code-generation",
            "litellm_params": {
                "model": "claude-sonnet-4-20250514",
                "api_key": settings.anthropic_api_key,
                "order": 1,
            },
        },
        {
            "model_name": "code-generation",
            "litellm_params": {
                "model": "gpt-4o",
                "api_key": settings.openai_api_key,
                "order": 2,
            },
        },
        # 代码审查: Claude
        {
            "model_name": "code-review",
            "litellm_params": {
                "model": "claude-sonnet-4-20250514",
                "api_key": settings.anthropic_api_key,
            },
        },
        # 轻量任务: DeepSeek
        {
            "model_name": "fast-chat",
            "litellm_params": {
                "model": "deepseek/deepseek-chat",
                "api_key": settings.deepseek_api_key,
            },
        },
    ]


def create_router() -> Router:
    return Router(
        model_list=_build_model_list(),
        num_retries=3,
        retry_after=2,
        allowed_fails=2,
        cooldown_time=60,
        enable_pre_call_checks=True,
        retry_policy=RetryPolicy(
            RateLimitErrorRetries=3,
            TimeoutErrorRetries=2,
            AuthenticationErrorRetries=0,
        ),
    )
