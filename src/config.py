"""Configuration loader for AI Tactico.

Loads configuration from environment variables and .env file.
Provides centralized configuration management for database, LLM, and agent settings.
"""
import os
from pathlib import Path
from typing import Optional

# Load .env file if it exists
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(env_path)
    except ImportError:
        print("Warning: python-dotenv not installed, using environment variables only")


class Config:
    """Configuration class for AI Tactico."""
    
    # ==================== Database Configuration ====================
    NEO4J_URI: str = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    NEO4J_USER: str = os.getenv("NEO4J_USER", "neo4j")
    NEO4J_PASSWORD: str = os.getenv("NEO4J_PASSWORD", "password")
    
    # ==================== LLM Configuration ====================
    # Base URL for LLM API (supports any OpenAI-compatible provider)
    LLM_BASE_URL: str = os.getenv(
        "LLM_BASE_URL",
        "http://localhost:11434/v1"  # Default to local Ollama
    )
    
    # Model identifier (provider-specific)
    LLM_MODEL: str = os.getenv(
        "LLM_MODEL",
        "gpt-3.5-turbo"  # Generic default
    )
    
    # API key for LLM provider (optional, may not be needed for local inference)
    LLM_API_KEY: str = os.getenv(
        "LLM_API_KEY",
        "not-needed"
    )
    
    # Request timeout in seconds
    LLM_TIMEOUT: int = int(os.getenv("LLM_TIMEOUT", "120"))
    
    # ==================== Agent Configuration ====================
    # Maximum number of iterations for ReAct loop
    AGENT_MAX_ITERATIONS: int = int(os.getenv("AGENT_MAX_ITERATIONS", "10"))
    
    # ==================== Server Configuration ====================
    # Flask app port
    PORT: int = int(os.getenv("PORT", "5000"))
    
    # Flask debug mode
    DEBUG: bool = os.getenv("DEBUG", "False").lower() in ("true", "1", "yes")
    
    # ==================== Validation ====================
    @classmethod
    def validate(cls) -> bool:
        """Validate critical configuration values.
        
        Returns:
            True if all critical values are set, False otherwise.
        """
        critical = [
            ("NEO4J_URI", cls.NEO4J_URI),
            ("LLM_BASE_URL", cls.LLM_BASE_URL),
            ("LLM_MODEL", cls.LLM_MODEL),
        ]
        
        valid = True
        for name, value in critical:
            if not value:
                print(f"ERROR: Critical config missing: {name}")
                valid = False
        
        return valid
    
    @classmethod
    def display(cls) -> None:
        """Display configuration (for debugging, masks API keys)."""
        print("=" * 60)
        print("AI TACTICO CONFIGURATION")
        print("=" * 60)
        
        print("\n[Database]")
        print(f"  URI: {cls.NEO4J_URI}")
        print(f"  User: {cls.NEO4J_USER}")
        print(f"  Password: {'*' * 8}")
        
        print("\n[LLM Service]")
        print(f"  Base URL: {cls.LLM_BASE_URL}")
        print(f"  Model: {cls.LLM_MODEL}")
        api_display = f"***{cls.LLM_API_KEY[-3:]}" if cls.LLM_API_KEY and cls.LLM_API_KEY != "not-needed" else cls.LLM_API_KEY
        print(f"  API Key: {api_display}")
        print(f"  Timeout: {cls.LLM_TIMEOUT}s")
        
        print("\n[Agent]")
        print(f"  Max Iterations: {cls.AGENT_MAX_ITERATIONS}")
        
        print("\n[Server]")
        print(f"  Port: {cls.PORT}")
        print(f"  Debug: {cls.DEBUG}")
        
        print("=" * 60)


# Singleton instance for easy import
config = Config()
