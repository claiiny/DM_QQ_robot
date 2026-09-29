"""AI 联网搜索子模块。

基于博查（Bocha）Web Search API，为 AI 对话提供实时联网搜索能力。
返回格式化的搜索结果摘要，可直接注入 AI 上下文。
"""

from __future__ import annotations

import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

API_URL = "https://api.bochaai.com/v1/web-search"


MAX_RESULTS = 10


async def search(query: str, count: int = MAX_RESULTS) -> str:
    """调用博查 API 进行联网搜索。

    Args:
        query: 搜索关键词
        count: 返回结果数量（默认 10，最多 10）

    Returns:
        格式化的搜索结果文本，包含标题、摘要和链接；
        搜索失败或无结果时返回提示信息。
    """
    if not settings.bocha_api_key:
        logger.warning("BOCHA_API_KEY not configured, skipping web search")
        return "联网搜索服务未配置"

    count = min(count, MAX_RESULTS)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                API_URL,
                headers={"Authorization": f"Bearer {settings.bocha_api_key}"},
                json={
                    "query": query,
                    "count": count,
                    "summary": True,
                    "freshness": "noLimit",
                },
            )
            resp.raise_for_status()
            data = resp.json()

        return _format_results(data)
    except Exception:
        logger.exception("Bocha web search failed")
        return "联网搜索暂不可用"


def _format_results(data: dict) -> str:
    """将博查 API 响应格式化为可读文本。"""
    result_data = data.get("data", {})

    parts: list[str] = []

    summary = result_data.get("summary")
    if summary:
        parts.append(f"摘要：{summary}")

    web_pages = result_data.get("webPages", {}).get("value", [])[:MAX_RESULTS]
    if web_pages:
        parts.append("\n搜索结果：")
        for i, page in enumerate(web_pages, 1):
            name = page.get("name", "")
            snippet = page.get("snippet", "")
            url = page.get("url", "")
            page_summary = page.get("summary", "")

            entry = f"{i}. {name}\n"
            if page_summary:
                entry += f"   {page_summary}\n"
            elif snippet:
                entry += f"   {snippet}\n"
            entry += f"   链接：{url}"
            parts.append(entry)
    elif not parts:
        return "未找到相关搜索结果"

    return "\n\n".join(parts)
