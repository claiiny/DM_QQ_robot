# 功能设计文档

## 1. 整体架构

```
QQ 机器人平台
      │
      │  POST /qq/callback
      │  (Webhook 验证 / 事件推送)
      ▼
┌─────────────────────────────────────┐
│  API 层 (api_qq.py)                 │
│  - 接收 Webhook 请求                │
│  - 区分验证请求 (op:13) 和事件 (op:0)│
│  - 返回签名验证响应 / ACK           │
│  - 使用 BackgroundTasks 异步处理    │
└─────────────┬───────────────────────┘
              │
              ▼
┌─────────────────────────────────────┐
│  Service 层 (qq_bot_service.py)     │
│  - Ed25519 签名验证                 │
│  - Access Token 管理（获取 + 缓存） │
│  - 发送群聊消息                     │
│  - 被动回复群消息                   │
└─────────────┬───────────────────────┘
              │
              ▼
┌─────────────────────────────────────┐
│  QQ 官方 API                        │
│  - POST /app/getAppAccessToken       │
│  - POST /v2/groups/{id}/messages    │
└─────────────────────────────────────┘
```

## 2. Webhook 流程

### 2.1 验证流程

QQ 平台在配置回调地址时发送验证请求：

```json
// 请求
{
  "id": "event_id",
  "op": 13,
  "d": {
    "plain_token": "随机字符串",
    "event_ts": "时间戳"
  }
}

// 响应
{
  "plain_token": "原样返回",
  "signature": "Ed25519签名(hex)"
}
```

**签名算法实现**：

```python
def verify_signature(self, data: ValidateData) -> str:
    # 1. 生成 seed：将 client_secret 重复填充至 32 字节
    seed = (settings.client_secret * 64)[:32].encode()

    # 2. 创建 Ed25519 SigningKey
    signing_key = SigningKey(seed)

    # 3. 对 event_ts + plain_token 签名
    message = f"{data.event_ts}{data.plain_token}".encode()
    signed = signing_key.sign(message)

    # 4. 返回签名的 hex 编码
    return signed.signature.hex()
```

**代码位置**：`app/service/qq_bot_service.py:24-29`

### 2.2 事件推送

验证通过后，平台推送群聊消息事件：

```json
// 请求
{
  "id": "event_id",
  "op": 0,
  "t": "GROUP_AT_MESSAGE_CREATE",
  "d": {
    "id": "message_id",
    "author": {
      "id": "user_id",
      "user_openid": "openid",
      "member_openid": "member_openid"
    },
    "content": "消息内容",
    "group_openid": "group_openid",
    "timestamp": "1234567890",
    "message_type": 0,
    "message_scene": 0
  },
  "s": 42
}

// 响应 (ACK)
{
  "op": 12
}
```

**事件处理实现**：

```python
@router.post("/callback")
async def qq_webhook(request: Request, background_tasks: BackgroundTasks) -> dict:
    payload = WebhookPayload(**await request.json())

    # 验证请求
    if payload.op == OP_VALIDATE:
        return _handle_validate(payload)

    # 事件推送：立即返回 ACK，后台异步处理
    if payload.op == OP_EVENT:
        background_tasks.add_task(_handle_event, payload)
        return {"op": OP_ACK}

    return {}
```

**代码位置**：`app/api/api_qq.py:18-28`

**关键设计**：
- 使用 FastAPI 的 `BackgroundTasks` 机制
- ACK 立即返回，不等待业务处理完成
- 避免平台因超时重试导致的重复处理

### 2.3 发送群聊消息

```json
// POST /v2/groups/{group_openid}/messages
// Authorization: QQBot {ACCESS_TOKEN}

// 请求体
{
  "content": "回复内容",
  "msg_type": 0,
  "msg_id": "原消息ID（被动回复时必填）"
}

// 响应
{
  "id": "新消息ID",
  "timestamp": "时间戳"
}
```

**消息发送实现**：

