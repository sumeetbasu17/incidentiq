"""
IncidentIQ - Configuration Module
Centralizes all API keys, model settings, and app configuration.
"""

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Application configuration loaded from environment variables."""

    # --- LLM Configuration ---
    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
    OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
    OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o")

    # --- Search APIs ---
    TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
    SERPER_API_KEY = os.getenv("SERPER_API_KEY", "")

    # --- Embeddings (via OpenRouter - no separate OpenAI key needed) ---
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "") or os.getenv("OPENROUTER_API_KEY", "")
    EMBEDDING_MODEL = "text-embedding-3-small"
    EMBEDDING_BASE_URL = "https://openrouter.ai/api/v1"

    # --- LangSmith Observability ---
    LANGCHAIN_API_KEY = os.getenv("LANGCHAIN_API_KEY", "")
    LANGCHAIN_TRACING_V2 = os.getenv("LANGCHAIN_TRACING_V2", "true")
    LANGCHAIN_PROJECT = os.getenv("LANGCHAIN_PROJECT", "incidentiq")
    LANGCHAIN_ORG_ID = os.getenv("LANGCHAIN_ORG_ID", "")  # e.g. 6ab8790c-a8f5-404b-9f42-1c8d3d19500c
    LANGCHAIN_PROJECT_ID = os.getenv("LANGCHAIN_PROJECT_ID", "")  # e.g. bcbc4ea4-f12d-4e78-8ca7-f61a0881e87b

    # --- Vector DB ---
    CHROMA_PERSIST_DIR = os.path.join(os.path.dirname(__file__), "data", "chroma_db")
    INCIDENT_DB_PATH = os.path.join(os.path.dirname(__file__), "data", "incidents.db")

    # --- Agent Settings ---
    MAX_AGENT_ITERATIONS = 8
    AGENT_TEMPERATURE = 0.1
    RAG_TOP_K = 5
    RAG_CHUNK_SIZE = 1000
    RAG_CHUNK_OVERLAP = 200

    # --- Supported Log Formats ---
    SUPPORTED_LANGUAGES = ["python", "java", "javascript", "go", "ruby", "csharp"]

    # --- Integrations ---
    SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")

    @classmethod
    def validate(cls) -> dict:
        """Check which API keys are configured. Returns status dict."""
        return {
            "OpenRouter LLM": bool(cls.OPENROUTER_API_KEY),
            "Tavily Search": bool(cls.TAVILY_API_KEY),
            "Serper Search": bool(cls.SERPER_API_KEY),
            "LangSmith Tracing": bool(cls.LANGCHAIN_API_KEY),
            "Slack": bool(cls.SLACK_WEBHOOK_URL),
        }

    @classmethod
    def is_ready(cls) -> bool:
        """Check if minimum required keys are set."""
        return bool(cls.OPENROUTER_API_KEY)
