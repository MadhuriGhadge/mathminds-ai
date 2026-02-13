# quick test in python console or new file
from app.agents.langchain_mathminds import MathMindsLangChainAgent
import asyncio

async def test():
    agent = MathMindsLangChainAgent()
    result = await agent.solve("Solve 4x - 12 = 8")
    print(result)
    result2 = await agent.solve("What is the gold price today in India?")
    print(result2)

asyncio.run(test())