```python
async def send_group_message(
    self, group_openid: str, message: SendMessageRequest
) -> SendMessageResponse:
    # 1. 获取 Access Token（自动处理缓存和刷新）
    token = await self.get_access_token()

    # 2. 调用 QQ API
    resp = await self._http.post(
        f"/v2/groups/{group_openid}/messages",
        headers=self._auth_headers(token),
        json=message.model_dump(exclude_none=True),
    )
    resp.raise_for_status()
    return SendMessageResponse(**resp.json())

async def reply_group_message(
    self, group_msg: GroupMessage, content: str
) -> SendMessageResponse:
    # 构造被动回复消息（携带 msg_id）
    message = SendMessageRequest(
        content=content,
        msg_type=0,
        msg_id=group_msg.id,  # 引用原消息
    )
    return await self.send_group_message(group_msg.group_openid, message)
```

**代码位置**：`app/service/qq_bot_service.py:49-69`

## 3. 数据模型

### 3.1 Webhook 载荷

```python
class WebhookPayload(BaseModel):
    id: str          # 事件 ID
    op: int          # 操作码 (0=事件, 12=ACK, 13=验证)
    t: str           # 事件类型
    d: dict          # 事件数据
    s: int | None    # 序列号
```

**代码位置**：`app/schemas.py:7-12`

### 3.2 群聊消息

```python
class GroupMessage(BaseModel):
    id: str                  # 消息 ID
    author: User             # 发送者
    content: str             # 消息正文
    group_openid: str        # 群唯一标识
    timestamp: str           # 时间戳
    message_type: int        # 消息类型
    message_scene: int       # 消息场景
    attachments: list        # 附件列表
    mentions: list           # @提及的用户

class User(BaseModel):
    id: str                  # 用户 ID
    user_openid: str         # 用户 openid
    member_openid: str       # 群成员 openid
```

**代码位置**：`app/schemas.py:22-34, 14-17`

### 3.3 发送消息请求

```python
class SendMessageRequest(BaseModel):
    content: str     # 消息内容
    msg_type: int    # 消息类型 (0=文本, 2=Markdown, 3=Ark, 4=Keyboard)
    msg_id: str      # 引用消息 ID（被动回复）
    event_id: str    # 事件 ID
    msg_seq: int     # 消息序列号
```

**代码位置**：`app/schemas.py:45-51`

### 3.4 Token 相关

```python
class TokenRequest(BaseModel):
    appId: str
    clientSecret: str

class TokenResponse(BaseModel):
    access_token: str
    expires_in: int    # 有效期（秒），固定 7200
```

**代码位置**：`app/schemas.py:59-65`

## 4. Token 管理

**实现逻辑**：

```python
async def get_access_token(self) -> str:
    now = time.time()

    # 1. 检查缓存是否有效（过期前 60 秒刷新）
    if self._access_token and now < self._token_expires_at - 60:
        return self._access_token

    # 2. 请求新 Token
    resp = await self._http.post(
        "/app/getAppAccessToken",
        json={"appId": settings.app_id, "clientSecret": settings.client_secret},
    )
    resp.raise_for_status()
    result = resp.json()

    # 3. 校验响应
    if "access_token" not in result:
        raise RuntimeError(f"Failed to get access token: {result}")

    # 4. 缓存 Token 和过期时间
    token_data = TokenResponse(**result)
    self._access_token = token_data.access_token
    self._token_expires_at = now + token_data.expires_in

    return self._access_token
```

**代码位置**：`app/service/qq_bot_service.py:31-48`

**缓存策略**：
- 内存缓存：`_access_token` 和 `_token_expires_at`
- 提前刷新：在过期前 60 秒内主动刷新，避免临界点失败
- 首次调用：启动时不获取 Token，首次发送消息时懒加载

## 5. 消息处理流程

### 5.1 完整时序图

```
QQ平台              后端API层              后端Service层           QQ官方API
  │                     │                        │                      │
  │──POST /callback────>│                        │                      │
  │   {op:0, t:GROUP..} │                        │                      │
  │                     │                        │                      │
  │                     │──add_task(_handle)─────>│                      │
  │<──{op:12} ACK──────│                        │                      │
  │                     │                        │                      │
  │                     │                        │──get_access_token()──>│
  │                     │                        │<──{access_token}─────│
  │                     │                        │                      │
  │                     │                        │──POST /v2/groups/...─>│
  │                     │                        │   {content, msg_id}  │
  │<──发送消息到群──────│                        │<──{id, timestamp}────│
  │                     │                        │                      │
```

