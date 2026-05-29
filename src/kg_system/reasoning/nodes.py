from __future__ import annotations

from kg_system.core.exceptions import NotImplementedInSkeleton
from kg_system.reasoning.state import ReasonerState


async def retrieve_node(state: ReasonerState) -> ReasonerState:
    """根据 question 检索 Neo4j 子图。骨架占位。"""
    raise NotImplementedInSkeleton("reasoning.retrieve_node")


async def reason_node(state: ReasonerState) -> ReasonerState:
    """LLM 基于 subgraph + question 推理一步。骨架占位。"""
    raise NotImplementedInSkeleton("reasoning.reason_node")


async def decide_node(state: ReasonerState) -> ReasonerState:
    """判断是否需要再检索 / 已可生成答案。骨架占位。"""
    raise NotImplementedInSkeleton("reasoning.decide_node")


async def generate_node(state: ReasonerState) -> ReasonerState:
    """生成最终答案。骨架占位。"""
    raise NotImplementedInSkeleton("reasoning.generate_node")


def route_after_decide(state: ReasonerState) -> str:
    """conditional_edges 路由函数。骨架占位。"""
    return state.get("next_action", "end")
