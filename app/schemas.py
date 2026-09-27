from __future__ import annotations

from pydantic import BaseModel, Field


class WebhookPayload(BaseModel):
    id: str = ""
    op: int = 0
    t: str = ""
    d: dict = Field(default_factory=dict)
    s: int | None = None


class ValidateData(BaseModel):
    plain_token: str
    event_ts: str


class ValidateResponse(BaseModel):
    plain_token: str
    signature: str


class User(BaseModel):
    id: str = ""
    user_openid: str = ""
    member_openid: str = ""


class MessageAttachment(BaseModel):
    content_type: str = ""
    filename: str = ""
    height: int = 0
    width: int = 0
    size: int = 0
    url: str = ""


class GroupMessage(BaseModel):
    id: str = ""
    author: User = Field(default_factory=User)
    content: str = ""
    group_openid: str = ""
    timestamp: str = ""
    message_type: int = 0
    message_scene: int = 0
    attachments: list[MessageAttachment] = Field(default_factory=list)
    mentions: list[User] = Field(default_factory=list)


class SendMessageRequest(BaseModel):
    content: str = ""
    msg_type: int = 0
    msg_id: str = ""
    event_id: str = ""
    msg_seq: int = 0


class SendMessageResponse(BaseModel):
    id: str = ""
    timestamp: str = ""


class TokenRequest(BaseModel):
    appId: str
    clientSecret: str


class TokenResponse(BaseModel):
    access_token: str
    expires_in: int
