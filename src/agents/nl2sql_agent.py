import os
import sys
from typing import Any
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
            
            # 1. Handle potential clarification JSON or direct errors
            if sql.strip().startswith("{") or sql.strip().startswith("Error"):
                return sql.strip()
            
            # 2. Execute SQL and return results
            try:
                result = self.session.execute(text(sql))
                if result.returns_rows:
                    return [dict(row._mapping) for row in result.all()]
                return f"Query executed successfully. Rows affected: {result.rowcount}"
                    
            except Exception as db_err:
                logger.error(f"Database execution failed: {db_err}")
                return f"Database Error: {db_err}"
            
        except Exception as e:
            logger.error(f"NL2SQL generation failed: {e}")
            return f"Error: {e}"

    def generate_response(self, user_message: str, memory_context: str, reasoning: str = "") -> str:
        """
        Generates a direct response to the user (greetings, out-of-scope, etc.).
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
            return response.content if hasattr(response, "content") else str(response)
        except Exception as e:
            logger.error(f"Direct response generation failed: {e}")
            return f"Error: {e}"

    def interpret_results(self, user_message: str, tool_output: Any, memory_context: str, route: str = "sql_generator") -> str:
        """
        Generates a human-readable explanation of SQL results.
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
            return response.content if hasattr(response, "content") else str(response)
        except Exception as e:
            logger.error(f"Synthesis failed: {e}")
            return f"Error: {e}"

    # --- LangGraph Nodes ---

    def nl2sql_node(self, state: dict) -> dict:
        """
        Node: Generates and executes SQL.
        """
        logger.info("--- NL2SQL NODE ---")
        user_msg = state.get("user_message", "")
        mem_ctx = state.get("memory_context", "")
        
        # We need to capture both SQL and results
        system_prompt, user_prompt = build_nl2sql_prompt(
            user_message=user_msg,
            memory_context=mem_ctx,
            schema=self.schema
        )
        
        try:
            response = self.llm.invoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ])
            sql = response.content if hasattr(response, "content") else str(response)
            sql = sql.strip()

            # 1. Handle potential clarification JSON or direct errors
            if sql.startswith("{") or sql.startswith("Error"):
                return {"final_answer": sql, "result": None, "sql_generated": None}
            
            # 2. Execute SQL
            logger.info(f"Executing SQL: {sql}")
            try:
                result_proxy = self.session.execute(text(sql))
                if result_proxy.returns_rows:
                    rows = [dict(row._mapping) for row in result_proxy.all()]
                    return {"result": rows, "sql_generated": sql}
                return {
                    "result": f"Affected rows: {result_proxy.rowcount}", 
                    "sql_generated": sql
                }
                    
            except Exception as db_err:
                logger.error(f"Database execution failed: {db_err}")
                return {"error": str(db_err), "sql_generated": sql}
            
        except Exception as e:
            logger.error(f"NL2SQL node failed: {e}")
            return {"error": str(e)}

    def direct_node(self, state: dict) -> dict:
        """
        Node: Handles direct greetings or refusals.
        """
        logger.info("--- DIRECT RESPONSE NODE ---")
        user_msg = state.get("user_message", "")
        mem_ctx = state.get("memory_context", "")
        reasoning = state.get("reasoning", "")
        
        response = self.generate_response(user_msg, mem_ctx, reasoning)
        return {"final_answer": response}

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

        response = self.interpret_results(user_msg, effective_output, mem_ctx, route)
        return {"final_answer": response}
