"""AI 对话记忆持久化模块。

将 Redis 工作集中淘汰的消息写入 PostgreSQL，
并在 Redis 缓存未命中时从数据库恢复最近的对话上下文。
"""

from __future__ import annotations

import logging

from app.config import settings
from app.core.database import get_pool

logger = logging.getLogger(__name__)

_TABLE = f"{settings.db_schema}.ais_memory_message"


async def insert_memory_messages(user_id: str, messages: list[dict]) -> None:
    """批量写入被淘汰的记忆消息。

    Args:
        user_id: 用户唯一标识
        messages: 消息列表，每条含 role 和 content
    """
    if not messages:
        return

    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.executemany(
            f"INSERT INTO {_TABLE} (user_id, role, content) VALUES ($1, $2, $3)",
            [(user_id, m["role"], m["content"]) for m in messages],
        )


async def delete_user_history(user_id: str) -> None:
    """删除指定用户的全部持久化记忆。

    Args:
        user_id: 用户唯一标识
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(f"DELETE FROM {_TABLE} WHERE user_id = $1", user_id)


async def load_recent_history(user_id: str, limit: int) -> list[dict]:
    """从数据库加载用户最近的对话历史。

    用于 Redis 缓存未命中时恢复上下文。

    Args:
        user_id: 用户唯一标识
        limit: 最大加载条数

    Returns:
        按时间正序排列的消息列表，每条含 role 和 content
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"SELECT role, content FROM {_TABLE} "
            f"WHERE user_id = $1 ORDER BY created_at DESC, id DESC LIMIT $2",
            user_id,
            limit,
        )
    return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]
