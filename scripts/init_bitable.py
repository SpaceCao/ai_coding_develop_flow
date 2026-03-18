#!/usr/bin/env python3
"""飞书多维表格初始化脚本

自动在指定多维表格中创建流水线所需的全部字段。
运行前确保 .env 已配置 FEISHU_APP_ID, FEISHU_APP_SECRET, FEISHU_BITABLE_APP_TOKEN。

用法:
    python scripts/init_bitable.py
    python scripts/init_bitable.py --table-name "AI开发流水线"
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import httpx

# 加载项目根目录的 .env
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dotenv import load_dotenv

load_dotenv()

from config.settings import settings

BASE_URL = "https://open.feishu.cn/open-apis"

# ── 字段定义 ──
# type: 1=文本, 2=数字, 3=单选, 4=多选, 5=日期, 7=复选框, 11=人员, 15=链接, 22=多行文本
FIELDS = [
    {"field_name": "任务ID", "type": 1},
    {
        "field_name": "迭代",
        "type": 3,
        "property": {
            "options": [
                {"name": "Backlog"},
                {"name": "Sprint-1"},
                {"name": "Sprint-2"},
                {"name": "Sprint-3"},
                {"name": "Sprint-4"},
                {"name": "Sprint-5"},
            ]
        },
    },
    {"field_name": "需求", "type": 22},
    {"field_name": "技术方案", "type": 22},
    {"field_name": "技术方案文档", "type": 15},
    {
        "field_name": "状态",
        "type": 3,
        "property": {
            "options": [
                {"name": "分析中"},
                {"name": "方案待确认"},
                {"name": "编码中"},
                {"name": "编码完成"},
                {"name": "审查中"},
                {"name": "审查通过"},
                {"name": "审查未通过"},
                {"name": "审批中"},
                {"name": "已部署"},
                {"name": "部署失败"},
            ]
        },
    },
    {"field_name": "负责人", "type": 11},
    {"field_name": "PR链接", "type": 15},
    {"field_name": "分支名", "type": 1},
    {
        "field_name": "AI审查结论",
        "type": 3,
        "property": {"options": [{"name": "通过"}, {"name": "需修改"}]},
    },
    {"field_name": "审查报告文档", "type": 15},
    {"field_name": "审批单号", "type": 1},
    {"field_name": "创建时间", "type": 5},
    {"field_name": "更新时间", "type": 5},
]


async def get_tenant_token() -> str:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{BASE_URL}/auth/v3/tenant_access_token/internal",
            json={
                "app_id": settings.feishu_app_id,
                "app_secret": settings.feishu_app_secret,
            },
        )
    data = resp.json()
    token = data.get("tenant_access_token", "")
    if not token:
        raise RuntimeError(f"获取 tenant_access_token 失败: {data}")
    return token


async def create_table_if_needed(app_token: str, table_name: str, headers: dict) -> str:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{BASE_URL}/bitable/v1/apps/{app_token}/tables",
            headers=headers,
            json={"table": {"name": table_name, "default_view_name": "默认视图"}},
        )
    data = resp.json()
    table_id = data.get("data", {}).get("table_id", "")
    if not table_id:
        raise RuntimeError(f"创建数据表失败: {data}")
    return table_id


async def create_field(app_token: str, table_id: str, field: dict, headers: dict) -> None:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{BASE_URL}/bitable/v1/apps/{app_token}/tables/{table_id}/fields",
            headers=headers,
            json=field,
        )
    data = resp.json()
    if data.get("code") != 0:
        print(f"[WARN] 创建字段失败 {field['field_name']}: {data}")
    else:
        print(f"[OK] 已创建字段: {field['field_name']}")


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--table-name", default="AI开发流水线")
    args = parser.parse_args()

    if not settings.feishu_bitable_app_token:
        raise RuntimeError("请先在 .env 配置 FEISHU_BITABLE_APP_TOKEN")

    token = await get_tenant_token()
    headers = {"Authorization": f"Bearer {token}"}

    table_id = settings.feishu_bitable_table_id
    if not table_id:
        table_id = await create_table_if_needed(settings.feishu_bitable_app_token, args.table_name, headers)
        print(f"[OK] 已创建数据表: {args.table_name} ({table_id})")
    else:
        print(f"[INFO] 使用已有数据表: {table_id}")

    for field in FIELDS:
        await create_field(settings.feishu_bitable_app_token, table_id, field, headers)
        time.sleep(0.2)

    print("\n初始化完成。")
    print(f"请将 FEISHU_BITABLE_TABLE_ID 设置为: {table_id}")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
