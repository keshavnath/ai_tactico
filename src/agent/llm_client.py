"""LLM client wrapper for text generation across any provider."""
import os
import requests
from typing import Optional
from openai import OpenAI


class LLMClient:
    """Client for LLM text generation via OpenAI-compatible API.
    
    Supports any OpenAI-compatible provider by configuring:
    - base_url: API endpoint (e.g., http://localhost:11434/v1, https://api.openai.com/v1)
    - model: Model identifier (e.g., gpt-4, claude-3-opus, mistral-7b)
    - api_key: Authentication token
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: int = 120,
    ):
        """Initialize LLM client.
        
        Args:
            base_url: API endpoint URL (defaults to LLM_BASE_URL env var)
            model: Model identifier (defaults to LLM_MODEL env var)
            api_key: API key for authentication (defaults to LLM_API_KEY env var)
            timeout: Request timeout in seconds
        """
        self.base_url = base_url or os.getenv("LLM_BASE_URL", "http://localhost:11434/v1")
        self.model = model or os.getenv("LLM_MODEL")
        self.api_key = api_key or os.getenv("LLM_API_KEY", "ollama")
        self.timeout = timeout
        
        self.client = OpenAI(
            base_url=self.base_url,
            api_key=self.api_key,
            timeout=timeout,
        )

    def generate(self, prompt: str, system: Optional[str] = None) -> str:
        """Generate text from prompt.
        
        Args:
            prompt: User message
            system: Optional system prompt providing context/instructions
            
        Returns:
            Generated text
            
        Raises:
            RuntimeError: If API request fails
        """
        messages = []
        
        if system:
            messages.append({"role": "system", "content": system})
        
        messages.append({"role": "user", "content": prompt})
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,
            )
            
            return response.choices[0].message.content
        
        except Exception as e:
            raise RuntimeError(f"LLM API request failed: {e}")

    def health_check(self) -> bool:
        """Check if LLM service is accessible and responding.
        
        Returns:
            True if service is reachable and returns valid response, False otherwise
        """
        try:
            # Try a simple model list call (works with most OpenAI-compatible APIs)
            self.client.models.list()
            return True
        except Exception:
            # If models list isn't supported, try a minimal completion
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": "ping"}],
                    max_tokens=1,
                )
                return response.choices[0].message.content is not None
            except Exception:
                return False
