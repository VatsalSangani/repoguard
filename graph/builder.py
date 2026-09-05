from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from state import AgentState
from agents.parser import parser_node
from agents.aggregator import aggregator_node
from agents.guardrails import guardrail_node, guardrail_router
from agents.router import router_node, route_after_router
from agents.lang_agents.python_agent import python_agent_node
from agents.lang_agents.sql_agent import sql_agent_node
from agents.lang_agents.js_agent import js_agent_node
from agents.lang_agents.json_agent import json_agent_node


def build_graph():
    memory = MemorySaver()
    workflow = StateGraph(AgentState)

    workflow.add_node("parser", parser_node)
    workflow.add_node("guardrails", guardrail_node)
    workflow.add_node("router", router_node)
    workflow.add_node("python_agent", python_agent_node)
    workflow.add_node("sql_agent", sql_agent_node)
    workflow.add_node("js_agent", js_agent_node)
    workflow.add_node("json_agent", json_agent_node)
    workflow.add_node("aggregator", aggregator_node)

    workflow.set_entry_point("parser")
    workflow.add_edge("parser", "guardrails")
    workflow.add_conditional_edges(
        "guardrails",
        guardrail_router,
        {"end_workflow": END, "human_approval": "router"},
    )
    workflow.add_conditional_edges(
        "router",
        route_after_router,
        ["python_agent", "sql_agent", "js_agent", "json_agent", "aggregator"],
    )
    workflow.add_edge("python_agent", "aggregator")
    workflow.add_edge("sql_agent", "aggregator")
    workflow.add_edge("js_agent", "aggregator")
    workflow.add_edge("json_agent", "aggregator")
    workflow.add_edge("aggregator", END)

    # HITL pause moves from "processor" (Phase 0) to "router" (Phase 1) —
    # router is now the first node after approval that touches file content.
    return workflow.compile(checkpointer=memory, interrupt_before=["router"])
