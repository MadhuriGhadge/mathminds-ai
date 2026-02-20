import enum
import logging

logger = logging.getLogger(__name__)

class RouteType(enum.Enum):
    WEB = "web"
    SYMBOLIC = "symbolic"
    GENERATIVE = "generative" # Default Gemini Flow

class QueryRouter:
    """
    Classifies user queries to determine the best execution path.
    """
    
    def __init__(self):
        # Keywords for Web Search
        self.web_keywords = [
            "stock", "price", "weather", "news", "current", "latest", "today's", 
            "who is", "when is", "population", "rate", "what is",
            "http", "https"
        ]
        
        # Keywords for Symbolic Math
        self.symbolic_keywords = [
            "integrate", "derivative", "derive", "plot", "solve for", 
            "simplify", "factor", "limit of", "proof"
        ]

    def route(self, query: str) -> RouteType:
        """
        Determines the route based on query content.
        """
        if not query:
            return RouteType.GENERATIVE
            
        q_lower = query.lower()
        
        # Check Web
        if any(kw in q_lower for kw in self.web_keywords):
            logger.info("Routing to WEB")
            return RouteType.WEB
            
        # Check Symbolic
        if any(kw in q_lower for kw in self.symbolic_keywords):
            logger.info("Routing to SYMBOLIC")
            return RouteType.SYMBOLIC
            
        # Default
        logger.info("Routing to GENERATIVE (Default)")
        return RouteType.GENERATIVE
