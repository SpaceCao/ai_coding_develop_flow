# AI Coding 开发流水线

基于飞书的 AI 辅助编码开发流水线，打通「需求 → 技术方案 → AI 编码 → 代码审查 → 审批 → 部署」全流程，并支持**迭代管理**与**飞书云文档沉淀**。

## 核心能力

- **需求接收**：飞书 Bot 接收需求，自动创建流水线任务
- **技术方案沉淀**：AI 生成完整技术方案，并自动写入飞书云文档
- **迭代管理**：每个任务归属某个迭代（如 `Sprint-3` / `v1.2.0` / `Backlog`）
- **AI 自动编码**：根据已确认方案生成代码并创建 GitHub PR
- **AI 审查沉淀**：代码审查结果同步写入 PR 评论和飞书云文档
- **流程审批**：审查通过后走飞书审批流再合并
- **进度看板**：多维表格统一记录任务、方案、文档、PR、审批和状态

## 架构

```
飞书 Bot / 多维表格 / 云文档
            │
            ▼
┌─────────────────┐     ┌──────────────┐
│  FastAPI Gateway │────▶│  Celery Worker│
│  (事件接收/API)  │     │  (异步任务)   │
└────────┬────────┘     └──────┬───────┘
         │                      │
    ┌────┴────┐           ┌────┴────┐
    │ 飞书集成 │           │ AI 服务  │
    │ Bot/审批 │           │ LiteLLM │
    │ 表格/文档│           │ Router  │
    └─────────┘           └────┬────┘
                               │
                          ┌────┴────┐
                          │ GitHub  │
                          │ PR/CI/CD│
                          └─────────┘
```

## 流水线阶段

| 阶段 | 触发 | 动作 | 产出 |
|------|------|------|------|
| 需求分析 | 飞书 Bot @消息 / 多维表格新增 | AI 分析需求，生成技术方案 | 飞书卡片摘要 + 技术方案云文档 |
| 方案确认 | 用户点击卡片确认 | 方案锁定，进入开发队列 | 任务归档到指定迭代 |
| AI 编码 | 确认方案 | AI 生成代码，创建 GitHub PR | PR 链接、多维表格更新 |
| 代码审查 | PR 创建 | AI 审查代码，生成审查报告 | PR Comment + 审查报告云文档 |
| 审批 | 审查通过 | 飞书审批流人工确认 | 审批单号回填 |
| 部署 | 审批通过 → 合并 PR → GitHub Actions | CI/CD 自动部署 | 飞书通知 + 表格状态更新 |


## 技术栈

- **Python 3.11+** / FastAPI / Celery + Redis
- **飞书**: lark-oapi (Bot、审批、多维表格、Webhook)
- **AI**: LiteLLM Router 多模型路由 (Claude / GPT-4o / DeepSeek)
- **代码托管**: GitHub + PyGithub + GitHub Actions
- **部署**: Docker Compose

## 快速开始

### 1. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，填入以下配置：
# - 飞书: APP_ID, APP_SECRET, Webhook URL, 多维表格 Token, 审批 Code, 文档目录 Token
# - AI: ANTHROPIC_API_KEY, OPENAI_API_KEY, DEEPSEEK_API_KEY
# - GitHub: GITHUB_TOKEN, GITHUB_REPO, WEBHOOK_SECRET
```

### 2. 启动服务

```bash
docker-compose up -d
```

这会启动三个容器：
- `app` — FastAPI 网关 (端口 8000)
- `worker` — Celery 异步任务处理
- `redis` — 消息队列

### 3. 配置飞书

1. 在 [飞书开发者后台](https://open.feishu.cn/app) 创建自建应用
2. 开启机器人能力，配置事件订阅：
   - 请求地址: `http://<your-host>:8000/feishu/event`
   - 订阅事件: `im.message.receive_v1`
3. 配置卡片回调地址: 同上
4. 创建审批定义，记录 `approval_code` 填入 `.env`
5. 在飞书云空间创建一个文件夹用于存放技术方案/审查报告，记录 `folder_token` 填入 `.env`
6. 创建多维表格（可用初始化脚本 `scripts/init_bitable.py`）
7. 将 Bot 添加到目标群聊

### 4. 初始化飞书多维表格

```bash
python scripts/init_bitable.py --table-name "AI开发流水线"
```

如果 `.env` 里没有 `FEISHU_BITABLE_TABLE_ID`，脚本会自动创建新表并输出表 ID；如果已配置，则会直接往已有表里补字段。

### 5. 配置 GitHub

1. 在目标仓库 Settings → Webhooks 添加：
   - Payload URL: `http://<your-host>:8000/github/webhook`
   - Content type: `application/json`
   - Secret: 与 `.env` 中 `GITHUB_WEBHOOK_SECRET` 一致
   - Events: Pull requests, Workflow runs

