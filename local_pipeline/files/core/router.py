"""
Router: decides which agent should handle the user query.

Currently rule-based:
- If keywords related to math are present, route to MathAgent.
- If logic keywords are present, route to LogicAgent.
- Otherwise default to MathAgent (conservative).

Router returns a unified structured dict result from the agent, ready to be
converted to JSON by the app.
"""
import logging
from typing import Dict, Optional

from agents.logic_agent import LogicAgent
from agents.math_agent import MathAgent
from core.prompt_templates import ROUTER_HINTS

logger = logging.getLogger("mathminds.router")


class Router:
    def __init__(self):
        self.math_agent = MathAgent()
        self.logic_agent = LogicAgent()

    def _is_logic(self, query: str) -> bool:
        q = query.lower()
        for hint in ROUTER_HINTS.get("logic", []):
            if hint in q:
                return True
        return False

    def _is_math(self, query: str) -> bool:
        q = query.lower()
        for hint in ROUTER_HINTS.get("math", []):
            if hint in q:
                return True
        return False

    def route(self, query: str, request_id: Optional[str] = None, timestamp: Optional[str] = None) -> Dict:
        """
        Route the query to the appropriate agent and return agent result.
        """
        logger.info("Routing query: %s", query)
        agent_name = "math"

        if self._is_logic(query):
            agent_name = "logic"
        elif self._is_math(query):
            agent_name = "math"
        else:
            # Default fallback
            agent_name = "math"

        if agent_name == "math":
            return self.math_agent.handle(query, request_id=request_id, timestamp=timestamp)
        else:
            return self.logic_agent.handle(query, request_id=request_id, timestamp=timestamp)