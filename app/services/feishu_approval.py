"""飞书审批流服务"""

from __future__ import annotations

import json
import logging

from lark_oapi.api.approval.v4 import (
    CreateInstanceRequest,
    CreateInstanceRequestBody,
    GetInstanceRequest,
    NodeApprover,
)

from app.services.feishu_bot import get_feishu_client
from config.settings import settings

logger = logging.getLogger(__name__)


async def create_approval_instance(
    user_id: str,
    form_data: list[dict],
    approver_ids: list[str] | None = None,
) -> str | None:
    """创建审批实例，返回 instance_code"""
    client = get_feishu_client()

    builder = (
        CreateInstanceRequestBody.builder()
        .approval_code(settings.feishu_approval_code)
        .user_id(user_id)
        .form(json.dumps(form_data, ensure_ascii=False))
    )

    req = CreateInstanceRequest.builder().request_body(builder.build()).build()
    resp = await client.approval.v4.instance.acreate(req)
    if not resp.success():
        logger.error("创建审批实例失败: %s %s", resp.code, resp.msg)
        return None
    return resp.data.instance_code


async def get_approval_status(instance_code: str) -> str | None:
    """查询审批实例状态"""
    client = get_feishu_client()
    req = GetInstanceRequest.builder().instance_id(instance_code).build()
    resp = await client.approval.v4.instance.aget(req)
    if not resp.success():
        logger.error("查询审批状态失败: %s %s", resp.code, resp.msg)
        return None
    return resp.data.status


def build_code_merge_form(task_id: str, pr_url: str, review_summary: str) -> list[dict]:
    """构建代码合并审批表单"""
    return [
        {"id": "task_id", "type": "input", "value": task_id},
        {"id": "pr_url", "type": "input", "value": pr_url},
        {"id": "review_summary", "type": "textarea", "value": review_summary},
    ]
