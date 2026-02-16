
import pytest
import asyncio
import base64
import io
from PIL import Image, ImageDraw, ImageFont
from app.agents.adk_mathminds import MathMindsADKAgent

def create_test_image_b64(text: str) -> str:
    """Creates a simple image with text and returns base64 string."""
    img = Image.new('RGB', (400, 100), color=(255, 255, 255))
    d = ImageDraw.Draw(img)
    # default font or simple drawing
    d.text((10, 40), text, fill=(0, 0, 0))
    
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode()

@pytest.mark.asyncio
async def test_ocr_tool_usage():
    """
    Verifies that the ADK agent can use the 'read_image' tool to extract text.
    """
    agent = MathMindsADKAgent()
    
    secret_text = "The secret number is 999."
    image_b64 = create_test_image_b64(secret_text)
    
    print("\n--- Starting OCR Tool Test ---")
    print(f"Generated image with text: '{secret_text}'")

    # Ask the agent to read it
    # We specifically ask to "read the text" to encourage tool usage 
    # over just vision model (though both might work).
    response = await agent.solve(
        problem="What is the secret number written in this image? Use your read_image tool if needed.",
        image_data=image_b64,
        session_id="test_ocr_session",
        user_id="test_user"
    )
    
    print(f"Agent Response: {response}")

    assert "999" in response, f"Agent failed to extract the number. Response: {response}"
    print("\nSUCCESS: OCR Tool verified!")

if __name__ == "__main__":
    asyncio.run(test_ocr_tool_usage())
