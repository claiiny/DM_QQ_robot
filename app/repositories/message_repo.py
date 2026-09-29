"""群聊消息持久化模块。

负责将 QQ 群聊 @机器人 的消息事件写入 PostgreSQL 数据库。
表结构采用 ODS 层命名规范（ods_ 前缀），嵌套字段平铺存储。
"""

from __future__ import annotations

import json

from app.config import settings
from app.core.database import get_pool


async def insert_group_at_message(data: dict) -> None:
    """将群聊 @消息事件数据写入 ods_qq_group_at_message 表。

    从原始事件 dict 中提取并平铺嵌套结构（如 author），
    复杂类型字段（message_scene、attachments 等）序列化为 JSONB 存储。
    使用 ON CONFLICT DO NOTHING 避免重复写入。

    Args:
        data: 原始事件数据（WebhookPayload.d）
    """
    pool = await get_pool()
    author = data.get("author") or {}
    async with pool.acquire() as conn:
        await conn.execute(
            f"""
            INSERT INTO {settings.db_schema}.ods_qq_group_at_message
                (message_id, author_id, author_member_openid,
                 author_username, author_bot, author_member_role, author_union_openid,
                 content, group_id, group_openid, timestamp,
                 message_type, message_scene, attachments, mentions)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15)
            ON CONFLICT (message_id) DO NOTHING
            """,
            data.get("id"),
            author.get("id"),
            author.get("member_openid"),
            author.get("username"),
            author.get("bot"),
            author.get("member_role"),
            author.get("union_openid"),
            data.get("content"),
            data.get("group_id"),
            data.get("group_openid"),
            data.get("timestamp"),
            _to_json(data.get("message_type")),
            _to_json(data.get("message_scene")),
            _to_json(data.get("attachments")),
            _to_json(data.get("mentions")),
        )


def _to_json(value) -> str | None:
    """将值序列化为 JSON 字符串，None 返回 None。"""
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False)
