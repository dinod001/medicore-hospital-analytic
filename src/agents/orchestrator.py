from loguru import logger
from src.agents.router import QueryRouter
from src.agents.nl2sql_agent import NL2SQLAgent
from src.agents.state import AgentState
from typing import Any, Dict, Optional
from langgraph.graph import StateGraph, END
from src.infrastructure.observability import (
    observe,
    update_current_trace,
)
from src.dashboard.chart_from_result import tabular_result_to_chart


class AgentOrchestrator:
    """
    Routes queries to the appropriate tool and manages the conversation flow using LangGraph.
    """
    def __init__(self, llm, db_connector=None):
        self.router = QueryRouter(llm=llm)
        self.nl2sql_agent = NL2SQLAgent(llm=llm)
        # Build and compile the graph once during initialization
        self.graph = self.build_graph()
        
    def _format_memory(self, memory_context: list) -> str:
        """Converts memory list of dicts to a formatted string for prompts."""
        if not memory_context:
            return "No prior context."
        return "\n".join([f"{m['role'].upper()}: {m['content']}" for m in memory_context])

    def build_graph(self) -> StateGraph:
        """Constructs the LangGraph state machine."""
        workflow = StateGraph(AgentState)

        # 1. Define Nodes
        workflow.add_node("router", self.router.route_node)
        workflow.add_node("nl2sql_agent", self.nl2sql_agent.nl2sql_node)
        workflow.add_node("direct_agent", self.nl2sql_agent.direct_node)
        workflow.add_node("synthesizer", self.nl2sql_agent.synthesizer_node)
        
        # 2. Define Routing Logic
        def route_decision(state: AgentState):
            # If nl2sql_node already set a final_answer (like a clarification), we end
            if state.get("final_answer"):
                return END
            
            route = state.get("route")
            if route == "direct":
                return "direct_agent"
            elif route == "sql_generator":
                return "nl2sql_agent"
            elif route == "result_interpreter":
                return "synthesizer"
            else:
                return "direct_agent"

        workflow.add_conditional_edges(
            "router",
            route_decision,
            {
                "direct_agent": "direct_agent",
                "nl2sql_agent": "nl2sql_agent",
                "synthesizer": "synthesizer",
                END: END
            }
        )

        def after_nl2sql(state: AgentState):
            """Skip synthesizer when NL2SQL already produced the final user-facing answer (retry fallback)."""
            if state.get("final_answer"):
                return END
            return "synthesizer"

        workflow.add_conditional_edges(
            "nl2sql_agent",
            after_nl2sql,
            {"synthesizer": "synthesizer", END: END},
        )
        workflow.add_edge("synthesizer", END)
        workflow.add_edge("direct_agent", END)

        # 4. Set Entry Point
        workflow.set_entry_point("router")

        return workflow.compile()

    @observe()
    def chat_with_sql_agent(
        self, 
        user_message: str,
        memory_context: list,
        max_retries: int = 3,
    ) -> Dict[str, Any]:
        """
        Invokes the LangGraph workflow to process the user message.

        ``max_retries`` is how many times to re-run the graph if invocation throws
        (transient errors); NL2SQL SQL retries are handled inside ``nl2sql_node``.
        """
        logger.info(f"Starting LangGraph workflow for: {user_message}")
        
        # 1. Prepare initial state
        initial_state: AgentState = {
            "user_message": user_message,
            "memory_context": self._format_memory(memory_context),
            "messages": [], # Standard history if needed
            "route": None,
            "reasoning": None,
            "sql_generated": None,
            "result": None,
            "final_answer": None,
            "error": None,
            "user_id": "default_user",
            "session_id": "default_session"
        }

        # 2. Log global trace info for Langfuse
        update_current_trace(
            user_id=initial_state["user_id"],
            session_id=initial_state["session_id"],
            tags=["v1.0", "langgraph-flow"],
            metadata={"source": "cli_chat"}
        )

        try:
            final_state: Optional[Dict[str, Any]] = None
            last_exc: Optional[Exception] = None
            for attempt in range(max_retries + 1):
                try:
                    final_state = self.graph.invoke(initial_state)
                    last_exc = None
                    break
                except Exception as e:
                    last_exc = e
                    logger.warning(
                        "Graph invoke failed (attempt {}/{}): {}",
                        attempt + 1,
                        max_retries + 1,
                        e,
                    )
            if last_exc is not None:
                raise last_exc
            assert final_state is not None
            
            # 3. Update memory (Side effect outside the graph for now to keep it simple)
            if final_state.get("final_answer"):
                memory_context.extend([
                    {"role": "user", "content": user_message},
                    {"role": "assistant", "content": final_state["final_answer"]}
                ])
                
                # Sliding window
                if len(memory_context) > 10:
                    del memory_context[:2]

            payload: Dict[str, Any] = {
                "status": "completed",
                "route": final_state.get("route"),
                "message": final_state.get("final_answer"),
                "insight": final_state.get("final_answer"),
                "result": final_state.get("result"),
                "sql_generated": final_state.get("sql_generated"),
            }
            chart = tabular_result_to_chart(
                final_state.get("result"),
                user_message=user_message,
            )
            if chart:
                payload["chart"] = chart
            payload["memory"] = memory_context
            return payload
            
        except Exception as e:
            logger.error(f"Graph execution failed: {e}")
            return {
                "status": "error",
                "message": f"I encountered an error while processing your request: {str(e)}",
                "error": str(e)
            }