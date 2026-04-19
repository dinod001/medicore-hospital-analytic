"""
Application configuration - loads from YAML param files.

CONFIGURATION POLICY:
====================
- Configuration is loaded from config/param.yaml and config/models.yaml.
- Secrets (API keys) live ONLY in .env and are loaded via os.getenv().
"""

from pathlib import Path
from typing import Any, Dict, Optional
import os
import yaml
from loguru import logger
from dotenv import load_dotenv

load_dotenv()

# ========================================
# Project Paths
# ========================================

# Get project root (parent of src/infrastructure/)
_PROJECT_ROOT = Path(__file__).parent.parent.parent
_CONFIG_DIR = _PROJECT_ROOT / "config"

# ========================================
# YAML Config Loading
# ========================================

def _load_yaml(filename: str) -> Dict[str, Any]:
    """Load a YAML config file."""
    filepath = _CONFIG_DIR / filename
    if not filepath.exists():
        return {}
    
    try:
        text = filepath.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = filepath.read_text(encoding="utf-8-sig")
    return yaml.safe_load(text) or {}


def _get_nested(d: Dict, *keys, default=None):
    """Get nested dictionary value safely."""
    for key in keys:
        if isinstance(d, dict):
            d = d.get(key, default)
        else:
            return default
    return d if d is not None else default


# Load configs
_PARAMS = _load_yaml("param.yaml")
_MODELS = _load_yaml("models.yaml")

# ========================================
# Provider Configuration
# ========================================

PROVIDER = _get_nested(_PARAMS, "provider", "default", default="openrouter")
MODEL_TIER = _get_nested(_PARAMS, "provider", "tier", default="general")
OPENROUTER_BASE_URL = _get_nested(_PARAMS, "provider", "openrouter_base_url",
                                   default="https://openrouter.ai/api/v1")

# ========================================
# Model Names (from models.yaml)
# ========================================

def get_chat_model(provider: Optional[str] = None, tier: Optional[str] = None) -> str:
    """Get chat model name for specified provider and tier."""
    p = provider or PROVIDER
    t = tier or MODEL_TIER

    # Handle provider name mapping
    if p == "gemini":
        p = "google"

    return _get_nested(_MODELS, p, "chat", t, default="openai/gpt-4o-mini")


# Main System Model
CHAT_MODEL = get_chat_model()

# ========================================
# LLM Defaults
# ========================================

LLM_TEMPERATURE = _get_nested(_PARAMS, "llm", "temperature", default=0.0)
LLM_MAX_TOKENS = _get_nested(_PARAMS, "llm", "max_tokens", default=2000)
LLM_STREAMING = _get_nested(_PARAMS, "llm", "streaming", default=False)

ROUTER_MODEL = "openai/gpt-4o-mini"
ROUTER_PROVIDER = "openrouter"

EXTRACTOR_MODEL = "llama-3.1-8b-instant"
EXTRACTOR_PROVIDER = "groq"
GROQ_BASE_URL = "https://api.groq.com/openai/v1"

CHAT_MODEL = "google/gemini-2.5-flash"
CHAT_PROVIDER = "openrouter"

# ========================================
# Logging
# ========================================

LOGGING_ENABLED = _get_nested(_PARAMS, "logging", "enabled", default=True)
LOG_LEVEL = _get_nested(_PARAMS, "logging", "level", default="INFO")
LOG_TOKENS = _get_nested(_PARAMS, "logging", "log_tokens", default=True)
LOG_LATENCY = _get_nested(_PARAMS, "logging", "log_latency", default=True)

# ========================================
# Observability
# ========================================

OBSERVABILITY_ENABLED = _get_nested(_PARAMS, "observability", "enabled", default=True)

# ========================================
# Helper Functions
# ========================================

def get_api_key(provider: Optional[str] = None) -> Optional[str]:
    """Get API key for the specified provider from environment."""
    p = provider or PROVIDER
    key_map = {
        "openrouter": "OPENROUTER_API_KEY",
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "google": "GOOGLE_API_KEY",
        "gemini": "GOOGLE_API_KEY",
        "groq": "GROQ_API_KEY",
        "deepseek": "DEEPSEEK_API_KEY",
    }
    env_var = key_map.get(p, f"{p.upper()}_API_KEY")
    return os.getenv(env_var)


def validate() -> None:
    """Validate configuration and required secrets."""
    api_key = get_api_key()
    if not api_key:
        key_name = "OPENROUTER_API_KEY" if PROVIDER == "openrouter" else f"{PROVIDER.upper()}_API_KEY"
        raise ValueError(
            f"❌ Missing required secret: {key_name}\n"
            f"Please add it to your .env file."
        )


def dump() -> None:
    """Print all active non-secret configuration values for debugging."""
    logger.info("\n" + "=" * 60)
    logger.info("CONFIGURATION (NON-SECRETS ONLY)")
    logger.info("=" * 60)

    logger.info("\n🌐 Provider:")
    logger.info(f"   Provider: {PROVIDER}")
    logger.info(f"   Model Tier: {MODEL_TIER}")
    logger.info(f"   Chat Model: {CHAT_MODEL}")

    logger.info("\n🔧 LLM Defaults:")
    logger.info(f"   Temperature: {LLM_TEMPERATURE}")
    logger.info(f"   Max Tokens: {LLM_MAX_TOKENS}")
    logger.info(f"   Streaming: {LLM_STREAMING}")

    logger.info("\n📝 Logging:")
    logger.info(f"   Level: {LOG_LEVEL}")
    logger.info(f"   Log Tokens: {LOG_TOKENS}")
    logger.info(f"   Log Latency: {LOG_LATENCY}")

    logger.info("\n👁️  Observability:")
    logger.info(f"   Enabled: {OBSERVABILITY_ENABLED}")

    logger.info("\n" + "=" * 60 + "\n")


def get_all_models() -> Dict[str, Any]:
    """Return all available models from models.yaml."""
    return _MODELS


def get_config() -> Dict[str, Any]:
    """Return full config dictionary."""
    return _PARAMS


if __name__ == "__main__":
    dump()
