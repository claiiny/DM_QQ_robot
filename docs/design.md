# 模块设计文档

本文档描述项目的模块划分、职责边界与依赖关系。代码变更时同步更新。

## 整体架构

采用分层 + 按功能域分包的结构，自上而下依赖，禁止反向引用。

```
app/
├── main.py                 # 应用入口：初始化日志、注册路由
├── config.py               # 全局配置（pydantic-settings）
├── core/                   # 基础设施层：日志、数据库等通用能力
│   ├── logging.py          #   日志初始化（RotatingFileHandler）
│   └── database.py         #   异步连接池管理（asyncpg）
├── schemas/                # 数据模型层：Pydantic 模型定义
│   └── qq.py               #   QQ API 相关数据结构
├── ai/                     # AI 模块：智能对话能力（可扩展多子模块）
│   ├── service.py          #   对话服务（OpenAI 兼容接口）
│   ├── prompt.py           #   系统提示词
│   ├── memory.py           #   对话记忆（Redis 热缓存 + PostgreSQL 持久化）
│   └── tools/              #   Function Calling 工具包
│       ├── __init__.py     #     工具注册：收集 TOOLS / HANDLERS
│       ├── web_search.py   #     联网搜索（博查 Web Search API）
│       └── file_writer.py  #     文件写入（文本文件）
├── services/               # 业务服务层：封装外部交互与核心逻辑
│   └── qq_bot.py           #   QQ 机器人服务（签名、Token、消息收发）
├── repositories/           # 数据访问层：SQL 操作封装
│   ├── message_repo.py     #   群聊消息持久化
│   └── memory_repo.py      #   AI 对话记忆持久化
└── api/                    # 接口层：HTTP 路由定义
    ├── qq/
    │   └── router.py       #   QQ Webhook 回调路由
    └── transfer/
        └── router.py       #   AI 转发接口（预留）

migrations/                 # 数据库 DDL 脚本（按序号递增）
```

## 模块说明

### main.py — 应用入口

- 调用 `core.logging.setup_logging()` 初始化日志
- 创建 FastAPI 实例并注册各业务路由
- 挂载 `ai_files_dir` 为静态文件服务（`/ai-files/`），供 QQ 服务器访问 AI 生成的文件
- 不包含任何业务逻辑

### config.py — 全局配置

- 基于 `pydantic-settings`，从环境变量（前缀 `QQ_BOT_`）和 `.env` 文件读取
- 集中管理 QQ Bot、数据库、AI、博查搜索、Redis、文件写入目录、公开访问地址等配置项
- 所有模块通过 `from app.config import settings` 获取配置

### core/ — 基础设施层

提供与业务无关的通用能力，供上层模块复用。

| 模块 | 职责 |
|------|------|
| `logging.py` | 日志初始化，RotatingFileHandler 轮转（10MB × 5 备份） |
| `database.py` | asyncpg 连接池懒初始化与获取，不包含 SQL 操作 |

### schemas/ — 数据模型层

定义所有 Pydantic 模型，按功能域分文件。

| 模块 | 内容 |
|------|------|
| `qq.py` | WebhookPayload、ValidateData/Response、User、GroupMessage、SendMessageRequest/Response、MediaRequest、UploadFileRequest/Response、TokenResponse |

### ai/ — AI 模块

独立的一级功能模块，封装所有 AI 相关能力，后续可扩展多个子模块。

| 子模块 | 职责 |
|--------|------|
| `service.py` | 对话服务：调用 OpenAI 兼容接口生成回复（`chat()`），集成记忆上下文与 Function Calling 工具调用 |
| `prompt.py` | 系统提示词管理：定义 AI 人设与行为约束（`SYSTEM_PROMPT`） |
| `memory.py` | 对话记忆管理：Redis 热缓存 + PostgreSQL 持久化的混合存储 |
| `tools/` | Function Calling 工具包：所有工具以子模块形式注册，自动收集 `TOOLS` 和 `HANDLERS` |

**记忆持久化机制：**
- Redis 保存每个用户最近的对话上下文（默认最多 `ai_memory_max` 条消息）
- 超出最大长度时，最早的消息被裁剪并批量写入 PostgreSQL（`ais_memory_message` 表）
- Redis 缓存未命中时（如服务重启），自动从 PostgreSQL 加载最近的历史恢复
- 每个用户通过 `group_openid:member_openid` 组合键隔离（群+用户维度）

