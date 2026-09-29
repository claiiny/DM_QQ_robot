"""QQ Webhook 回调路由。

接收 QQ 平台的 Webhook 请求，根据 op 操作码分发处理：
- op=13：验证请求，返回 Ed25519 签名
- op=0：事件推送，异步处理后立即返回 ACK（op=12）

事件处理通过 BackgroundTasks 异步执行，避免阻塞 ACK 响应。
"""

from __future__ import annotations

import json
import logging
import re
from urllib.parse import quote

from fastapi import APIRouter, BackgroundTasks, Request

from app.repositories.message_repo import insert_group_at_message
from app.schemas.qq import GroupMessage, ValidateData, ValidateResponse, WebhookPayload
from app.ai import memory as ai_memory
from app.ai import service as ai
from app.config import settings
from app.services.qq_bot import qq_bot_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/qq", tags=["qq"])

OP_VALIDATE = 13
OP_EVENT = 0
OP_ACK = 12

EVENT_GROUP_AT_MESSAGE_CREATE = "GROUP_AT_MESSAGE_CREATE"

_FILE_SEND_RE = re.compile(r"\[SEND_FILE:([^\]]+)\]")


@router.post("/callback")
async def qq_webhook(request: Request, background_tasks: BackgroundTasks) -> dict:
    """QQ Webhook 回调入口。

    记录请求日志后，根据 op 操作码分发：
    - 验证请求 → 同步返回签名
    - 事件推送 → 放入后台任务异步处理，立即返回 ACK
    """
    body = await request.body()
    client_ip = request.client.host if request.client else "unknown"
    logger.info("%s %s body=%s", request.method, client_ip, body[:2000].decode(errors="replace"))

    payload = WebhookPayload(**json.loads(body))

    if payload.op == OP_VALIDATE:
        return _handle_validate(payload)

    if payload.op == OP_EVENT:
        background_tasks.add_task(_handle_event, payload)
        return {"op": OP_ACK}

    return {}


def _handle_validate(payload: WebhookPayload) -> dict:
    """处理 Webhook 验证请求（op=13），返回签名响应。"""
    data = ValidateData(**payload.d)
    signature = qq_bot_service.verify_signature(data)
    return ValidateResponse(plain_token=data.plain_token, signature=signature).model_dump()


async def _handle_event(payload: WebhookPayload) -> None:
    """处理事件推送（op=0），根据事件类型分发到对应处理器。"""
    event_type = payload.t

    if event_type == EVENT_GROUP_AT_MESSAGE_CREATE:
        try:
            await insert_group_at_message(payload.d)
        except Exception:
            logger.exception("Failed to insert group message %s into database", payload.d.get("id"))
        group_msg = GroupMessage(**payload.d)
        await _on_group_message(group_msg)
    else:
        logger.info("Unhandled event type: %s", event_type)


async def _on_group_message(group_msg: GroupMessage) -> None:
    """处理群聊 @机器人 消息：识别命令或调用 AI 生成回复。"""
    session_id = f"{group_msg.group_openid}:{group_msg.author.member_openid}"
    content = group_msg.content.strip()

    if content == "/clear":
        try:
            await ai_memory.clear_history(session_id)
            await qq_bot_service.reply_group_message(group_msg, "已清空对话记忆~")
        except Exception:
            logger.exception("Failed to clear memory for session %s", session_id)
        return

    try:
        ai.set_group_context(group_msg.group_openid, group_msg.id)
        reply = await ai.chat(session_id, content)

        file_matches = _FILE_SEND_RE.findall(reply)
        for filename in file_matches:
            encoded_filename = quote(filename, safe="")
            file_url = f"{settings.public_base_url}/ai-files/{encoded_filename}"
            logger.info("Sending file: %s, URL: %s", filename, file_url)
            try:
                await qq_bot_service.send_group_file(
                    group_msg.group_openid, file_url, filename
                )
                logger.info("File sent successfully: %s", filename)
            except Exception:
                logger.exception("Failed to send file: %s", filename)

        reply = _FILE_SEND_RE.sub("", reply).strip()
        if reply:
            await qq_bot_service.reply_group_message(group_msg, reply)
    except Exception:
        logger.exception("Failed to reply to group message %s", group_msg.id)
