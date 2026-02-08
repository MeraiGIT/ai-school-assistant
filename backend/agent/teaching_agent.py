"""LangGraph teaching agent for AI School Assistant."""

import logging
from typing import Optional

from langgraph.graph import StateGraph, END

from agent.nodes import (
    TeachingState,
    classify_intent,
    retrieve_knowledge,
    generate_answer,
    generate_practice,
    handle_greeting,
    handle_off_topic,
    escalate_to_human,
)

logger = logging.getLogger(__name__)


def build_teaching_agent(anthropic_key: str, knowledge_base) -> StateGraph:
    """Build and compile the LangGraph teaching agent."""

    # Wrap node functions to inject dependencies
    async def _classify(state: TeachingState) -> dict:
        return await classify_intent(state, anthropic_key)

    async def _retrieve(state: TeachingState) -> dict:
        return await retrieve_knowledge(state, knowledge_base)

    async def _answer(state: TeachingState) -> dict:
        return await generate_answer(state, anthropic_key)

    async def _practice(state: TeachingState) -> dict:
        return await generate_practice(state, anthropic_key)

    async def _greeting(state: TeachingState) -> dict:
        return await handle_greeting(state)

    async def _off_topic(state: TeachingState) -> dict:
        return await handle_off_topic(state)

    async def _escalate(state: TeachingState) -> dict:
        return await escalate_to_human(state)

    # Build the graph
    workflow = StateGraph(TeachingState)

    workflow.add_node("classify_node", _classify)
    workflow.add_node("retrieve_node", _retrieve)
    workflow.add_node("answer_node", _answer)
    workflow.add_node("practice_node", _practice)
    workflow.add_node("greeting_node", _greeting)
    workflow.add_node("off_topic_node", _off_topic)
    workflow.add_node("escalate_node", _escalate)

    workflow.set_entry_point("classify_node")

    # After classify, route based on intent
    def route_after_classify(state: TeachingState) -> str:
        if state.get("needs_human"):
            return "escalate_node"
        intent = state.get("intent", "question")
        if intent == "greeting":
            return "greeting_node"
        if intent == "off_topic":
            return "off_topic_node"
        return "retrieve_node"

    workflow.add_conditional_edges(
        "classify_node",
        route_after_classify,
        {
            "escalate_node": "escalate_node",
            "greeting_node": "greeting_node",
            "off_topic_node": "off_topic_node",
            "retrieve_node": "retrieve_node",
        },
    )

    workflow.add_edge("retrieve_node", "answer_node")

    # After answer, optionally generate practice
    def route_after_answer(state: TeachingState) -> str:
        if state.get("intent") == "practice":
            return "practice_node"
        return END

    workflow.add_conditional_edges(
        "answer_node",
        route_after_answer,
        {
            "practice_node": "practice_node",
            END: END,
        },
    )

    workflow.add_edge("practice_node", END)
    workflow.add_edge("greeting_node", END)
    workflow.add_edge("off_topic_node", END)
    workflow.add_edge("escalate_node", END)

    return workflow.compile()


class TeachingAgentRunner:
    """High-level runner for the teaching agent."""

    def __init__(self, anthropic_key: str, knowledge_base):
        self.agent = build_teaching_agent(anthropic_key, knowledge_base)

    async def respond(
        self,
        student_id: str,
        question: str,
        chat_history: list[dict] = None,
        student_level: str = "beginner",
        student_memory: str = "",
        formality: str = "formal",
    ) -> str:
        """Get a teaching response for a student question."""
        state: TeachingState = {
            "student_id": student_id,
            "question": question,
            "chat_history": chat_history or [],
            "intent": "",
            "retrieved_docs": "",
            "student_memory": student_memory,
            "answer": "",
            "student_level": student_level,
            "needs_human": False,
            "formality": formality,
        }

        result = await self.agent.ainvoke(state)
        return result.get("answer", "Извини, произошла ошибка. Попробуй ещё раз.")
