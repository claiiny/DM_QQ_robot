"""AI 对话服务子模块。

基于 OpenAI 兼容接口（支持 OpenAI、DeepSeek 等），
提供异步对话能力。机器人收到群消息后调用本模块获取 AI 回复。
"""

from __future__ import annotations

import logging

from openai import AsyncOpenAI

from app.ai import memory
from app.ai.prompt import SYSTEM_PROMPT
from app.config import settings

logger = logging.getLogger(__name__)

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    """获取 AsyncOpenAI 客户端实例（懒初始化）。"""
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            api_key=settings.ai_api_key,
            base_url=settings.ai_base_url or None,
        )
    return _client


async def chat(user_id: str, user_message: str) -> str:
    """调用 AI 模型生成回复，带用户级对话记忆。

    从 Redis 加载该用户的历史对话上下文，连同系统提示词一起发送给 AI。
    回复生成后将本轮对话（用户消息 + AI 回复）存入记忆。

    Args:
        user_id: 用户唯一标识（member_openid），用于隔离对话上下文
        user_message: 用户发送的消息内容

    Returns:
        AI 生成的回复文本
    """
    if not settings.ai_api_key:
        logger.warning("AI_API_KEY not configured, skipping AI chat")
        return "AI 服务未配置"

    try:
        client = _get_client()
        messages = []
        if SYSTEM_PROMPT:
            messages.append({"role": "system", "content": SYSTEM_PROMPT})

        history = await memory.get_history(user_id)
        messages.extend(history)
        messages.append({"role": "user", "content": user_message})

        resp = await client.chat.completions.create(
            model=settings.ai_model,
            messages=messages,
        )
        reply = resp.choices[0].message.content or ""

        await memory.append_message(user_id, "user", user_message)
        await memory.append_message(user_id, "assistant", reply)

        return reply
    except Exception:
        logger.exception("AI chat failed")
        return "AI 服务暂时不可用"
