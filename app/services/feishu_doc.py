"""飞书云文档服务 - 创建和写入文档"""

from __future__ import annotations

import logging

import httpx

from config.settings import settings

logger = logging.getLogger(__name__)


async def _get_tenant_token() -> str:
    """获取 tenant_access_token"""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
            json={
                "app_id": settings.feishu_app_id,
                "app_secret": settings.feishu_app_secret,
            },
        )
    return resp.json().get("tenant_access_token", "")


async def create_doc(title: str, folder_token: str = "") -> tuple[str, str]:
    """创建飞书云文档，返回 (document_id, doc_url)"""
    token = await _get_tenant_token()
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "title": title,
        "folder_token": folder_token or settings.feishu_doc_folder_token,
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://open.feishu.cn/open-apis/docx/v1/documents",
            headers=headers,
            json=payload,
        )
    doc_data = resp.json().get("data", {}).get("document", {})
    document_id = doc_data.get("document_id", "")
    doc_url = f"https://bytedance.feishu.cn/docx/{document_id}" if document_id else ""

    if not document_id:
        logger.error("创建云文档失败: %s", resp.text)
    else:
        logger.info("创建云文档: %s -> %s", title, doc_url)
    return document_id, doc_url


async def write_doc_content(document_id: str, markdown_content: str) -> bool:
    """向云文档追加内容（按段落拆分为 block 写入）"""
    token = await _get_tenant_token()
    headers = {"Authorization": f"Bearer {token}"}

    blocks = []
    for line in markdown_content.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("### "):
            blocks.append(_heading_block(stripped[4:], level=4))
        elif stripped.startswith("## "):
            blocks.append(_heading_block(stripped[3:], level=3))
        elif stripped.startswith("# "):
            blocks.append(_heading_block(stripped[2:], level=2))
        elif stripped.startswith("- "):
            blocks.append(_bullet_block(stripped[2:]))
        else:
            blocks.append(_text_block(stripped))

    if not blocks:
        return True

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"https://open.feishu.cn/open-apis/docx/v1/documents/{document_id}"
            f"/blocks/{document_id}/children",
            headers=headers,
            json={"children": blocks, "index": -1},
        )
    code = resp.json().get("code", -1)
    if code != 0:
        logger.error("写入云文档失败: %s", resp.text)
        return False
    return True


async def create_and_write_doc(title: str, content: str) -> tuple[str, str]:
    """创建云文档并写入内容，返回 (document_id, doc_url)"""
    document_id, doc_url = await create_doc(title)
    if document_id:
        await write_doc_content(document_id, content)
    return document_id, doc_url


# ── block 构造辅助 ──

def _text_block(text: str) -> dict:
    return {
        "block_type": 2,
        "text": {"elements": [{"text_run": {"content": text}}], "style": {}},
    }


def _heading_block(text: str, level: int = 3) -> dict:
    # heading2=3, heading3=4, heading4=5
    return {
        "block_type": {2: 3, 3: 4, 4: 5}.get(level, 4),
        "heading": {"elements": [{"text_run": {"content": text}}], "style": {}},
    }


def _bullet_block(text: str) -> dict:
    return {
        "block_type": 12,
        "bullet": {"elements": [{"text_run": {"content": text}}], "style": {}},
    }
