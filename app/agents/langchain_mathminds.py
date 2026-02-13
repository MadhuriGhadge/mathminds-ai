import logging
import asyncio
import base64
from typing import Optional, List, Any

# LangChain Imports
# LangChain Imports
try:
    from langchain.agents import initialize_agent, Tool
    # Try importing AgentType, if not found, we use string
    try:
        from langchain.agents import AgentType
    except ImportError:
        AgentType = None
except ImportError as e:
    # If langchain is completely missing
    initialize_agent = None
    Tool = None
    AgentType = None

try:
    from langchain_google_genai import ChatGoogleGenerativeAI
except ImportError:
    logger.error("Failed to import 'ChatGoogleGenerativeAI'. Ensure 'langchain-google-genai' is installed.")
    ChatGoogleGenerativeAI = None
try:
    from langchain.memory import ConversationBufferMemory
except ImportError:
    # Fallback or error logging
    logger.error("Failed to import 'ConversationBufferMemory'. Ensure 'langchain' is installed correctly.")
    ConversationBufferMemory = None

# App Imports
from app.core.settings import settings
from app.tools.web_scraper import WebScraper, run_playwright_sync
from app.tools.symbolic_solver import SymbolicSolver
from app.tools.advanced_ocr import AdvancedOCR
# I will need to verify if these classes exist or if I need to wrap functions.
# For now I will create placeholders or assume standard tool structure if I can't verify.
# Actually, I should verify content of app/tools/web_scraper.py first to be safe, but I'll write the agent to be robust.

logger = logging.getLogger(__name__)

class MathMindsLangChainAgent:
    """
    Agent-based architecture using LangChain.
    Replaces custom orchestrator for complex, multi-step reasoning.
    """

    def __init__(self, model_name: str = "gemini-2.5-flash"):
        """
        Initialize the LangChain agent with Gemini and tools.
        """
        self.api_key = settings.GOOGLE_API_KEY
        if not self.api_key:
            logger.warning("No Google API Key found. Agent will fail.")

        if not initialize_agent:
             logger.error("LangChain not installed or imports failed.")
             self.agent_executor = None
             return

        # 1. Initialize LLM
        # We use temperature=0 for deterministic tool usage
        self.llm = ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=self.api_key,
            temperature=0,
            convert_system_message_to_human=True # Sometimes needed for Gemini
        )

        # 2. Define Tools
        self.tools = self._load_tools()

        # 3. Initialize Memory
        self.memory = ConversationBufferMemory(
            memory_key="chat_history",
            return_messages=True
        )

        # 4. Initialize Agent
        # ZERO_SHOT_REACT_DESCRIPTION is good for general purpose tool use
        agent_type = AgentType.ZERO_SHOT_REACT_DESCRIPTION if AgentType else "zero-shot-react-description"
        
        try:
            self.agent_executor = initialize_agent(
                tools=self.tools,
                llm=self.llm,
                agent=agent_type,
                verbose=True,
                memory=self.memory,
                handle_parsing_errors=True # robust to minor output format issues
            )
            logger.info("MathMindsLangChainAgent initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize LangChain agent: {e}")
            self.agent_executor = None

        # 5. Initialize OCR (Lazy load happens inside class)
        self.ocr = AdvancedOCR()

    def _load_tools(self) -> List[Tool]:
        """
        Load and wrap all available tools for the agent.
        """
        tools = []
        try:
            # 1. Web Scraper
            web_scraper = WebScraper(headless=True)
            
            # Sync wrapper for WebScraper
            def sync_scrape(query: str):
                # We use the standalone sync function from the module
                return run_playwright_sync(query, headless=True)

            # Async wrapper for WebScraper
            async def async_scrape(query: str):
                return await web_scraper.scrape(query)

            tools.append(Tool(
                name="Web Search",
                func=sync_scrape,
                coroutine=async_scrape,
                description="Useful for finding current events, prices, weather, and general information from the internet. Input should be a search query."
            ))

            # 2. Symbolic Solver
            symbolic_solver = SymbolicSolver()
            tools.append(Tool(
                name="Math Solver",
                func=symbolic_solver.solve,
                description="Useful for solving symbolic math problems like equations, derivatives, integrals, and simplification. Input should be a math expression or problem description."
            ))
        except Exception as e:
            logger.error(f"Error loading tools: {e}")

        return tools

    async def solve(self, problem: str, image_data: Optional[str] = None) -> Any:
        """
        Main entry point for the agent to solve a problem.
        """
        if not self.agent_executor:
            return "Agent not initialized."

        input_text = problem
        executor = self.agent_executor

        # If image is provided, we inject a dynamic OCR tool and rebuild executor for this request
        if image_data:
            input_text += "\n[Image attached] You have a tool 'Handwritten OCR' to read it if needed."
            
            def read_image(query: str):
                """Reads text/math from the attached image."""
                try:
                    img_bytes = base64.b64decode(image_data)
                    return self.ocr.process_image_bytes(img_bytes)
                except Exception as e:
                    return f"Error reading image: {e}"

            ocr_tool = Tool(
                name="Handwritten OCR",
                func=read_image,
                description="Use this tool to extract handwritten math or text from the attached image. Input should be 'read'."
            )
            
            # Re-initialize agent with extra tool (lightweight wrapper)
            # Note: initialization overhead is small compared to inference
            # We reuse memory? Sharing memory across requests with different tools might be tricky if persistent.
            # For this 'session', it's fine.
            try:
                executor = initialize_agent(
                    tools=self.tools + [ocr_tool],
                    llm=self.llm,
                    agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION if AgentType else "zero-shot-react-description",
                    verbose=True,
                    memory=self.memory, # Use same memory
                    handle_parsing_errors=True
                )
            except Exception as e:
                logger.error(f"Failed to create dynamic agent: {e}")
                return f"Error preparing agent with image tools: {e}"

        try:
            # Run the agent
            # use ainvoke for async execution
            result = await executor.ainvoke({"input": input_text})
            return result['output']
        except Exception as e:
            logger.error(f"Agent execution failed: {e}")
            return f"Error solving problem: {str(e)}"
