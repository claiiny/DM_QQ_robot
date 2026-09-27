from __future__ import annotations

import logging
import time

import httpx
from nacl.signing import SigningKey

from app.config import settings
from app.schemas import (
    GroupMessage,
    SendMessageRequest,
    SendMessageResponse,
    TokenResponse,
    ValidateData,
)

logger = logging.getLogger(__name__)


class QQBotService:
    def __init__(self) -> None:
        self._access_token: str = ""
        self._token_expires_at: float = 0.0
        self._http = httpx.AsyncClient(base_url=settings.qq_api_base, timeout=10.0)

    def verify_signature(self, data: ValidateData) -> str:
        secret = settings.client_secret
        if not secret:
            raise ValueError("QQ_BOT_CLIENT_SECRET is not configured")
        seed = (secret * 64)[:32].encode()
        signing_key = SigningKey(seed)
        message = f"{data.event_ts}{data.plain_token}".encode()
        signed = signing_key.sign(message)
        return signed.signature.hex()

    async def get_access_token(self) -> str:
        now = time.time()
        if self._access_token and now < self._token_expires_at - 60:
            return self._access_token

        resp = await self._http.post(
            "/app/getAppAccessToken",
            json={"appId": settings.app_id, "clientSecret": settings.client_secret},
        )
        resp.raise_for_status()
        result = resp.json()

        if "access_token" not in result:
            raise RuntimeError(f"Failed to get access token: {result}")

        token_data = TokenResponse(**result)
        self._access_token = token_data.access_token
        self._token_expires_at = now + token_data.expires_in
        return self._access_token

    def _auth_headers(self, token: str) -> dict[str, str]:
        return {"Authorization": f"QQBot {token}", "Content-Type": "application/json"}

    async def send_group_message(
        self, group_openid: str, message: SendMessageRequest
    ) -> SendMessageResponse:
        token = await self.get_access_token()
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
        message = SendMessageRequest(
            content=content,
            msg_type=0,
            msg_id=group_msg.id,
        )
        return await self.send_group_message(group_msg.group_openid, message)


qq_bot_service = QQBotService()
