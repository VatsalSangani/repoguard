from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from state import AgentState
from agents.parser import parser_node
from agents.processor import processing_node
from agents.aggregator import aggregator_node
from agents.guardrails import guardrail_node, guardrail_router


def build_graph():
    memory = MemorySaver()
    workflow = StateGraph(AgentState)

    workflow.add_node("parser", parser_node)
    workflow.add_node("guardrails", guardrail_node)
    workflow.add_node("processor", processing_node)
    workflow.add_node("aggregator", aggregator_node)

    workflow.set_entry_point("parser")
    workflow.add_edge("parser", "guardrails")
    workflow.add_conditional_edges(
        "guardrails",
        guardrail_router,
        {"end_workflow": END, "human_approval": "processor"},
    )
    workflow.add_edge("processor", "aggregator")
    workflow.add_edge("aggregator", END)

    return workflow.compile(checkpointer=memory, interrupt_before=["processor"])
