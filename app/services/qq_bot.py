"""QQ 机器人服务模块。

封装与 QQ 官方 API 的所有交互逻辑：
- Ed25519 签名验证（Webhook 回调鉴权）
- Access Token 管理（获取 + 自动刷新）
- 群聊消息发送与被动回复
"""

from __future__ import annotations

import logging
import time

import httpx
from nacl.signing import SigningKey

from app.config import settings
from app.schemas.qq import (
    GroupMessage,
    SendMessageRequest,
    SendMessageResponse,
    TokenResponse,
    ValidateData,
)

logger = logging.getLogger(__name__)


class QQBotService:
    """QQ 机器人核心服务，管理 Token 生命周期与消息收发。"""

    def __init__(self) -> None:
        self._access_token: str = ""
        self._token_expires_at: float = 0.0
        self._http = httpx.AsyncClient(base_url=settings.qq_api_base, timeout=10.0)

    def verify_signature(self, data: ValidateData) -> str:
        """使用 Ed25519 对 Webhook 验证请求进行签名。

        签名算法：以 client_secret 重复填充至 32 字节作为 seed，
        对 event_ts + plain_token 拼接后的内容进行签名。

        Args:
            data: 验证请求数据，包含 plain_token 和 event_ts

        Returns:
            签名的 hex 编码字符串

        Raises:
            ValueError: 当 client_secret 未配置时
        """
        secret = settings.client_secret
        if not secret:
            raise ValueError("QQ_BOT_CLIENT_SECRET is not configured")
        seed = (secret * 64)[:32].encode()
        signing_key = SigningKey(seed)
        message = f"{data.event_ts}{data.plain_token}".encode()
        signed = signing_key.sign(message)
        return signed.signature.hex()

    async def get_access_token(self) -> str:
        """获取 Access Token，带内存缓存。

        Token 有效期 7200 秒，在过期前 60 秒自动刷新。

        Returns:
            有效的 access_token 字符串

        Raises:
            RuntimeError: 当 QQ 平台返回错误（如 appid/secret 无效）时
        """
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
        """构造 QQ API 鉴权请求头。"""
        return {"Authorization": f"QQBot {token}", "Content-Type": "application/json"}

    async def send_group_message(
        self, group_openid: str, message: SendMessageRequest
    ) -> SendMessageResponse:
        """向指定群发送消息。

        Args:
            group_openid: 群的唯一标识
            message: 发送消息请求体

        Returns:
            发送结果，包含新消息 ID 和时间戳
        """
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
        """被动回复群聊消息（引用原消息）。

        Args:
            group_msg: 原始群消息对象
            content: 回复内容

        Returns:
            发送结果
        """
        message = SendMessageRequest(
            content=content,
            msg_type=0,
            msg_id=group_msg.id,
        )
        return await self.send_group_message(group_msg.group_openid, message)


qq_bot_service = QQBotService()