### 5.2 事件分发

```python
async def _handle_event(payload: WebhookPayload) -> None:
    event_type = payload.t

    if event_type == EVENT_GROUP_AT_MESSAGE_CREATE:
        group_msg = GroupMessage(**payload.d)
        await _on_group_message(group_msg)
    else:
        logger.info("Unhandled event type: %s", event_type)
```

**代码位置**：`app/api/api_qq.py:35-42`

### 5.3 群消息处理

```python
async def _on_group_message(group_msg: GroupMessage) -> None:
    try:
        # 被动回复：引用原消息
        await qq_bot_service.reply_group_message(
            group_msg,
            f"收到消息: {group_msg.content}"
        )
    except Exception:
        logger.exception("Failed to reply to group message %s", group_msg.id)
```

**代码位置**：`app/api/api_qq.py:45-50`

**错误处理**：
- 捕获所有异常，避免后台任务崩溃
- 记录完整错误堆栈，便于排查
- 不影响其他消息的处理

## 6. 目录职责

| 文件                          | 职责                                           | 关键函数/类                           |
| ----------------------------- | ---------------------------------------------- | ------------------------------------- |
| `app/main.py`                 | 应用入口，注册路由                             | `app`                                 |
| `app/config.py`               | 配置管理（AppID、Secret、API 基础 URL）        | `Settings`, `settings`                |
| `app/schemas.py`              | 数据模型定义                                   | `WebhookPayload`, `GroupMessage` 等   |
| `app/api/api_qq.py`           | Webhook 接口（验证 + 事件接收 + ACK）          | `qq_webhook`, `_handle_event`         |
| `app/service/qq_bot_service.py` | 业务逻辑（签名验证、Token 管理、消息收发）   | `QQBotService`, `qq_bot_service`      |

## 7. 配置项

| 环境变量               | 说明              | 必填 | 默认值                    |
| ---------------------- | ----------------- | ---- | ------------------------- |
| `QQ_BOT_APP_ID`        | 机器人 AppID      | 是   | `""`                      |
| `QQ_BOT_CLIENT_SECRET` | 机器人 ClientSecret | 是   | `""`                      |
| `QQ_BOT_QQ_API_BASE`   | QQ API 基础 URL   | 否   | `https://api.bot.qq.com`  |

**配置加载**：

```python
class Settings(BaseSettings):
    app_id: str = ""
    client_secret: str = ""
    qq_api_base: str = "https://api.bot.qq.com"

    model_config = {"env_prefix": "QQ_BOT_", "env_file": ".env"}
```

**代码位置**：`app/config.py:4-10`

## 8. 依赖说明

| 依赖              | 版本     | 用途                          |
| ----------------- | -------- | ----------------------------- |
| `fastapi`         | >=0.141  | Web 框架                      |
| `uvicorn`         | >=0.54   | ASGI 服务器                   |
| `httpx`           | >=0.28   | 异步 HTTP 客户端（调用 QQ API）|
| `pydantic-settings`| >=2.0   | 配置管理                      |
| `pynacl`          | >=1.5    | Ed25519 签名验证              |

## 9. 后续扩展点

- **AI 回复**：在 `_on_group_message` 中接入大模型 API，根据消息内容生成智能回复
- **富文本消息**：支持 `msg_type=2`（Markdown）、`msg_type=3`（Ark）、`msg_type=4`（Keyboard）
- **附件处理**：下载并处理图片、文件等附件
- **事件分发**：引入事件分发机制，支持更多事件类型（群成员变更、消息撤回等）
- **持久化**：接入数据库，存储消息记录和用户状态
- **消息队列**：引入 Redis / RabbitMQ，替代 BackgroundTasks，实现更可靠的异步处理
- **重试机制**：对消息发送失败的情况实现指数退避重试
- **消息去重**：基于消息 ID 实现幂等处理，防止平台重试导致的重复回复
