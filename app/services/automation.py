import logging
import httpx
from typing import Dict, Any, Optional
from app.core.settings import settings

logger = logging.getLogger(__name__)

class AutomationService:
    """
    Service for integrating with n8n via webhooks.
    Used for external notifications, data logging, and low-code workflows.
    """

    def __init__(self, webhook_url: Optional[str] = None):
        self.webhook_url = webhook_url or settings.N8N_WEBHOOK_URL

    async def trigger(self, event_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Triggers an n8n workflow by sending a POST request to a webhook.
        """
        if not self.webhook_url:
            logger.warning("n8n automation triggered but no N8N_WEBHOOK_URL is configured.")
            return {"status": "skipped", "reason": "no_webhook_url"}

        try:
            # Add metadata to the payload
            data = {
                "event": event_name,
                "timestamp": settings.datetime.now().isoformat() if hasattr(settings, 'datetime') else None,
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
                return {"status": "error", "code": response.status_code, "detail": response.text}

        except Exception as e:
            logger.error(f"Error triggering n8n automation: {e}")
            return {"status": "error", "detail": str(e)}

# Singleton instance
automation_service = AutomationService()
