# QQ Bot Backend

QQ 机器人后端服务，基于 QQ 官方 API v2，通过 Webhook 接收群聊消息事件，并调用官方接口回复群聊消息。

## 技术栈

- Python 3.13+
- FastAPI + Uvicorn
- httpx（异步 HTTP 客户端）
- PyNaCl（Ed25519 签名验证）
- pydantic-settings（配置管理）
- asyncpg（PostgreSQL 异步驱动）
- openai（AI 对话服务）
- uv（包管理）

## 快速开始

```bash
# 安装依赖
uv sync

# 配置环境变量（或创建 .env 文件）
export QQ_BOT_APP_ID="your_app_id"
export QQ_BOT_CLIENT_SECRET="your_client_secret"

# 启动开发服务器
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8080
```

> QQ 平台 Webhook 仅支持 80 / 443 / 8080 / 8443 端口。

## 项目结构

```
backend/
├── app/
│   ├── main.py                 # 应用入口（初始化日志、注册路由）
│   ├── config.py               # 全局配置（pydantic-settings）
│   ├── core/                   # 基础设施层
│   │   ├── logging.py          #   日志初始化
│   │   └── database.py         #   异步连接池管理
│   ├── schemas/                # 数据模型层
│   │   └── qq.py               #   QQ API 数据结构
│   ├── ai/                     # AI 模块（可扩展多子模块）
│   │   └── service.py          #   对话服务
│   ├── services/               # 业务服务层
│   │   └── qq_bot.py           #   QQ Bot 服务（签名、Token、消息收发）
│   ├── repositories/           # 数据访问层
│   │   └── message_repo.py     #   群聊消息持久化
│   └── api/                    # 接口层
│       ├── qq/router.py        #   QQ Webhook 回调路由
│       └── transfer/router.py  #   AI 转发接口（预留）
├── docs/
│   └── design.md               # 模块设计文档
├── .env                        # 环境变量（需自行创建）
├── pyproject.toml
├── README.md
├── req.md                      # 需求文档
└── func.md                     # 功能设计文档
```

## 相关文档

- [模块设计文档](docs/design.md)
- [需求文档](req.md)
- [功能设计文档](func.md)
- [QQ 机器人官方文档](https://bot.q.qq.com/wiki/develop/api-v2/)
