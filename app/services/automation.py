import logging
import httpx
import asyncio
from typing import Dict, Any, Optional
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from app.core.settings import settings

logger = logging.getLogger(__name__)

class AutomationService:
    """
    Service for integrating with n8n via webhooks.
    Used for external notifications, data logging, and low-code workflows.
    """

    def __init__(self, webhook_url: Optional[str] = None):
        self.webhook_url = webhook_url or settings.N8N_WEBHOOK_URL

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.HTTPError, asyncio.TimeoutError)),
        reraise=True
    )
    async def trigger(self, event_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Triggers an n8n workflow by sending a POST request to a webhook.
        """
        if not self.webhook_url:
            logger.warning("n8n automation triggered but no N8N_WEBHOOK_URL is configured.")
            return {"status": "skipped", "reason": "no_webhook_url"}

        try:
            # Add metadata to the payload
            # Use datetime directly since settings.datetime might not exist reliably
            from datetime import datetime
            data = {
                "event": event_name,
                "timestamp": datetime.now().isoformat(),
                "environment": settings.ENV,
                "data": payload
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.webhook_url,
                    json=data,
                    timeout=10.0
                )
            
            if response.status_code in (200, 201):
                logger.info(f"n8n automation triggered successfully: {event_name}")
                return {"status": "success", "response": response.json() if response.content else "OK"}
            else:
                logger.error(f"n8n automation failed with status {response.status_code}: {response.text}")
                # We raise here to trigger tenacity retry if it's a 5xx or transient 
                if 500 <= response.status_code < 600:
                    raise httpx.HTTPStatusError(f"Server Error {response.status_code}", request=None, response=response)
                return {"status": "error", "code": response.status_code, "detail": response.text}

        except Exception as e:
            logger.error(f"Error triggering n8n automation: {e}")
            raise # Re-raise to let tenacity catch it and retry if it matches the types

# Singleton instance
automation_service = AutomationService()
