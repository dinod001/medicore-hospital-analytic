import json
from loguru import logger
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from src.agents.prompts.agent_prompts import build_router_prompt

# Valid routes
VALID_ROUTES = {"result_interpreter", "sql_generator", "direct"}

@dataclass
class RouteDecision:
    route: str = "direct"
    confidence: float = 0.0
    reasoning: str = ""


class QueryRouter:
    """
    Routes user queries to the appropriate tool path.

    Uses an LLM call with structured JSON output to classify intent.
    Falls back to ``direct`` on parse errors.
    """

    def __init__(self, llm: Any) -> None:
        """
        Args:
            llm: A LangChain ``ChatOpenAI`` (or compatible) instance.
        """
        self.llm = llm

    def route(
        self,
        user_message: str,
        memory_context: str,
    ) -> RouteDecision:
        """
        Classify user intent and extract parameters.

        Traced as a LangFuse **generation** so cost/tokens are captured.
        """
        system_prompt, user_prompt = build_router_prompt(
            user_message=user_message,
            memory_context=memory_context
        )
        try:
            response = self.llm.invoke(
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ]
            )
            content = (
                response.content
                if hasattr(response, "content")
                else str(response)
            )

            # Extract and log token usage
            usage: Dict[str, int] = {}
            if hasattr(response, "response_metadata"):
                meta = response.response_metadata or {}
                token_usage = meta.get("token_usage") or meta.get("usage", {})
                if token_usage:
                    usage = {
                        "input": token_usage.get("prompt_tokens", 0),
                        "output": token_usage.get("completion_tokens", 0),
                        "total": token_usage.get("total_tokens", 0),
                    }
            if usage:
                logger.debug(
                    "Router tokens — in:{} out:{} total:{}",
                    usage["input"], usage["output"], usage["total"],
                )


        except Exception as exc:
            logger.error("Router LLM call failed: {}", exc)
            return RouteDecision(
                route="direct",
                confidence=0.0,
                reasoning=f"Router LLM error: {exc}",
            )

        return self._parse_response(content)

    # ------------------------------------------------------------------
    def _parse_response(self, content: str) -> RouteDecision:
        """
        Parse the LLM's raw JSON string into a RouteDecision.

        Falls back to ``direct`` on any parse or validation error so the
        pipeline always has a safe, usable decision to continue with.
        """
        try:
            # Strip accidental markdown fences the LLM might add
            cleaned = content.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            data: Dict[str, Any] = json.loads(cleaned)

            route = str(data.get("route", "direct")).lower()
            if route not in VALID_ROUTES:
                logger.warning("Router returned unknown route '{}', falling back to 'direct'.", route)
                route = "direct"

            return RouteDecision(
                route=route,
                confidence=float(data.get("confidence", 0.0)),
                reasoning=str(data.get("reasoning", "")),
            )

        except (json.JSONDecodeError, ValueError, TypeError) as exc:
            logger.warning("Router response parse failed ({}): {!r}", exc, content)
            return RouteDecision(
                route="direct",
                confidence=0.0,
                reasoning=f"Parse error — defaulting to direct. Raw: {content[:120]}",
            )
