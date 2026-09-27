from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, Request

from app.schemas import GroupMessage, ValidateData, ValidateResponse, WebhookPayload
from app.service.qq_bot_service import qq_bot_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/qq", tags=["qq"])

OP_VALIDATE = 13
OP_EVENT = 0
OP_ACK = 12

EVENT_GROUP_AT_MESSAGE_CREATE = "GROUP_AT_MESSAGE_CREATE"


@router.post("/callback")
async def qq_webhook(request: Request, background_tasks: BackgroundTasks) -> dict:
    payload = WebhookPayload(**await request.json())

    if payload.op == OP_VALIDATE:
        return _handle_validate(payload)

    if payload.op == OP_EVENT:
        background_tasks.add_task(_handle_event, payload)
        return {"op": OP_ACK}

    return {}


def _handle_validate(payload: WebhookPayload) -> dict:
    data = ValidateData(**payload.d)
    signature = qq_bot_service.verify_signature(data)
    return ValidateResponse(plain_token=data.plain_token, signature=signature).model_dump()


async def _handle_event(payload: WebhookPayload) -> None:
    event_type = payload.t

    if event_type == EVENT_GROUP_AT_MESSAGE_CREATE:
        group_msg = GroupMessage(**payload.d)
        await _on_group_message(group_msg)
    else:
        logger.info("Unhandled event type: %s", event_type)


async def _on_group_message(group_msg: GroupMessage) -> None:
    try:
        await qq_bot_service.reply_group_message(group_msg, f"收到消息: {group_msg.content}")
    except Exception:
        logger.exception("Failed to reply to group message %s", group_msg.id)
