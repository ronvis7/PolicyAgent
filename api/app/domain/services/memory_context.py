"""长期记忆上下文渲染（Agent 跨会话记忆第 2 层的"召回"半边）。

把当前租户的长期记忆条目渲染成一段系统提示词上下文块，在会话启动时注入
Planner / ReAct 两个 Agent 的首条 system 消息（与 #59 的企业档案注入同链路）。
这样 Agent 在新会话里也"记得"用户历次会话中陈述过的事实与偏好。

纯函数、无副作用，便于单测。无记忆条目时返回空串(不注入任何块)。
"""

from typing import List

from app.domain.models.agent_memory import AgentMemory


def render_memory_context(memories: List[AgentMemory]) -> str:
    """把长期记忆条目渲染为系统提示词上下文块。

    返回值以 `\\n\\n` 开头便于拼接到系统提示词尾部；无条目时返回空串。
    仅渲染有内容的条目，按传入顺序(调用方已按最新在前排序)逐条列出。
    """
    lines: List[str] = [m.content.strip() for m in memories if m.content and m.content.strip()]
    if not lines:
        return ""

    body = "\n".join(f"- {line}" for line in lines)
    return (
        "\n\n<long_term_memory>\n"
        "以下是你在与该企业的历次对话中记下的长期记忆（事实与偏好），均为**已知背景**，"
        "在本次对话中应主动参考并保持一致；如与用户本次的新陈述冲突，以用户最新陈述为准。\n\n"
        f"{body}\n"
        "</long_term_memory>"
    )
