import json
import re
from loguru import logger
from dataclasses import dataclass
from typing import Any
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.messages import SystemMessage, HumanMessage
from src.agents.prompts.agent_prompts import build_router_prompt

@dataclass
class RouteDecision:
    route: str = "direct"
    confidence: float = 0.0
    reasoning: str = ""


class QueryRouter:
    """
    Routes user queries to the appropriate tool path using LangChain.
    """

    def __init__(self, llm: Any) -> None:
        """
        Args:
            llm: A LangChain ChatOpenAI or compatible instance.
        """
        self.llm = llm

    def route(self, user_message: str, memory_context: str) -> RouteDecision:
        """
        Original routing logic for backward compatibility.
        """
        system_prompt, user_prompt = build_router_prompt(
            user_message=user_message,
            memory_context=memory_context
        )
        
        try:
            # Use direct messages to avoid curly brace parsing issues with ChatPromptTemplate
            response = self.llm.invoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ])
            
            content = response.content if hasattr(response, "content") else str(response)
            
            # Use regex to find the JSON block
            match = re.search(r"\{.*\}", content, re.DOTALL)
            if match:
                content = match.group(0)

            data = json.loads(content)
            return RouteDecision(
                route=data.get("route", "direct"),
                confidence=data.get("confidence", 0.0),
                reasoning=data.get("reasoning", "")
            )
        except Exception as e:
            logger.error(f"Routing failed: {e}")
            return RouteDecision(route="direct", confidence=0.0, reasoning=f"Error: {e}")

    def route_node(self, state: dict) -> dict:
        """
        LangGraph Node: Routes the query based on the current state.
        """
        logger.info("--- ROUTING NODE ---")
        user_msg = state.get("user_message", "")
        mem_ctx = state.get("memory_context", "")

        decision = self.route(user_msg, mem_ctx)
        
        return {
            "route": decision.route,
            "reasoning": decision.reasoning
        }
