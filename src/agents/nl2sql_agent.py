import json
import os
import sys
from typing import Any, Optional, Tuple
from loguru import logger
from sqlalchemy import text
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.output_parsers import StrOutputParser

# Ensure src is in path
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.agents.prompts.agent_prompts import (
    build_nl2sql_prompt, 
    build_direct_prompt, 
    build_synthesiser_prompt
)
from src.infrastructure.db.sql_client import get_session
from src.infrastructure.db.crm_init import get_schema_for_prompt
from src.infrastructure.llm_token_cost import count_tokens, estimate_llm_cost_usd
from src.infrastructure.sql_safety import normalize_llm_sql, validate_readonly_sql
from src.infrastructure.observability import (
    observe,
    update_current_trace,
    update_current_observation,
)

_MAX_SQL_ATTEMPTS = 3
_SQL_FALLBACK_MESSAGE = (
    "I couldn't produce a safe answer for that question after a few tries. "
    "Try rephrasing, or ask for a simpler report (for example counts or a short list)."
)


class NL2SQLAgent:
    """
    Agent responsible for converting Natural Language to SQL, 
    executing it, and interpreting results using LangChain.
    """

    def __init__(self, llm: Any) -> None:
        """
        Args:
            llm: A LangChain ChatOpenAI or compatible instance.
        """
        self.llm = llm
        self.session = get_session()
        self.schema = get_schema_for_prompt()

    def _recover_db_session_after_error(self) -> None:
        """
        After a failed ``execute``, SQLAlchemy leaves the session in a transaction
        that must be rolled back before any further use (including retries).

        If the connection died (e.g. Supabase closed it), ``rollback`` may fail;
        then we close and open a new session so the next attempt gets a fresh
        connection from the pool (with ``pool_pre_ping``).
        """
        try:
            self.session.rollback()
        except Exception as rb_err:
            logger.warning(f"Session rollback after DB error failed: {rb_err}")
            try:
                self.session.close()
            except Exception:
                pass
            self.session = get_session()

    def _push_usage_cost_to_langfuse(
        self, system_prompt: str, user_prompt: str, output_text: str
    ) -> None:
        """tiktoken + local price table → Langfuse usage + total cost."""
        model_id = getattr(self.llm, "model_name", None)
        pt = count_tokens(system_prompt + "\n" + user_prompt)
        ct = count_tokens(output_text)
        update_current_observation(
            usage={
                "prompt_tokens": pt,
                "completion_tokens": ct,
                "total_tokens": pt + ct,
            },
            cost_details={"total": estimate_llm_cost_usd(pt, ct, model_id)},
            model=model_id,
        )

    def generate_sql(self, user_message: str, memory_context: str) -> Any:
        """
        Generates SQL or a clarification JSON from user message.
        """
        system_prompt, user_prompt = build_nl2sql_prompt(
            user_message=user_message,
            memory_context=memory_context,
            schema=self.schema
        )
        
        try:
            # Use direct messages to avoid curly brace parsing issues
            response = self.llm.invoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ])
            sql = response.content if hasattr(response, "content") else str(response)
            sql = sql.strip()
            
            # 1. Handle potential clarification JSON or direct errors
            if sql.startswith("{") or sql.startswith("Error"):
                return sql
            
            normalized = normalize_llm_sql(sql)
            ok, reason = validate_readonly_sql(normalized)
            if not ok:
                return json.dumps(
                    {
                        "clarification_needed": True,
                        "message": f"{reason} Please use a read-only question.",
                    }
                )
            
            # 2. Execute SQL and return results
            try:
                result = self.session.execute(text(normalized))
                if result.returns_rows:
                    return [dict(row._mapping) for row in result.all()]
                return f"Query executed successfully. Rows affected: {result.rowcount}"
                    
            except Exception as db_err:
                self._recover_db_session_after_error()
                logger.error(f"Database execution failed: {db_err}")
                return f"Database Error: {db_err}"
            
        except Exception as e:
            logger.error(f"NL2SQL generation failed: {e}")
            return f"Error: {e}"

    def generate_response(
        self, user_message: str, memory_context: str, reasoning: str = ""
    ) -> Tuple[str, str, str]:
        """
        Returns ``(answer_text, system_prompt, user_prompt)`` for Langfuse token/cost.
        """
        system_prompt, user_prompt = build_direct_prompt(
            user_message=user_message,
            memory_context=memory_context,
            reasoning=reasoning
        )

        try:
            response = self.llm.invoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ])
            text = response.content if hasattr(response, "content") else str(response)
            return text, system_prompt, user_prompt
        except Exception as e:
            logger.error(f"Direct response generation failed: {e}")
            return f"Error: {e}", system_prompt, user_prompt

    def interpret_results(
        self, user_message: str, tool_output: Any, memory_context: str, route: str = "sql_generator"
    ) -> Tuple[str, str, str]:
        """
        Returns ``(answer_text, system_prompt, user_prompt)`` for Langfuse token/cost.
        """
        system_prompt, user_prompt = build_synthesiser_prompt(
            user_message=user_message,
            tool_output=str(tool_output),
            memory_context=memory_context,
            route=route
        )

        try:
            response = self.llm.invoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ])
            text = response.content if hasattr(response, "content") else str(response)
            return text, system_prompt, user_prompt
        except Exception as e:
            logger.error(f"Synthesis failed: {e}")
            return f"Error: {e}", system_prompt, user_prompt

    # --- LangGraph Nodes ---

    @observe(name="NL2SQL Node", as_type="generation")
    def nl2sql_node(self, state: dict) -> dict:
        """
        Node: Generates and executes SQL with validation, up to ``_MAX_SQL_ATTEMPTS`` retries.
        """
        logger.info("--- NL2SQL NODE ---")
        user_msg = state.get("user_message", "")
        mem_ctx = state.get("memory_context", "")

        last_feedback: Optional[str] = None
        last_system = ""
        last_user = ""
        last_model_output = ""

        for attempt in range(1, _MAX_SQL_ATTEMPTS + 1):
            system_prompt, user_prompt = build_nl2sql_prompt(
                user_message=user_msg,
                memory_context=mem_ctx,
                schema=self.schema,
                retry_feedback=last_feedback,
            )
            last_system, last_user = system_prompt, user_prompt

            try:
                response = self.llm.invoke([
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=user_prompt),
                ])
                raw = response.content if hasattr(response, "content") else str(response)
                raw = raw.strip()
                last_model_output = raw
            except Exception as e:
                logger.error(f"NL2SQL LLM invoke failed (attempt {attempt}): {e}")
                last_feedback = f"LLM error: {e}"
                continue

            # Clarification JSON — pass to synthesizer for a friendly reply (no final_answer here)
            if raw.startswith("{") or raw.startswith("Error"):
                self._push_usage_cost_to_langfuse(system_prompt, user_prompt, raw)
                return {"result": raw, "sql_generated": None}

            sql = normalize_llm_sql(raw)
            ok, reason = validate_readonly_sql(sql)
            if not ok:
                logger.warning(f"SQL validation failed (attempt {attempt}): {reason}")
                last_feedback = f"Validation rejected the SQL ({reason}). Propose a single SELECT or clarification JSON."
                continue

            logger.info(f"Executing SQL (attempt {attempt}): {sql[:500]}...")
            update_current_observation(
                input=user_msg,
                metadata={"generated_sql": sql, "attempt": attempt},
            )

            try:
                result_proxy = self.session.execute(text(sql))
                if result_proxy.returns_rows:
                    rows = [dict(row._mapping) for row in result_proxy.all()]
                    update_current_observation(
                        output=str(rows),
                        metadata={"result_count": len(rows)},
                    )
                    self._push_usage_cost_to_langfuse(system_prompt, user_prompt, sql)
                    return {"result": rows, "sql_generated": sql}

                update_current_observation(
                    output=f"Affected rows: {result_proxy.rowcount}",
                    metadata={"affected_rows": result_proxy.rowcount},
                )
                self._push_usage_cost_to_langfuse(system_prompt, user_prompt, sql)
                return {
                    "result": f"Affected rows: {result_proxy.rowcount}",
                    "sql_generated": sql,
                }

            except Exception as db_err:
                self._recover_db_session_after_error()
                logger.error(f"Database execution failed (attempt {attempt}): {db_err}")
                last_feedback = (
                    f"PostgreSQL rejected the query: {db_err!s}. "
                    "Fix syntax/schema issues or ask for clarification via JSON."
                )

        self._push_usage_cost_to_langfuse(
            last_system,
            last_user,
            last_model_output or _SQL_FALLBACK_MESSAGE,
        )
        return {
            "final_answer": _SQL_FALLBACK_MESSAGE,
            "result": None,
            "sql_generated": None,
            "error": "sql_retry_exhausted",
        }

    @observe(name="Direct Node", as_type="generation")
    def direct_node(self, state: dict) -> dict:
        """
        Node: Handles direct greetings or refusals.
        """
        logger.info("--- DIRECT RESPONSE NODE ---")
        user_msg = state.get("user_message", "")
        mem_ctx = state.get("memory_context", "")
        reasoning = state.get("reasoning", "")
        
        answer, system_prompt, user_prompt = self.generate_response(user_msg, mem_ctx, reasoning)
        self._push_usage_cost_to_langfuse(system_prompt, user_prompt, answer)
        return {"final_answer": answer}

    @observe(name="Synthesizer Node", as_type="generation")
    def synthesizer_node(self, state: dict) -> dict:
        """
        Node: Interprets the results and produces the final answer.
        """
        logger.info("--- SYNTHESIZER NODE ---")
        user_msg = state.get("user_message", "")
        mem_ctx = state.get("memory_context", "")
        tool_output = state.get("result")
        route = state.get("route", "sql_generator")

        # For result_interpreter, we often don't have fresh tool_output; 
        # the synthesizer should use memory instead.
        if tool_output is None and route != "result_interpreter":
            return {"final_answer": "I couldn't find any data to analyze."}
            
        # Use a placeholder if None for result_interpreter to satisfy the prompt builder
        effective_output = tool_output if tool_output is not None else "Refer to memory context"

        update_current_observation(
            input=str(effective_output),
            metadata={"route_context": route}
        )

        response, system_prompt, user_prompt = self.interpret_results(
            user_msg, effective_output, mem_ctx, route
        )
        
        update_current_observation(output=response)
        self._push_usage_cost_to_langfuse(system_prompt, user_prompt, response)
        
        return {"final_answer": response}
