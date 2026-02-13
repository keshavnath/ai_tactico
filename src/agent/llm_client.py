"""LLM client wrapper for text generation across any provider."""
import os
import time
import threading
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

        # Rate limiting configuration (simple token-bucket style via timestamps)
        # Maximum number of calls allowed in `rate_window_seconds`.
        self.rate_limit = int(os.getenv("LLM_RATE_LIMIT", "30"))
        self.rate_window_seconds = int(os.getenv("LLM_RATE_WINDOW_SECONDS", "60"))
        # Strategy when the limit is reached: "delay", "block", or "fail"
        self.rate_strategy = os.getenv("LLM_RATE_STRATEGY", "delay")
        # When using 'delay', wait up to this many seconds before failing
        self.rate_max_wait = float(os.getenv("LLM_MAX_WAIT_SECONDS", "10"))

        # Internal state
        self._call_timestamps: list[float] = []
        self._lock = threading.Lock()

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
        
        # Enforce rate limiting before making a call
        start_wait = time.time()
        waited = 0.0
        while True:
            with self._lock:
                # Drop timestamps older than the window
                cutoff = time.time() - self.rate_window_seconds
                self._call_timestamps = [t for t in self._call_timestamps if t > cutoff]
                if len(self._call_timestamps) < self.rate_limit:
                    # Permit and record this call
                    self._call_timestamps.append(time.time())
                    break
                # Rate limit reached
                if self.rate_strategy == "fail":
                    raise RuntimeError("LLM rate limit exceeded (strategy=fail)")
                elif self.rate_strategy == "block":
                    # Will block until a slot frees; release lock and retry
                    pass
                else:  # delay
                    pass
            # Outside lock: wait a short interval then retry, but respect max wait for 'delay'
            time.sleep(0.1)
            waited = time.time() - start_wait
            if self.rate_strategy == "delay" and waited >= self.rate_max_wait:
                raise RuntimeError("LLM rate limit exceeded (strategy=delay, max wait reached)")

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.1,
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
