"""长期记忆上下文渲染纯函数单测。

覆盖：无条目返回空串(不注入块)、有条目渲染为 <long_term_memory> 块逐条列出、
空白条目被过滤。无 IO。
"""

from app.domain.models.agent_memory import AgentMemory
from app.domain.services.memory_context import render_memory_context


def test_empty_memories_render_nothing():
    """无记忆条目：返回空串，不注入任何上下文块。"""
    assert render_memory_context([]) == ""


def test_blank_contents_are_filtered_to_empty():
    """仅有空白内容的条目：过滤后视为无条目，返回空串。"""
    memories = [AgentMemory(tenant_id="t1", content="   "), AgentMemory(tenant_id="t1", content="")]
    assert render_memory_context(memories) == ""


def test_memories_render_as_long_term_memory_block():
    """有条目：渲染为 <long_term_memory> 块，逐条列出，并声明为已知背景。"""
    memories = [
        AgentMemory(tenant_id="t1", content="该企业2026年新增3项发明专利"),
        AgentMemory(tenant_id="t1", content="用户偏好回答简洁、不要列表"),
    ]
    ctx = render_memory_context(memories)

    assert ctx.startswith("\n\n<long_term_memory>")
    assert ctx.endswith("</long_term_memory>")
    assert "该企业2026年新增3项发明专利" in ctx
    assert "用户偏好回答简洁、不要列表" in ctx
    assert "已知背景" in ctx
