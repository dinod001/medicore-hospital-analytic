import json
import re
from loguru import logger
from dataclasses import dataclass
from typing import Any
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.messages import SystemMessage, HumanMessage
from src.agents.prompts.agent_prompts import build_router_prompt
from src.infrastructure.llm_token_cost import count_tokens, estimate_llm_cost_usd
from src.infrastructure.observability import (
    observe,
    update_current_observation,
)


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

    def route(
        self, user_message: str, memory_context: str
    ) -> tuple[RouteDecision, str, str, str]:
        """
        Returns ``(decision, system_prompt, user_prompt, assistant_text)`` for token/cost.
        On failure, prompts and assistant text are empty strings.
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
            
            raw_text = response.content if hasattr(response, "content") else str(response)
            content = raw_text
            
            # Use regex to find the JSON block
            match = re.search(r"\{.*\}", content, re.DOTALL)
            if match:
                content = match.group(0)

            data = json.loads(content)
            decision = RouteDecision(
                route=data.get("route", "direct"),
                confidence=data.get("confidence", 0.0),
                reasoning=data.get("reasoning", "")
            )
            return decision, system_prompt, user_prompt, raw_text
        except Exception as e:
            logger.error(f"Routing failed: {e}")
            return (
                RouteDecision(route="direct", confidence=0.0, reasoning=f"Error: {e}"),
                "",
                "",
                "",
            )

    @observe(name="Routing Node", as_type="generation")
    def route_node(self, state: dict) -> dict:
        """
        LangGraph Node: Routes the query based on the current state.
        """
        logger.info("--- ROUTING NODE ---")
        user_msg = state.get("user_message", "")
        mem_ctx = state.get("memory_context", "")

        # 1. Update observation with input
        update_current_observation(input=user_msg)

        decision, system_prompt, user_prompt, assistant_text = self.route(user_msg, mem_ctx)
        
        # 2. Update observation with decision as output
        update_current_observation(
            output=decision.route,
            metadata={
                "confidence": decision.confidence,
                "reasoning": decision.reasoning
            }
        )

        model_id = getattr(self.llm, "model_name", None)
        if system_prompt and assistant_text:
            pt = count_tokens(system_prompt + "\n" + user_prompt)
            ct = count_tokens(assistant_text)
            update_current_observation(
                usage={
                    "prompt_tokens": pt,
                    "completion_tokens": ct,
                    "total_tokens": pt + ct,
                },
                cost_details={"total": estimate_llm_cost_usd(pt, ct, model_id)},
                model=model_id,
            )
        
        return {
            "route": decision.route,
            "reasoning": decision.reasoning
        }
