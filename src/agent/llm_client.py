"""LLM client wrapper for local and remote inference."""
import os
import requests
from typing import Optional


class LLMClient:
    """HTTP client for LLM inference (Ollama, OpenAI, etc.)."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: int = 120,
    ):
        self.base_url = base_url or os.getenv("LLM_BASE_URL", "http://localhost:11434")
        self.model = model or os.getenv("LLM_MODEL", "qwen3:1.7b")
        self.timeout = timeout

    def generate(self, prompt: str, system: Optional[str] = None) -> str:
        """Generate text from prompt using Ollama.
        
        Args:
            prompt: User message
            system: Optional system prompt
            
        Returns:
            Generated text
        """
        messages = []
        
        if system:
            messages.append({"role": "system", "content": system})
        
        messages.append({"role": "user", "content": prompt})
        
        try:
            response = requests.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": messages,
                    "stream": False,
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
            
            result = response.json()
            return result["message"]["content"]
        
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Ollama request failed: {e}")

    def health_check(self) -> bool:
        """Check if Ollama service is running and model is available."""
        try:
            response = requests.get(
                f"{self.base_url}/api/tags",
                timeout=5,
            )
            if response.status_code != 200:
                return False
            
            # Check if specific model is available
            data = response.json()
            models = data.get("models", [])
            model_names = [m.get("name", "") for m in models]
            
            # Model names in Ollama may include tags, check both exact and prefix match
            has_model = any(
                self.model in name or name.startswith(self.model + ":")
                for name in model_names
            )
            
            return has_model
            
        except Exception:
            return False
