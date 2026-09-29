"""QQ 官方 API v2 数据模型。

定义 Webhook 回调、群聊消息、Token 管理等与 QQ 平台交互的数据结构。
字段定义参考：https://bot.q.qq.com/wiki/develop/api-v2/autogen/event/group_at_message_create.html
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class WebhookPayload(BaseModel):
    """QQ Webhook 回调请求体。

    Attributes:
        id: 事件唯一标识
        op: 操作码（0=事件推送, 12=ACK, 13=验证请求）
        t: 事件类型名称（如 GROUP_AT_MESSAGE_CREATE）
        d: 事件数据（具体结构因事件类型而异）
        s: 序列号
    """

    id: str = ""
    op: int = 0
    t: str = ""
    d: dict = Field(default_factory=dict)
    s: int | None = None


class ValidateData(BaseModel):
    """Webhook 验证请求中的数据字段（op=13 时）。"""

    plain_token: str
    event_ts: str


class ValidateResponse(BaseModel):
    """Webhook 验证响应体，返回签名后的 plain_token。"""

    plain_token: str
    signature: str


class User(BaseModel):
    """消息发送者信息。

    Attributes:
        id: 用户唯一标识
        username: 用户昵称
        bot: 是否为机器人
        member_openid: 用户在群内的唯一标识
        member_role: 用户在群内的角色（owner/admin/member 等）
        union_openid: 用户跨应用的统一标识
    """

    id: str = ""
    username: str = ""
    bot: bool = False
    member_openid: str = ""
    member_role: str = ""
    union_openid: str = ""


class MessageAttachment(BaseModel):
    """消息附件信息（图片、文件等）。"""

    content_type: str = ""
    filename: str = ""
    height: int = 0
    width: int = 0
    size: int = 0
    url: str = ""


class GroupMessage(BaseModel):
    """群聊 @机器人 消息事件数据。

    Attributes:
        id: 消息唯一 ID
        author: 发送者信息
        content: 消息正文
        group_id: 群 ID
        group_openid: 群唯一标识（用于 API 调用）
        timestamp: 消息时间戳
        message_type: 消息类型（可能为 int 或 dict）
        message_scene: 消息场景（可能为 int 或 dict）
        attachments: 附件列表
        mentions: @提及的用户列表
    """

    id: str = ""
    author: User = Field(default_factory=User)
    content: str = ""
    group_id: str = ""
    group_openid: str = ""
    timestamp: str = ""
    message_type: Any = None
    message_scene: Any = None
    attachments: list[MessageAttachment] = Field(default_factory=list)
    mentions: list[User] = Field(default_factory=list)


class SendMessageRequest(BaseModel):
    """发送群聊消息的请求体。"""

    content: str = ""
    msg_type: int = 0
    msg_id: str = ""
    event_id: str = ""
    msg_seq: int = 0
    media: MediaRequest | None = None


class MediaRequest(BaseModel):
    """富媒体消息的媒体信息。"""

    file_info: str


class SendMessageResponse(BaseModel):
    """发送群聊消息的响应体。"""

    id: str = ""
    timestamp: str = ""


class UploadFileRequest(BaseModel):
    """群聊富媒体上传请求体。

    Attributes:
        file_type: 文件类型（1=图片, 2=视频, 3=语音, 4=文件）
        url: 文件 URL（服务端从该 URL 拉取文件）
        srv_send_msg: 是否上传后直接发送（false=仅上传获取 file_info）
    """

    file_type: int
    url: str
    srv_send_msg: bool = False


class UploadFileResponse(BaseModel):
    """群聊富媒体上传响应体。"""

    file_info: str = ""


class TokenResponse(BaseModel):
    """Access Token 接口响应体。"""

    access_token: str
    expires_in: int
