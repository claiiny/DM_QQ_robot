"""图片生成工具。

调用 DashScope 兼容的 OpenAI images API 生成图片，
保存到本地并通过 pending_files 机制发送到群聊。
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path

import httpx
from openai import AsyncOpenAI

from app.config import settings

logger = logging.getLogger(__name__)

definition = {
    "name": "generate_image",
    "description": "根据文字描述生成图片。当用户要求画图、生成图片、画一个XX时使用此工具。生成的图片会自动发送到群聊。",
    "parameters": {
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": "图片描述（英文效果更好，也支持中文）",
            },
            "size": {
                "type": "string",
                "description": "图片尺寸，可选：1024x1024, 1024x1792, 1792x1024",
                "default": "1024x1024",
            },
        },
        "required": ["prompt"],
    },
}

_image_client: AsyncOpenAI | None = None


def _get_image_client() -> AsyncOpenAI:
    global _image_client
    if _image_client is None:
        _image_client = AsyncOpenAI(
            api_key=settings.ai_image_api_key or settings.ai_api_key,
            base_url=settings.ai_image_base_url or settings.ai_base_url or None,
        )
    return _image_client


async def handler(prompt: str, size: str = "1024x1024") -> str:
    """根据描述生成图片并保存到本地，自动发送到群聊。"""
    if not settings.ai_image_model:
        return "图片生成服务未配置"

    try:
        client = _get_image_client()
        resp = await client.images.generate(
            model=settings.ai_image_model,
            prompt=prompt,
            size=size,
            n=1,
        )

        image_url = resp.data[0].url
        if not image_url:
            return "图片生成失败：未返回图片地址"

        filename = f"image_{uuid.uuid4().hex[:8]}.png"
        target = Path(settings.ai_files_dir) / filename
        target.parent.mkdir(parents=True, exist_ok=True)

        async with httpx.AsyncClient(timeout=30.0) as http:
            img_resp = await http.get(image_url)
            img_resp.raise_for_status()
            target.write_bytes(img_resp.content)

        logger.info("Image generated: %s (%d bytes)", filename, len(img_resp.content))

        from app.ai.service import add_pending_file
        add_pending_file(filename, filename)

        return f"图片已生成并发送：{filename}（{len(img_resp.content)} 字节）"

    except Exception:
        logger.exception("Image generation failed")
        return "图片生成失败，请稍后重试"
