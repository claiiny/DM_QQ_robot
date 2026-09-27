# QQ Bot Backend

QQ 机器人后端服务，基于 QQ 官方 API v2，通过 Webhook 接收群聊消息事件，并调用官方接口回复群聊消息。

## 技术栈

- Python 3.13+
- FastAPI + Uvicorn
- httpx（异步 HTTP 客户端）
- PyNaCl（Ed25519 签名验证）
- pydantic-settings（配置管理）
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
│   ├── api/
│   │   ├── api_qq.py           # QQ Webhook 回调接口
│   │   └── api_transfer.py     # AI 转发接口（预留）
│   ├── service/
│   │   └── qq_bot_service.py   # QQ Bot 服务（Token 管理、签名验证、消息收发）
│   ├── config.py               # 配置（从环境变量 / .env 读取）
│   ├── schemas.py              # 数据模型（Webhook 事件、API 请求/响应）
│   └── main.py                 # FastAPI 应用入口
├── .env                        # 环境变量（需自行创建）
├── pyproject.toml
├── README.md
├── req.md                      # 需求文档
└── func.md                     # 功能设计文档
```

## 相关文档

- [需求文档](req.md)
- [功能设计文档](func.md)
- [QQ 机器人官方文档](https://bot.q.qq.com/wiki/develop/api-v2/)
