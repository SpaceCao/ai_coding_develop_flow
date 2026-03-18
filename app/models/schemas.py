"""数据模型定义"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class PipelineStage(str, Enum):
    REQUIREMENT = "requirement"
    CODING = "coding"
    REVIEW = "review"
    DEPLOY = "deploy"


class PipelineStatus(str, Enum):
    PENDING = "pending"
    ANALYZING = "analyzing"
    PLAN_READY = "plan_ready"
    PLAN_CONFIRMED = "plan_confirmed"
    CODING = "coding"
    PR_CREATED = "pr_created"
    REVIEWING = "reviewing"
    REVIEW_PASSED = "review_passed"
    REVIEW_FAILED = "review_failed"
    APPROVAL_PENDING = "approval_pending"
    APPROVED = "approved"
    MERGING = "merging"
    DEPLOYING = "deploying"
    DEPLOYED = "deployed"
    FAILED = "failed"


class PipelineTask(BaseModel):
    task_id: str = Field(default_factory=lambda: "")
    title: str = ""
    requirement: str = ""
    tech_plan: str = ""
    iteration: str = ""  # 所属迭代，如 "v1.2.0" / "Sprint-3"
    stage: PipelineStage = PipelineStage.REQUIREMENT
    status: PipelineStatus = PipelineStatus.PENDING

    # GitHub
    branch_name: str = ""
    pr_number: int = 0
    pr_url: str = ""

    # 飞书
    feishu_chat_id: str = ""
    feishu_user_id: str = ""
    feishu_message_id: str = ""
    approval_instance_code: str = ""
    bitable_record_id: str = ""

    # 飞书云文档
    tech_plan_doc_url: str = ""
    review_doc_url: str = ""

    # AI 审查
    review_comments: str = ""
    review_passed: bool = False

    # 时间
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class AIRequest(BaseModel):
    """AI 调用请求"""
    task_type: str  # requirements-analysis / code-generation / code-review / fast-chat
    prompt: str
    system_prompt: str = ""
    temperature: float = 0.7
    max_tokens: int = 4096


class AIResponse(BaseModel):
    """AI 调用响应"""
    content: str
    model: str = ""
    usage: dict = Field(default_factory=dict)
