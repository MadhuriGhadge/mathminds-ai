"""
LLM client that talks to a local Ollama instance.

Supports:
- HTTP API (preferred) at http://localhost:11434/api/generate
- Ollama CLI fallback (if installed) via subprocess

The client offers two convenience methods:
- generate_text: general text generation
- generate_code: explicitly used when expecting code output

Model default: qwen2.5:3b-instruct-q4_K_M
"""
import json
import logging
import subprocess
from typing import Optional

import requests

logger = logging.getLogger("mathminds.llm_client")


class OllamaError(Exception):
    pass


class LLMClient:
    def __init__(self, model: str = "qwen2.5:3b-instruct-q4_K_M", timeout: int = 120):
        self.model = model
        self.timeout = timeout
        # Ollama HTTP endpoint (local)
        self.base_url = "http://127.0.0.1:11434"
        self.api_endpoint = f"{self.base_url}/api/generate"

    def _call_http(self, prompt: str, max_tokens: int = 1024, temperature: float = 0.0) -> str:
        """
        Call Ollama HTTP API with proper streaming response handling.
        Ollama returns newline-delimited JSON objects when streaming.
        """
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,  # Request non-streaming response
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            }
        }
        try:
            resp = requests.post(self.api_endpoint, json=payload, timeout=self.timeout)
            resp.raise_for_status()
            
            # Parse the response
            data = resp.json()
            
            # Ollama's non-streaming response format: {"response": "text here", "done": true}
            if isinstance(data, dict) and "response" in data:
                return data["response"]
            
            # Fallback: try to extract any text-like field
            for key in ["text", "content", "output"]:
                if key in data:
                    return str(data[key])
            
            # Last resort: return JSON dump
            logger.warning(f"Unexpected Ollama response format: {data}")
            return json.dumps(data)
            
        except requests.exceptions.Timeout as e:
            logger.error(f"Ollama HTTP request timed out after {self.timeout}s")
            raise OllamaError(f"HTTP request timed out: {e}")
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Could not connect to Ollama at {self.api_endpoint}")
            raise OllamaError(f"Connection failed: {e}")
        except Exception as e:
            logger.error(f"HTTP call to Ollama failed: {e}")
            raise OllamaError(f"HTTP call failed: {e}")

    def _call_cli(self, prompt: str, max_tokens: int = 1024, temperature: float = 0.0) -> str:
        """
        Use the ollama CLI as a fallback. It must be installed and on PATH.
        Command: ollama run <model> "<prompt>"
        """
        # Use 'run' instead of 'generate' for better compatibility
        cmd = ["ollama", "run", self.model, prompt]
        try:
            proc = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
                timeout=self.timeout,
                text=True,
            )
            stdout = proc.stdout.strip()
            if not stdout:
                stderr = proc.stderr.strip()
                raise OllamaError(f"CLI returned empty output. Stderr: {stderr}")
            return stdout
        except subprocess.TimeoutExpired:
            logger.error(f"Ollama CLI timed out after {self.timeout}s")
            raise OllamaError(f"CLI call timed out after {self.timeout}s")
        except subprocess.CalledProcessError as e:
            logger.error(f"Ollama CLI failed with exit code {e.returncode}")
            logger.error(f"Stderr: {e.stderr}")
            raise OllamaError(f"CLI call failed: {e}")
        except FileNotFoundError:
            logger.error("Ollama CLI not found. Is it installed and in PATH?")
            raise OllamaError("Ollama CLI not found in PATH")
        except Exception as e:
            logger.error(f"CLI call to Ollama failed: {e}")
            raise OllamaError(f"CLI call failed: {e}")

    def generate_text(
        self, prompt: str, max_tokens: int = 1024, temperature: float = 0.0
    ) -> str:
        """
        Generate text from the local Ollama LLM. Tries HTTP endpoint first, then CLI.
        """
        errors = []
        
        # Try HTTP first
        try:
            return self._call_http(prompt, max_tokens=max_tokens, temperature=temperature)
        except OllamaError as e:
            errors.append(f"HTTP: {e}")
            logger.warning(f"HTTP method failed: {e}")
        
        # Try CLI as fallback
        try:
            return self._call_cli(prompt, max_tokens=max_tokens, temperature=temperature)
        except OllamaError as e:
            errors.append(f"CLI: {e}")
            logger.warning(f"CLI method failed: {e}")
        
        # Both failed
        error_msg = "All Ollama methods failed. " + " | ".join(errors)
        logger.error(error_msg)
        raise OllamaError(error_msg)

    def generate_code(
        self, prompt: str, max_tokens: int = 2048, temperature: float = 0.0
    ) -> str:
        """
        Convenience wrapper for generating code. Downstreams expect raw text; this
        function does no post-processing beyond calling generate_text.
        """
        return self.generate_text(prompt, max_tokens=max_tokens, temperature=temperature)

    def check_connection(self) -> bool:
        """
        Check if Ollama is accessible and the model is available.
        Returns True if connection is successful, False otherwise.
        """
        try:
            # Try to list models
            resp = requests.get(f"{self.base_url}/api/tags", timeout=5)
            resp.raise_for_status()
            data = resp.json()
            
            # Check if our model is in the list
            if "models" in data:
                model_names = [m.get("name", "") for m in data["models"]]
                if self.model in model_names:
                    logger.info(f"Model {self.model} is available")
                    return True
                else:
                    logger.warning(f"Model {self.model} not found. Available: {model_names}")
                    return False
            return True
        except Exception as e:
            logger.error(f"Connection check failed: {e}")
            return False