### 6. 本地开发 (不用 Docker)

```bash
# 安装依赖
pip install -e ".[dev]"

# 启动 Redis
docker run -d -p 6379:6379 redis:7-alpine

# 启动 API
uvicorn app.main:app --reload --port 8000

# 启动 Worker (另一个终端)
celery -A app.tasks.celery_app worker --loglevel=info -Q coding,review,deploy
```

## 项目结构

```
├── config/
│   ├── settings.py          # 统一配置 (pydantic-settings)
│   └── litellm_config.py    # AI 多模型路由配置
├── app/
│   ├── main.py              # FastAPI 入口
│   ├── api/
│   │   ├── feishu_events.py # 飞书事件回调
│   │   └── webhooks.py      # GitHub Webhook
│   ├── services/
│   │   ├── pipeline.py      # 流水线状态机引擎
│   │   ├── ai_service.py    # LiteLLM 多模型调用
│   │   ├── github_service.py# GitHub PR/分支操作
│   │   ├── feishu_bot.py    # 飞书 Bot 消息 + 卡片
│   │   ├── feishu_approval.py # 飞书审批流
│   │   ├── feishu_bitable.py  # 飞书多维表格
│   │   ├── feishu_doc.py      # 飞书云文档（技术方案/审查报告）
│   │   └── feishu_notify.py   # Webhook 群通知
│   ├── tasks/
│   │   ├── celery_app.py    # Celery 配置
│   │   ├── coding_tasks.py  # AI 编码任务
│   │   ├── review_tasks.py  # AI 审查任务
│   │   └── deploy_tasks.py  # 部署通知任务
│   ├── models/
│   │   └── schemas.py       # 数据模型
│   └── prompts/
│       ├── code_gen.py      # 代码生成 Prompt
│       ├── code_review.py   # 代码审查 Prompt
│       └── requirement.py   # 需求分析 Prompt
├── docker-compose.yml
├── Dockerfile
└── pyproject.toml
```

## AI 模型路由策略

| 任务类型 | 主模型 | 备选模型 | 说明 |
|---------|--------|---------|------|
| 需求分析 | GPT-4o | Claude Sonnet | 理解自然语言需求 |
| 代码生成 | Claude Sonnet | GPT-4o | 代码质量更高 |
| 代码审查 | Claude Sonnet | — | 代码理解能力强 |
| 轻量对话 | DeepSeek Chat | — | 低成本快速响应 |

模型自动 fallback：主模型失败时自动切换备选模型，支持速率限制重试和超时重试。

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 健康检查 |
| GET | `/tasks` | 查看所有流水线任务 |
| GET | `/tasks/{task_id}` | 查看单个任务详情 |
| POST | `/feishu/event` | 飞书事件回调 |
| POST | `/github/webhook` | GitHub Webhook 回调 |

## 飞书多维表格字段

在飞书多维表格中创建以下字段（或使用 `scripts/init_bitable.py` 自动创建）：

| 字段名 | 字段类型 | 说明 | 写入时机 |
|--------|---------|------|---------|
| 任务ID | 文本 | 流水线唯一标识，如 `a3f2b1c0` | 需求接收时创建 |
| 迭代 | 单选 | 所属迭代，如 `Sprint-3` / `v1.2.0` / `Backlog` | 需求接收时创建 |
| 需求 | 多行文本 | 原始需求描述（截取前 500 字） | 需求接收时创建 |
| 技术方案 | 多行文本 | AI 生成的技术方案摘要（截取前 2000 字） | AI 分析完成后更新 |
| 技术方案文档 | 链接 | 飞书云文档链接，承载完整技术方案 | AI 分析完成后更新 |
| 状态 | 单选 | 见下方状态流转表 | 每个阶段自动更新 |
| 负责人 | 人员 | 飞书消息发送者 | 需求接收时创建 |
| PR链接 | 链接 | GitHub PR 地址 | AI 编码完成后更新 |
| 分支名 | 文本 | Git 分支名，格式 `ai/{task_id}` | AI 编码完成后更新 |
| AI审查结论 | 单选 | `通过` / `需修改` | AI 审查完成后更新 |
| 审查报告文档 | 链接 | 飞书云文档链接，承载完整审查报告 | AI 审查完成后更新 |
| 审批单号 | 文本 | 飞书审批 instance_code | 审批发起后更新 |
| 创建时间 | 日期 | 任务创建时间 | 需求接收时创建 |
| 更新时间 | 日期 | 最近一次状态变更时间 | 每次状态变更时更新 |

### 状态流转

```
分析中 → 方案待确认 → 编码中 → 编码完成 → 审查中 → 审查通过 → 审批中 → 已部署
                                                    ↘ 审查未通过       ↘ 部署失败
```

### 单选字段选项配置

**迭代**：Backlog、Sprint-1、Sprint-2、Sprint-3（按需添加）

