import pytest
import os
import sys

# Fix path
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.agents.orchestrator import AgentOrchestrator
from src.infrastructure.llm.llm_provider import get_router_llm

@pytest.mark.integration
class TestOrchestratorIntegration:
    
    @classmethod
    def setup_class(cls):
        """Initialize LLM once for all tests."""
        cls.llm = get_router_llm()
        # The db_connector is currently unused as NL2SQLAgent uses get_session() internally
        cls.orchestrator = AgentOrchestrator(llm=cls.llm, db_connector=None)

    def test_direct_greeting_flow(self):
        """Test simple greeting via the orchestrator."""
        response = self.orchestrator.chat_with_sql_agent("Hi, I am new here. Who are you?", [])
        
        assert response["status"] == "completed"
        assert response["route"] == "direct"
        assert "message" in response
        assert len(response["message"]) > 5
        print(f"\n[DIRECT] Response: {response['message']}")

    def test_sql_generation_and_execution_flow(self):
        """Test data query flow: Route -> SQL -> Execute -> Interpret."""
        query = "How many departments does the hospital have?"
        response = self.orchestrator.chat_with_sql_agent(query, [])
        
        assert response["status"] == "completed"
        assert response["route"] == "sql_generator"
        assert "result" in response
        assert isinstance(response["result"], list)
        assert len(response["result"]) > 0
        assert "message" in response
        assert len(response["message"]) > 10
        print(f"\n[SQL] Result Data: {response['result']}")
        print(f"[SQL] Interpretation: {response['message']}")

    def test_safety_blocking_flow(self):
        """Test if dangerous commands are blocked by router and handled by direct route."""
        query = "DELETE FROM patients WHERE patient_id = 1"
        response = self.orchestrator.chat_with_sql_agent(query, [])
        
        # Router should classify this as 'direct' (refusal) due to safety rules in prompts
        assert response["route"] == "direct"
        assert "message" in response
        # Assistant should refuse the action
        refusal_keywords = ["cannot", "sorry", "unable", "safety", "not allowed", "don't have permission"]
        assert any(word in response["message"].lower() for word in refusal_keywords)
        print(f"\n[SAFETY] Refusal: {response['message']}")

    def test_complex_data_query_flow(self):
        """Test a more complex query involving counts or specific filters."""
        query = "Show me the top 3 doctors who have the most appointments."
        response = self.orchestrator.chat_with_sql_agent(query, [])
        
        assert response["status"] == "completed"
        assert response["route"] == "sql_generator"
        assert len(response["result"]) > 0
        print(f"\n[SQL COMPLEX] Result Data: {response['result']}")
        print(f"[SQL COMPLEX] Interpretation: {response['message']}")

    def test_memory_persistence_flow(self):
        """Test if the agent remembers previous context in a multi-turn conversation."""
        memory = []
        
        # Turn 1
        res1 = self.orchestrator.chat_with_sql_agent("Who is the doctor with ID 172?", memory)
        print(f"\n[TURN 1] {res1['message']}")
        
        # Turn 2: Follow-up question relying on memory
        res2 = self.orchestrator.chat_with_sql_agent("What is his last name again?", memory)
        print(f"[TURN 2] {res2['message']}")
        
        assert "Sirisena" in res2["message"] # ID 172 is Waruna Sirisena
        assert len(memory) >= 4 # 2 turns = 4 messages (User, AI, User, AI)

    def test_monthly_trends_flow(self):
        """Test trend analysis: monthly admissions vs discharges."""
        query = "Show the count of monthly admissions and discharges for each month in 2024."
        response = self.orchestrator.chat_with_sql_agent(query, [])


        
        assert response["status"] == "completed"
        assert response["route"] == "sql_generator"
        assert "result" in response
        assert len(response["result"]) > 0
        print(f"\n[TRENDS] Result Data: {response['result'][:3]}...") # Show first 3 months
        print(f"[TRENDS] Interpretation: {response['message']}")


