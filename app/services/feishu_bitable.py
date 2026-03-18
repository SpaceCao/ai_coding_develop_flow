"""飞书多维表格服务"""

from __future__ import annotations

import logging
from datetime import datetime

from lark_oapi.api.bitable.v1 import (
    AppTableRecord,
    BatchCreateAppTableRecordRequest,
    BatchCreateAppTableRecordRequestBody,
    BatchUpdateAppTableRecordRequest,
    BatchUpdateAppTableRecordRequestBody,
    ListAppTableRecordRequest,
)

from app.services.feishu_bot import get_feishu_client
from config.settings import settings

logger = logging.getLogger(__name__)

# ── 多维表格字段名常量 ──
F_TASK_ID = "任务ID"
F_REQUIREMENT = "需求"
F_TECH_PLAN = "技术方案"
F_ITERATION = "迭代"
F_TECH_PLAN_DOC = "技术方案文档"
F_REVIEW_DOC = "审查报告文档"
F_STATUS = "状态"
F_OWNER = "负责人"
F_PR_LINK = "PR链接"
F_BRANCH = "分支名"
F_REVIEW_RESULT = "AI审查结论"
F_APPROVAL_CODE = "审批单号"
F_CREATED_AT = "创建时间"
F_UPDATED_AT = "更新时间"


async def create_record(fields: dict) -> str | None:
    """在多维表格中创建一条记录，返回 record_id"""
    client = get_feishu_client()
    req = (
        BatchCreateAppTableRecordRequest.builder()
        .app_token(settings.feishu_bitable_app_token)
        .table_id(settings.feishu_bitable_table_id)
        .request_body(
            BatchCreateAppTableRecordRequestBody.builder()
            .records([AppTableRecord.builder().fields(fields).build()])
            .build()
        )
        .build()
    )
    resp = await client.bitable.v1.app_table_record.abatch_create(req)
    if not resp.success():
        logger.error("创建多维表格记录失败: %s %s", resp.code, resp.msg)
        return None
    records = resp.data.records
    return records[0].record_id if records else None


async def update_record(record_id: str, fields: dict) -> bool:
    """更新多维表格记录"""
    client = get_feishu_client()
    req = (
        BatchUpdateAppTableRecordRequest.builder()
        .app_token(settings.feishu_bitable_app_token)
        .table_id(settings.feishu_bitable_table_id)
        .request_body(
            BatchUpdateAppTableRecordRequestBody.builder()
            .records([
                AppTableRecord.builder().record_id(record_id).fields(fields).build()
            ])
            .build()
        )
        .build()
    )
    resp = await client.bitable.v1.app_table_record.abatch_update(req)
    if not resp.success():
        logger.error("更新多维表格记录失败: %s %s", resp.code, resp.msg)
        return False
    return True


async def sync_task_status(record_id: str, status: str, **extra_fields: str) -> bool:
    """同步流水线任务状态到多维表格，自动附带更新时间"""
    fields: dict = {
        F_STATUS: status,
        F_UPDATED_AT: _now_ms(),
        **extra_fields,
    }
    return await update_record(record_id, fields)


def _now_ms() -> int:
    """当前时间戳（毫秒），飞书日期字段要求"""
    return int(datetime.now().timestamp() * 1000)
