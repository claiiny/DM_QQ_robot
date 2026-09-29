"""AI 转发路由。

提供 AI 能力的外部调用接口（预留扩展）。
"""

from fastapi import APIRouter

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/transfer")
def link_ai() -> str:
    """AI 转发接口（预留）。"""
    return "OK"
