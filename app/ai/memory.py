"""AI 对话记忆管理子模块。

基于 Redis 为每个用户维护独立的对话上下文，
支持最大长度限制，超出时自动裁剪最早的消息。
"""

from __future__ import annotations

import json
import logging

import redis.asyncio as aioredis

from app.config import settings

logger = logging.getLogger(__name__)

_pool: aioredis.Redis | None = None

KEY_PREFIX = "ai:memory:"


async def _get_redis() -> aioredis.Redis:
    """获取 Redis 客户端实例（懒初始化）。"""
    global _pool
    if _pool is None:
        _pool = aioredis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            db=settings.redis_db,
            decode_responses=True,
        )
    return _pool


def _memory_key(user_id: str) -> str:
    """构造用户记忆存储键。"""
    return f"{KEY_PREFIX}{user_id}"


async def get_history(user_id: str) -> list[dict]:
    """获取指定用户的对话历史。

    Args:
        user_id: 用户唯一标识（member_openid）

    Returns:
        对话历史消息列表，每条包含 role 和 content
    """
    r = await _get_redis()
    data = await r.get(_memory_key(user_id))
    if data is None:
        return []
    try:
        return json.loads(data)
    except (json.JSONDecodeError, TypeError):
        logger.warning("Failed to parse memory for user %s, resetting", user_id)
        await r.delete(_memory_key(user_id))
        return []


async def append_message(user_id: str, role: str, content: str) -> None:
    """向指定用户的对话历史追加一条消息。

    超出最大长度时，裁剪最早的消息（保留 system prompt 之外的消息）。

    Args:
        user_id: 用户唯一标识
        role: 消息角色（user / assistant）
        content: 消息内容
    """
    history = await get_history(user_id)
    history.append({"role": role, "content": content})

    max_len = settings.ai_memory_max
    if len(history) > max_len:
        history = history[-max_len:]

    r = await _get_redis()
    await r.set(_memory_key(user_id), json.dumps(history, ensure_ascii=False))


async def clear_history(user_id: str) -> None:
    """清空指定用户的对话历史。

    Args:
        user_id: 用户唯一标识
    """
    r = await _get_redis()
    await r.delete(_memory_key(user_id))
