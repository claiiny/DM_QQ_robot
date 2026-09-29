"""数据库连接池管理模块。

基于 asyncpg 提供异步连接池的创建与获取。
具体的 SQL 操作由各 repository 模块实现，本模块仅管理连接池生命周期。
"""

from __future__ import annotations

import asyncpg

from app.config import settings

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    """获取全局异步连接池（懒初始化，首次调用时创建）。"""
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            host=settings.db_host,
            port=settings.db_port,
            database=settings.db_name,
            user=settings.db_user,
            password=settings.db_password,
            min_size=1,
            max_size=5,
        )
    return _pool
