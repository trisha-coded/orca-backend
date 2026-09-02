from typing import Any, Dict
from app.state import MarineAgentState
from app.agents.supervisor import supervisor_intent_parser
from app.agents.domain_agents import (
    weather_agent_node,
    ocean_agent_node,
    geofence_agent_node,
)
from app.agents.synthesizer import safety_evaluator_node, synthesizer_node

# Attempt LangGraph compilation if available
try:
    from langgraph.graph import StateGraph, START, END
    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False


def build_marine_langgraph():
    """Constructs compiled LangGraph StateGraph workflow."""
    if not LANGGRAPH_AVAILABLE:
        return None

    workflow = StateGraph(MarineAgentState)

    # 1. Add Agent & Evaluator Nodes
    workflow.add_node("supervisor", supervisor_intent_parser)
    workflow.add_node("weather_agent", weather_agent_node)
    workflow.add_node("ocean_agent", ocean_agent_node)
    workflow.add_node("geofence_agent", geofence_agent_node)
    workflow.add_node("safety_evaluator", safety_evaluator_node)
    workflow.add_node("synthesizer", synthesizer_node)

    # 2. Add Linear & Conditional Edges
    workflow.add_edge(START, "supervisor")
    workflow.add_edge("supervisor", "weather_agent")
    workflow.add_edge("weather_agent", "ocean_agent")
    workflow.add_edge("ocean_agent", "geofence_agent")
    workflow.add_edge("geofence_agent", "safety_evaluator")
    workflow.add_edge("safety_evaluator", "synthesizer")
    workflow.add_edge("synthesizer", END)

    return workflow.compile()


# Global compiled graph instance
compiled_graph = build_marine_langgraph()


async def run_marine_decision_pipeline(initial_state: MarineAgentState) -> MarineAgentState:
    """
    Executes the multi-agent decision support workflow asynchronously.
    Seamlessly utilizes LangGraph when available or falls back to direct async node dispatch.
    """
    if compiled_graph is not None:
        result = await compiled_graph.ainvoke(initial_state)
        return result

    # Deterministic Async Fallback Dispatch
    state = supervisor_intent_parser(initial_state)
    state = await weather_agent_node(state)
    state = await ocean_agent_node(state)
    state = geofence_agent_node(state)
    state = safety_evaluator_node(state)
    state = synthesizer_node(state)

    return state