**工具包机制（Function Calling）：**
- 所有工具以子模块形式组织在 `ai/tools/` 包下
- 每个工具模块导出 `definition`（OpenAI function 定义字典）和 `handler`（异步处理函数）
- `tools/__init__.py` 自动收集所有已注册模块，生成 `TOOLS` 列表和 `HANDLERS` 字典
- 对话循环最多执行 3 轮工具调用，防止无限循环
- 新增工具只需：① 在 `ai/tools/` 下创建子模块，导出 `definition` 和 `handler` ② 在 `tools/__init__.py` 的 `_TOOL_MODULES` 中注册

**群聊上下文传递：**
- `service.py` 通过 `contextvars` 传递 `group_openid` 和 `msg_id`，工具可通过 `get_group_context()` 获取
- 路由层在调用 `chat()` 前通过 `set_group_context()` 设置上下文

**文件写入与发送：**
- `write_file` 工具支持 `send` 参数，AI 自主决定是否将文件发送到群聊
- 文件写入后通过 `/ai-files/` 静态文件服务提供公开 URL
- 工具返回 `[SEND_FILE:filename]` 标记，路由层检测后调用 QQ 富媒体 API 发送文件，并从文本回复中剥离标记

可扩展方向：多模型路由、RAG 检索增强、向量存储等。

### services/ — 业务服务层

封装与外部系统的交互逻辑，供 API 层调用。

| 模块 | 职责 | 关键方法 |
|------|------|----------|
| `qq_bot.py` | QQ 官方 API 交互 | `verify_signature()` — Ed25519 签名验证 |
| | | `get_access_token()` — Token 获取与缓存（过期前 60s 刷新） |
| | | `send_group_message()` — 向群发送消息 |
| | | `reply_group_message()` — 被动回复群消息 |
| | | `upload_group_file()` — 上传富媒体文件（图片/视频/语音/文件） |
| | | `send_group_image()` — 发送群图片消息（msg_type=7） |
| | | `send_group_file()` — 发送群文件（自动识别文件类型） |

### repositories/ — 数据访问层

封装 SQL 操作，与 `core/database.py` 配合使用。

| 模块 | 职责 |
|------|------|
| `message_repo.py` | 群聊 @消息写入 `ods_qq_group_at_message` 表，嵌套字段平铺，复杂字段 JSONB 存储 |
| `memory_repo.py` | AI 对话记忆写入 `ais_memory_message` 表，支持批量插入、按用户加载最近历史、清除用户记忆 |

### api/ — 接口层

按功能域分子包，每个子包包含独立的 `router.py`。

| 模块 | 路由 | 职责 |
|------|------|------|
| `qq/router.py` | `POST /qq/callback` | 接收 QQ Webhook，分发验证/事件处理；支持 `/clear` 命令清空用户记忆；检测 AI 回复中的文件发送标记并发送文件 |
| `transfer/router.py` | `POST /ai/transfer` | AI 转发接口（预留） |

## 依赖关系

```
api/ ──→ services/ ──→ schemas/
  │          │            └──→ config.py
  │          └──→ config.py
  │
  ├──→ ai/ ──→ repositories/ ──→ core/database.py ──→ config.py
  │     │
  │     └──→ config.py
  │
  └──→ repositories/ ──→ core/database.py ──→ config.py

main.py ──→ core/logging.py
         ──→ api/
```

规则：
- 上层可依赖下层，下层不可反向依赖上层
- `schemas/` 和 `config.py` 为公共基础，各层均可引用
- `ai/` 为独立一级模块，与 `services/` 平级，互不依赖；通过 `repositories/` 实现记忆持久化

## 扩展指南

新增功能时：
1. 在 `schemas/` 下新增或扩展数据模型文件
2. 在 `services/` 下新增业务服务模块
3. 如需数据库操作，在 `repositories/` 下新增数据访问模块
4. AI 相关能力在 `ai/` 下新增子模块（如 `rag.py`）
5. 新增 Function Calling 工具在 `ai/tools/` 下创建子模块，导出 `definition` 和 `handler`，并在 `tools/__init__.py` 注册
6. 在 `api/` 下新增子包和路由，最后在 `main.py` 中注册
