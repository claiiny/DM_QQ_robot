"""AI 对话服务子模块。

基于 OpenAI 兼容接口（支持 OpenAI、DeepSeek 等），
提供异步对话能力。机器人收到群消息后调用本模块获取 AI 回复。
支持 Function Calling，AI 可自主调用联网搜索等工具。
"""

from __future__ import annotations

import json
import logging
from contextvars import ContextVar

from openai import AsyncOpenAI

from app.ai import memory
from app.ai.prompt import SYSTEM_PROMPT
from app.ai.tools import HANDLERS, TOOLS
from app.config import settings

logger = logging.getLogger(__name__)

_client: AsyncOpenAI | None = None

_group_openid_var: ContextVar[str] = ContextVar("group_openid", default="")
_msg_id_var: ContextVar[str] = ContextVar("msg_id", default="")
_pending_files_var: ContextVar[list[str]] = ContextVar("pending_files", default=[])


def set_group_context(group_openid: str, msg_id: str) -> None:
    """设置当前协程的群聊上下文，供工具（如文件发送）使用。"""
    _group_openid_var.set(group_openid)
    _msg_id_var.set(msg_id)
    _pending_files_var.set([])


def get_group_context() -> tuple[str, str]:
    """获取当前协程的群聊上下文。"""
    return _group_openid_var.get(), _msg_id_var.get()


def add_pending_file(filename: str) -> None:
    """记录一个待发送的文件名。"""
    _pending_files_var.get().append(filename)


def get_pending_files() -> list[str]:
    """获取所有待发送的文件名。"""
    return _pending_files_var.get()


def _get_client() -> AsyncOpenAI:
    """获取 AsyncOpenAI 客户端实例（懒初始化）。"""
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            api_key=settings.ai_api_key,
            base_url=settings.ai_base_url or None,
        )
    return _client


async def chat(user_id: str, user_message: str) -> str:
    """调用 AI 模型生成回复，带用户级对话记忆和工具调用。

    AI 可自主决定是否调用工具（如联网搜索），调用结果会注入上下文继续生成。
    回复生成后将本轮对话（用户消息 + AI 回复）存入记忆。

    Args:
        user_id: 用户唯一标识（member_openid），用于隔离对话上下文
        user_message: 用户发送的消息内容

    Returns:
        AI 生成的回复文本
    """
    if not settings.ai_api_key:
        logger.warning("AI_API_KEY not configured, skipping AI chat")
        return "AI 服务未配置"

    try:
        client = _get_client()
        reply = await _chat_with_tools(client, user_id, user_message)
        await memory.save_exchange(user_id, user_message, reply)
        return reply
    except Exception:
        logger.exception("AI chat failed")
        return "AI 服务暂时不可用"


async def _chat_with_tools(
    client: AsyncOpenAI,
    user_id: str,
    user_message: str,
) -> str:
    """带工具调用的对话循环，支持多轮工具执行。"""
    messages: list[dict] = []
    if SYSTEM_PROMPT:
        messages.append({"role": "system", "content": SYSTEM_PROMPT})

    history = await memory.get_history(user_id)
    messages.extend(history)
    messages.append({"role": "user", "content": user_message})

    max_tool_rounds = 3
    for _ in range(max_tool_rounds):
        resp = await client.chat.completions.create(
            model=settings.ai_model,
            messages=messages,
            tools=TOOLS,
        )

        choice = resp.choices[0]
        assistant_msg = choice.message

        if not assistant_msg.tool_calls:
            return assistant_msg.content or ""

        messages.append(assistant_msg.model_dump())

        for tool_call in assistant_msg.tool_calls:
            func_name = tool_call.function.name
            func_args = json.loads(tool_call.function.arguments)

            logger.info("AI calling tool: %s(%s)", func_name, func_args)

            handler = HANDLERS.get(func_name)
            if handler:
                result = await handler(**func_args)
            else:
                result = f"未知工具: {func_name}"

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result,
                }
            )

    resp = await client.chat.completions.create(
        model=settings.ai_model,
        messages=messages,
    )
    return resp.choices[0].message.content or ""
