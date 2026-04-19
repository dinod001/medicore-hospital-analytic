import os
import sys
from typing import Any, Optional
from loguru import logger
from dotenv import load_dotenv

# Fix Python path so 'src' can be imported when running this script directly
# The root is 3 levels up from this file: src/agents/nl2sql_agent.py
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.agents.prompts.agent_prompts import build_nl2sql_prompt
from src.infrastructure.llm.llm_provider import get_router_llm

# Load API keys
load_dotenv()

class NL2SQLAgent:
    """
    Agent responsible for converting Natural Language to SQL.
    Uses the schema defined in data/schema.sql.
    """

    def __init__(self, llm: Any, schema_path: str = "data/schema.sql") -> None:
        """
        Args:
            llm: A LangChain ChatOpenAI or compatible instance.
            schema_path: Path to the .sql file containing the DDL.
        """
        self.llm = llm
        self.schema_path = schema_path
        self._schema_cache: Optional[str] = None

    def _load_schema(self) -> str:
        """Loads the schema from the SQL file and caches it."""
        if self._schema_cache:
            return self._schema_cache

        if not os.path.exists(self.schema_path):
            logger.error(f"Schema file not found at {self.schema_path}")
            return "Error: Schema definition missing."

        try:
            with open(self.schema_path, "r", encoding="utf-8") as f:
                content = f.read()
                # Clean up: remove DROP TABLE statements to not confuse the LLM
                lines = [l for l in content.splitlines() if not l.strip().upper().startswith("DROP TABLE")]
                # Also remove empty lines or comments if needed, but keeping DDL is fine
                self._schema_cache = "\n".join(lines).strip()
                return self._schema_cache
        except Exception as e:
            logger.error(f"Failed to load schema: {e}")
            return f"Error loading schema: {e}"

    def generate_sql(self, user_message: str, memory_context: str) -> str:
        """
        Generates a SQL query based on the user's question and database schema.
        
        Returns:
            The raw SQL query string or a clarification message.
        """
        schema = self._load_schema()
        system_prompt, user_prompt = build_nl2sql_prompt(
            user_message=user_message,
            memory_context=memory_context,
            schema=schema
        )

        try:
            response = self.llm.invoke([
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ])
            
            sql = response.content if hasattr(response, "content") else str(response)
            
            # Clean up: sometimes LLMs wrap SQL in markdown blocks
            if "```" in sql:
                parts = sql.split("```")
                if len(parts) >= 2:
                    sql = parts[1]
                    if sql.startswith("sql"):
                        sql = sql[3:]
            
            return sql.strip()
            
        except Exception as e:
            logger.error(f"NL2SQL generation failed: {e}")
            return f"Error: {e}"

# if __name__ == "__main__":
#     # Test execution
#     test_llm = get_router_llm()
#     test_agent = NL2SQLAgent(llm=test_llm)
    
#     test_query = "How many patients were admitted last week?"
#     print(f"\nUser Query: {test_query}")
#     print("-" * 40)
    
#     sql_out = test_agent.generate_sql(test_query, "")
#     print(f"Generated SQL:\n{sql_out}\n")

