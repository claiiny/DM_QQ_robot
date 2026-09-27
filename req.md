# 需求文档

## 1. 项目背景

搭建一个 QQ 机器人后端服务，基于 QQ 官方 API v2，通过 Webhook 机制接收群聊中 @机器人 的消息事件，并调用官方接口回复消息。

## 2. 核心需求

### 2.1 Webhook 回调验证

- QQ 平台在注册回调地址时会发送验证请求（`op: 13`），后端需使用 Ed25519 算法对 `plain_token` + `event_ts` 进行签名并返回
- 验证通过后，平台才会正式推送事件
- **实现要点**：
  - 签名 seed = `(client_secret * 64)[:32].encode()`
  - 签名内容 = `event_ts + plain_token`
  - 返回签名的 hex 编码

### 2.2 群聊消息接收

- 接收 `GROUP_AT_MESSAGE_CREATE` 事件（群内 @机器人 时触发）
- 解析消息内容，包括：消息 ID、发送者、消息正文、群 ID、时间戳、附件、@提及等
- 接收后需返回 ACK（`op: 12`）确认
- **实现要点**：
  - 事件推送时 `op=0`，`t="GROUP_AT_MESSAGE_CREATE"`
  - 必须立即返回 `{"op": 12}` 作为 ACK，否则平台会认为推送失败并重试
  - 业务处理（如回复消息）应异步进行，不阻塞 ACK 返回

### 2.3 群聊消息发送

- 调用 QQ 官方 API `POST /v2/groups/{group_openid}/messages` 发送群聊消息
- 支持被动回复（携带 `msg_id` 引用原消息）
- 鉴权方式：`Authorization: QQBot {ACCESS_TOKEN}`
- **实现要点**：
  - 被动回复时 `msg_id` 必填，引用原消息的 ID
  - `msg_type=0` 表示文本消息
  - 请求头需同时包含 `Authorization` 和 `Content-Type: application/json`

### 2.4 Token 管理

- 通过 `POST /app/getAppAccessToken` 获取 Access Token
- Token 有效期 7200 秒，需在过期前 60 秒内自动刷新
- Token 缓存在内存中，避免频繁请求
- **实现要点**：
  - 请求体：`{"appId": "...", "clientSecret": "..."}`
  - 响应体：`{"access_token": "...", "expires_in": 7200}`
  - 缓存策略：记录 `token_expires_at = now + expires_in`，每次获取前检查 `now < token_expires_at - 60`

## 3. 接口规范

### 3.1 Webhook 回调（接收）

| 项目     | 说明                                      |
| -------- | ----------------------------------------- |
| 协议     | HTTPS（平台要求）                         |
| 方法     | POST                                      |
| 路径     | `/qq/callback`                            |
| 端口     | 80 / 443 / 8080 / 8443                    |
| 请求体   | JSON（`WebhookPayload` 结构）             |
| 响应体   | JSON（验证响应 或 ACK）                   |

**请求体结构**：

```json
{
  "id": "event_id",
  "op": 0,
  "t": "GROUP_AT_MESSAGE_CREATE",
  "d": { /* 事件数据 */ },
  "s": 42
}
```

**响应体**：

- 验证请求（`op=13`）：`{"plain_token": "...", "signature": "..."}`
- 事件推送（`op=0`）：`{"op": 12}`

### 3.2 发送群聊消息（调用 QQ 官方 API）

| 项目     | 说明                                                    |
| -------- | ------------------------------------------------------- |
| 方法     | POST                                                    |
| URL      | `https://api.bot.qq.com/v2/groups/{group_openid}/messages` |
| 鉴权     | `Authorization: QQBot {ACCESS_TOKEN}`                   |
| 请求体   | `{ content, msg_type, msg_id, ... }`                    |

**请求体结构**：

```json
{
  "content": "回复内容",
  "msg_type": 0,
  "msg_id": "原消息ID（被动回复时必填）"
}
```

**响应体结构**：

```json
{
  "id": "新消息ID",
  "timestamp": "时间戳"
}
```

### 3.3 获取 Access Token（调用 QQ 官方 API）

| 项目     | 说明                                      |
| -------- | ----------------------------------------- |
| 方法     | POST                                      |
| URL      | `https://api.bot.qq.com/app/getAppAccessToken` |
| 请求体   | `{"appId": "...", "clientSecret": "..."}` |

**响应体结构**：

```json
{
  "access_token": "token_string",
  "expires_in": 7200
}
```

## 4. 非功能需求

- **安全性**：Ed25519 签名验证，确保回调来源为 QQ 平台
- **可靠性**：Token 自动刷新，避免过期导致接口调用失败
- **可扩展**：分层架构（API / Service），方便后续增加业务逻辑
- **异步处理**：全链路异步，支持高并发场景
- **实时性**：事件处理使用 BackgroundTasks 异步执行，确保 ACK 立即返回

## 5. 实现细节

### 5.1 消息收发完整流程

```
1. QQ 平台推送事件
   POST /qq/callback
   Body: {"op": 0, "t": "GROUP_AT_MESSAGE_CREATE", "d": {...}}

2. 后端接收并立即返回 ACK
   Response: {"op": 12}

3. 后台异步处理事件（BackgroundTasks）
   - 解析 GroupMessage
   - 调用 _on_group_message()

4. 调用 QQ API 发送回复
   - 获取 Access Token（缓存或刷新）
   - POST /v2/groups/{group_openid}/messages
   - Body: {"content": "...", "msg_type": 0, "msg_id": "原消息ID"}

5. QQ 平台发送消息到群聊
```

### 5.2 错误处理

- **签名验证失败**：返回 500 错误，记录日志
- **Token 获取失败**：抛出 RuntimeError，记录日志
- **消息发送失败**：捕获异常，记录日志，不影响 ACK 返回
- **未知事件类型**：记录日志，返回 ACK

### 5.3 配置管理

- 使用 `pydantic-settings` 从环境变量读取配置
- 环境变量前缀：`QQ_BOT_`
- 支持 `.env` 文件

## 6. 后续迭代方向

- 接入 AI 大模型，对群聊消息进行智能回复
- 支持富文本消息（Markdown、Ark 模板、Keyboard 等）
- 支持图片/文件等附件消息的收发
- 消息持久化与历史记录查询
- 接入消息队列，解耦事件接收与业务处理
- 实现重试机制，处理消息发送失败的情况
- 添加消息去重，防止平台重试导致的重复处理
