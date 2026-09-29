"""AI 对话记忆管理子模块。

基于 Redis 为每个用户维护独立的对话上下文（热数据），
支持最大长度限制，超出时自动裁剪最早的消息并持久化到 PostgreSQL（冷数据）。
服务重启时从 PostgreSQL 恢复上下文。
"""

from __future__ import annotations

import json
import logging

import redis.asyncio as aioredis

from app.config import settings
from app.repositories import memory_repo

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

    优先从 Redis 读取；若 Redis 无数据，则从 PostgreSQL 恢复最近的历史。

    Args:
        user_id: 用户唯一标识（member_openid）

    Returns:
        对话历史消息列表，每条包含 role 和 content
    """
    r = await _get_redis()
    data = await r.get(_memory_key(user_id))

    if data is not None:
        try:
            return json.loads(data)
        except (json.JSONDecodeError, TypeError):
            logger.warning("Failed to parse memory for user %s, resetting", user_id)
            await r.delete(_memory_key(user_id))

    history = await memory_repo.load_recent_history(user_id, settings.ai_memory_max)
    if history:
        await r.set(_memory_key(user_id), json.dumps(history, ensure_ascii=False))
        logger.info("Restored %d messages from database for user %s", len(history), user_id)

    return history


async def save_exchange(user_id: str, user_msg: str, assistant_msg: str) -> None:
    """保存一轮完整的对话（用户消息 + AI 回复）。

    追加两条消息到 Redis，超出最大长度时裁剪最早的消息并持久化到 PostgreSQL。

    Args:
        user_id: 用户唯一标识
        user_msg: 用户发送的消息
        assistant_msg: AI 生成的回复
    """
    history = await get_history(user_id)
    history.append({"role": "user", "content": user_msg})
    history.append({"role": "assistant", "content": assistant_msg})

    max_len = settings.ai_memory_max
    if len(history) > max_len:
        trimmed = history[:-max_len]
        history = history[-max_len:]
        try:
            await memory_repo.insert_memory_messages(user_id, trimmed)
        except Exception:
            logger.exception("Failed to persist trimmed memory to database")

    r = await _get_redis()
    await r.set(_memory_key(user_id), json.dumps(history, ensure_ascii=False))


async def clear_history(user_id: str) -> None:
    """清空指定用户的对话历史（Redis + PostgreSQL）。

    Args:
        user_id: 用户唯一标识
    """
    r = await _get_redis()
    await r.delete(_memory_key(user_id))

    try:
        await memory_repo.delete_user_history(user_id)
    except Exception:
        logger.exception("Failed to clear persisted memory for user %s", user_id)
