"""AI 工具包。

所有 Function Calling 工具以子模块形式组织在此包下。
每个工具模块需导出：
- ``definition``: OpenAI function 定义字典
- ``handler``: 异步处理函数

新增工具时，在包下创建子模块并实现上述两个导出，
然后在 ``__init__.py`` 的 ``_TOOL_MODULES`` 中注册即可。
"""

from __future__ import annotations

from typing import Any, Callable

from app.ai.tools import file_writer, web_search

_TOOL_MODULES = [web_search, file_writer]

TOOLS: list[dict[str, Any]] = [
    {"type": "function", "function": mod.definition}
    for mod in _TOOL_MODULES
]

HANDLERS: dict[str, Callable] = {
    mod.definition["name"]: mod.handler
    for mod in _TOOL_MODULES
}