**状态**：分析中、方案待确认、编码中、编码完成、审查中、审查通过、审查未通过、审批中、已部署、部署失败

**AI审查结论**：通过、需修改

## 飞书云文档

流水线会自动在指定文件夹下创建以下文档：

| 文档类型 | 命名规则 | 创建时机 | 内容 |
|---------|---------|---------|------|
| 技术方案 | `技术方案 - {task_id}` | AI 需求分析完成后 | 完整技术方案（模块、步骤、文件清单、风险评估） |
| 审查报告 | `代码审查报告 - {task_id} PR #{pr_number}` | AI 代码审查完成后 | 审查结论、问题列表、改进建议 |

文档链接会自动回填到多维表格对应字段，并附在飞书卡片消息中。

## 迭代管理

每个流水线任务归属一个迭代。默认为 `Backlog`，可在 Bot 消息中指定：

```
@Bot [Sprint-3] 实现用户登录功能，支持手机号+验证码
```

多维表格按迭代字段筛选/分组，即可得到迭代看板视图。

## 使用用例

### 1. 新功能开发

适用于功能明确、需要完整方案、代码审查和审批留痕的场景。

示例：

```
@Bot [Sprint-4] 新增会员积分中心页面和积分明细接口
```

### 2. Bug 修复

适用于复现路径清晰、目标明确、需要快速生成修复 PR 的场景。

示例：

```
@Bot [Sprint-4] 修复支付成功后订单状态未更新的问题，复现路径是用户重复点击提交按钮
```

### 3. 技术优化 / 重构

适用于小范围架构优化、性能优化、技术债治理等场景。

示例：

```
@Bot [Backlog] 优化订单查询接口性能，减少 N+1 查询
```

### 4. 迭代看板管理

适用于需要将需求、方案、PR、审批、部署状态统一沉淀到飞书多维表格的团队协作场景。

## SOP（标准操作流程）

### SOP 0：管理员初始化

首次部署时执行一次。

1. 复制环境变量模板：

```bash
cp .env.example .env
```

2. 填写 `.env` 中的飞书、AI、GitHub 配置
3. 初始化飞书多维表格：

```bash
python scripts/init_bitable.py --table-name "AI开发流水线"
```

4. 启动服务：

```bash
docker compose up -d
```

5. 在飞书开发者后台配置：
   - 事件订阅地址：`/feishu/event`
   - 卡片回调地址：`/feishu/event`
6. 在 GitHub 仓库配置 Webhook：`/github/webhook`

### SOP 1：提交需求

由产品、项目经理或研发负责人在飞书群中 @Bot 提交需求。

推荐格式：

```
@Bot [Sprint-3] 实现用户登录功能，支持手机号+验证码
```

系统会自动完成：
- 创建任务 ID
- 在多维表格写入任务记录
- 调用 AI 生成技术方案
- 将技术方案写入飞书云文档
- 回一张待确认卡片到飞书群

### SOP 2：确认技术方案

由技术负责人或需求提出人点击飞书卡片中的确认按钮。

确认后系统会自动：
- 将状态更新为 `编码中`
- 触发 Celery 异步编码任务
- 根据技术方案生成代码并创建 GitHub PR

### SOP 3：AI 编码

系统自动执行以下动作：
- 创建分支
- 提交 AI 生成代码
- 创建 GitHub PR
- 更新多维表格中的 `PR链接`、`分支名`
- 向飞书群发送 PR 创建通知

### SOP 4：AI 审查

PR 创建后系统自动触发 AI 审查：
- 获取 PR diff
- 生成审查结论
- 将结果写入 GitHub PR 评论
- 将完整审查报告写入飞书云文档
- 更新多维表格中的 `AI审查结论`、`审查报告文档`
- 飞书群发送审查结果卡片

### SOP 5：飞书审批

当 AI 审查通过后：
- 系统自动发起飞书审批流
- 审批人收到待审批单据
- 审批通过后进入合并/部署
- 审批驳回则流程终止或人工介入

### SOP 6：部署与结果通知

PR 合并后由 GitHub Actions 触发部署。

系统会：
- 接收 GitHub workflow webhook
- 更新多维表格状态为 `已部署` 或 `部署失败`
- 通过飞书群 Webhook 发送部署结果通知

## 团队角色建议

- **产品 / 业务**：发起需求
- **技术负责人**：确认方案、审批合并
- **AI 系统**：生成方案、编码、审查
- **运维 / 平台**：关注部署结果与回滚

## 飞书需求模板

### 新功能模板

```
@Bot [Sprint-x] 功能名称
目标：
约束：
验收标准：
```

### Bug 模板

```
@Bot [Sprint-x] 修复某问题
现象：
复现步骤：
期望结果：
```

### 优化模板

```
@Bot [Backlog] 优化某模块
当前问题：
优化目标：
限制条件：
```
