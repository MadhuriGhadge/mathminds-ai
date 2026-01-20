#!/usr/bin/env python3
"""
MathMinds AI - Entry point

Starts a simple CLI for interacting with the MathMinds system. Accepts a math
problem as input, routes it to the appropriate agent, executes generated
SymPy code safely, and returns a structured JSON response.

This file intentionally avoids web/cloud dependencies and runs entirely locally.
"""
import argparse
import json
import logging
import sys
import uuid
from datetime import datetime, timezone

from core.router import Router
from core.llm_client import LLMClient, OllamaError
from models.schemas import MMResponse

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mathminds.app")


def check_ollama_status():
    """
    Check if Ollama is running and the required model is available.
    Provides helpful error messages if not.
    """
    try:
        client = LLMClient()
        if client.check_connection():
            logger.info("✓ Ollama is running and model is available")
            return True
        else:
            logger.error("✗ Ollama is running but model not found")
            print("\n" + "="*60, file=sys.stderr)
            print("ERROR: Required model not found", file=sys.stderr)
            print("="*60, file=sys.stderr)
            print(f"\nThe model '{client.model}' is not available.", file=sys.stderr)
            print("\nTo install it, run:", file=sys.stderr)
            print(f"  ollama pull {client.model}", file=sys.stderr)
            print("\nOr use a different model by modifying the code.", file=sys.stderr)
            print("="*60 + "\n", file=sys.stderr)
            return False
    except Exception as e:
        logger.error(f"✗ Cannot connect to Ollama: {e}")
        print("\n" + "="*60, file=sys.stderr)
        print("ERROR: Cannot connect to Ollama", file=sys.stderr)
        print("="*60, file=sys.stderr)
        print("\nOllama doesn't appear to be running.", file=sys.stderr)
        print("\nTo start Ollama:", file=sys.stderr)
        print("  1. Make sure Ollama is installed: https://ollama.ai", file=sys.stderr)
        print("  2. Start the Ollama service:", file=sys.stderr)
        print("     - On Windows/Mac: Ollama should start automatically", file=sys.stderr)
        print("     - On Linux: run 'ollama serve' in a separate terminal", file=sys.stderr)
        print("  3. Verify it's running: ollama list", file=sys.stderr)
        print("="*60 + "\n", file=sys.stderr)
        return False


def main():
    parser = argparse.ArgumentParser(prog="mathminds", description="MathMinds AI CLI")
    parser.add_argument(
        "query",
        nargs="?",
        help="Math problem to solve. If omitted, reads from stdin.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw JSON only.",
    )
    parser.add_argument(
        "--skip-check",
        action="store_true",
        help="Skip Ollama connection check (not recommended).",
    )
    args = parser.parse_args()

    # Check Ollama status unless skipped
    if not args.skip_check:
        if not check_ollama_status():
            sys.exit(1)

    if args.query:
        query = args.query
    else:
        # Read from stdin
        logger.info("Reading problem from stdin...")
        query = sys.stdin.read().strip()

    if not query:
        print("No query provided.", file=sys.stderr)
        sys.exit(2)

    # Create request id and timestamp
    request_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')

    router = Router()

    logger.info("Routing the request...")
    try:
        response = router.route(query, request_id=request_id, timestamp=timestamp)
    except OllamaError as e:
        # Handle LLM errors gracefully
        logger.error(f"LLM error: {e}")
        response = {
            "agent": "unknown",
            "success": False,
            "error": f"LLM error: {str(e)}",
            "meta": {}
        }

    mm_response = MMResponse(
        id=request_id,
        timestamp=timestamp,
        query=query,
        agent=response.get("agent"),
        success=response.get("success", False),
        code=response.get("code"),
        sanitized_code=response.get("sanitized_code"),
        execution_result=response.get("execution_result"),
        explanation=response.get("explanation"),
        error=response.get("error"),
        meta=response.get("meta", {}),
    )

    output = mm_response.to_json()

    if args.json:
        print(output)
    else:
        # Pretty-print JSON with minimal commentary
        print(output)


if __name__ == "__main__":
    main()