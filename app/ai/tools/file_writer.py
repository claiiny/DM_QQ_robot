"""文件写入工具。

AI 可在服务器上创建文本文件（代码、配置、笔记等），
文件保存在配置的 ``ai_files_dir`` 目录下。
可选将文件发送到群聊（通过静态文件服务提供公开 URL）。
"""

from __future__ import annotations

import logging
import re
import uuid
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)

definition = {
    "name": "write_file",
    "description": "将文本内容写入文件。支持各类文本文件（代码、配置、Markdown、纯文本等）。文件保存在服务器指定目录下。可选择是否将文件发送到当前群聊。",
    "parameters": {
        "type": "object",
        "properties": {
            "filename": {
                "type": "string",
                "description": "文件名（可包含子目录路径，如 'scripts/hello.py'）",
            },
            "content": {
                "type": "string",
                "description": "要写入的文件内容",
            },
            "send": {
                "type": "boolean",
                "description": "是否将文件发送到群聊，默认为 false",
            },
        },
        "required": ["filename", "content"],
    },
}


def _ascii_filename(filename: str) -> str:
    """Generate an ASCII-safe filename for URL use."""
    name, dot, ext = filename.rpartition(".")
    stem = name if dot else filename
    ascii_stem = re.sub(r"[^\w\-.]", "_", stem.encode("ascii", "replace").decode())
    ascii_stem = ascii_stem.replace("?", "").strip("_") or "file"
    suffix = uuid.uuid4().hex[:8]
    if dot and ext:
        return f"{ascii_stem}_{suffix}.{ext}"
    return f"{ascii_stem}_{suffix}"


async def handler(filename: str, content: str, send: bool = False) -> str:
    """将内容写入指定文件，可选发送到群聊。"""
    base_dir = Path(settings.ai_files_dir)

    if send:
        url_name = _ascii_filename(filename)
        target = (base_dir / url_name).resolve()
    else:
        url_name = filename
        target = (base_dir / filename).resolve()

    if not str(target).startswith(str(base_dir.resolve())):
        return "错误：不允许写入目录外的路径"

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        logger.info("File written: %s (%d bytes)", target, len(content))
    except Exception:
        logger.exception("Failed to write file: %s", filename)
        return f"文件写入失败：{filename}"

    if send:
        if not settings.public_base_url:
            return f"文件已写入：{filename}（{len(content)} 字节），但发送失败：未配置公开访问地址"
        from app.ai.service import add_pending_file
        add_pending_file(url_name, filename)
        return f"文件已写入：{filename}（{len(content)} 字节），将发送到群聊"

    return f"文件已写入：{filename}（{len(content)} 字节）"
