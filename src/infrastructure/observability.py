"""
Observability layer — LangFuse v4 integration for tracing, cost, and latency.
"""

from loguru import logger
import os
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Config flag
# ---------------------------------------------------------------------------

_ENABLED: Optional[bool] = None


def _is_enabled() -> bool:
    global _ENABLED
    if _ENABLED is not None:
        return _ENABLED
    try:
        from infrastructure.config import _get_nested, _PARAMS
        _ENABLED = _get_nested(_PARAMS, "observability", "enabled", default=True)
    except Exception:
        _ENABLED = True
    return _ENABLED


# ---------------------------------------------------------------------------
# LangFuse v4 imports
# ---------------------------------------------------------------------------

try:
    from langfuse import get_client as _get_client
    from langfuse import observe as _lf_observe
    from langfuse import propagate_attributes as _propagate_attributes
    _lf_available = True
except ImportError:
    _get_client = None
    _lf_observe = None
    _propagate_attributes = None
    _lf_available = False
    logger.warning("langfuse package not installed — tracing is a no-op.")


# ---------------------------------------------------------------------------
# Initialise client on startup
# ---------------------------------------------------------------------------

def _init_langfuse() -> None:
    if not _lf_available or not _is_enabled():
        return

    secret_key = os.getenv("LANGFUSE_SECRET_KEY")
    public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
    base_url = os.getenv("LANGFUSE_BASE_URL", "https://us.cloud.langfuse.com")

    if not secret_key or not public_key:
        logger.warning(
            "LangFuse keys not set (LANGFUSE_SECRET_KEY / LANGFUSE_PUBLIC_KEY). "
            "Tracing is disabled."
        )
        return

    try:
        from langfuse import Langfuse
        Langfuse(
            secret_key=secret_key,
            public_key=public_key,
            host=base_url,
        )
        logger.info("LangFuse v4 client initialised (host={})", base_url)
    except Exception as exc:
        logger.error("Failed to initialise LangFuse: {}", exc)


_init_langfuse()


def get_langfuse():
    """Return the active LangFuse v4 client, or None if unavailable."""
    if not _lf_available or not _is_enabled():
        return None
    try:
        return _get_client()
    except Exception as exc:
        logger.error("Failed to get LangFuse client: {}", exc)
        return None


# ---------------------------------------------------------------------------
# Prompt Management
# ---------------------------------------------------------------------------

def fetch_prompt(
    name: str,
    *,
    fallback: str,
    cache_ttl_seconds: int = 300,
    **compile_vars: str,
) -> str:
    """
    Fetch a prompt from LangFuse Prompt Management with local fallback.

    Args:
        name: Prompt name in LangFuse dashboard.
        fallback: Local string used when LangFuse is unavailable.
        cache_ttl_seconds: Client-side cache TTL (default 5 min).
        **compile_vars: Variables substituted into the template.

    Returns:
        Compiled prompt string ready to send to the LLM.
    """
    client = get_langfuse()
    if client is not None:
        try:
            prompt_obj = client.get_prompt(
                name,
                type="text",
                cache_ttl_seconds=cache_ttl_seconds,
            )
            compiled = prompt_obj.compile(**compile_vars) if compile_vars else prompt_obj.compile()
            logger.debug("LangFuse prompt '{}' loaded (version={})", name, getattr(prompt_obj, "version", "?"))
            return compiled
        except Exception as exc:
            logger.debug(
                "LangFuse prompt '{}' fetch failed: {}. Using local fallback.",
                name, exc,
            )

    if compile_vars:
        return fallback.format(**compile_vars)
    return fallback


# ---------------------------------------------------------------------------
# @observe decorator
# ---------------------------------------------------------------------------

def observe(
    *,
    name: Optional[str] = None,
    as_type: Optional[str] = None,
):
    """
    Decorator that wraps ``langfuse.observe`` (v4).

    Falls back to a no-op when langfuse is not installed or disabled.
    """
    def _noop_decorator(fn):
        return fn

    if not _is_enabled() or not _lf_available:
        return _noop_decorator

    kwargs = {}
    if name is not None:
        kwargs["name"] = name
    if as_type is not None:
        kwargs["as_type"] = as_type

    return _lf_observe(**kwargs)


# ---------------------------------------------------------------------------
# Trace & Observation Helpers — v4 API
# ---------------------------------------------------------------------------

def update_current_trace(
    *,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    metadata: Optional[dict] = None,
    tags: Optional[list] = None,
) -> None:
    """
    Propagate trace-level attributes (user_id, session_id, tags, metadata)
    onto the current active span using LangFuse v4's propagate_attributes().

    Must be called inside a function decorated with @observe() or within
    a start_as_current_observation() context block.
    Safe to call when tracing is disabled (no-op).
    """
    if not _lf_available or not _is_enabled():
        return
    try:
        kwargs = {}
        if user_id is not None:
            kwargs["user_id"] = user_id
        if session_id is not None:
            kwargs["session_id"] = session_id
        if metadata is not None:
            kwargs["metadata"] = metadata
        if tags is not None:
            kwargs["tags"] = tags
        if kwargs:
            # propagate_attributes is a context manager — use it inline
            # by entering and immediately exiting to stamp the current span
            with _propagate_attributes(**kwargs):
                pass
    except Exception as exc:
        logger.debug("update_current_trace failed (non-critical): {}", exc)


def update_current_observation(
    *,
    input: Optional[str] = None,
    output: Optional[str] = None,
    metadata: Optional[dict] = None,
    usage: Optional[dict] = None,
    model: Optional[str] = None,
    cost_details: Optional[dict[str, float]] = None,
) -> None:
    """
    Update the active observation created by @observe() or
    start_as_current_observation().

    Maps to Langfuse SDK ``update_current_span`` (default @observe spans) and
    ``update_current_generation`` when usage, cost, or model are set.

    Safe to call when tracing is disabled (no-op).
    """
    if not _lf_available or not _is_enabled():
        return
    try:
        client = _get_client()
        span_kwargs: dict = {}
        if input is not None:
            span_kwargs["input"] = input
        if output is not None:
            span_kwargs["output"] = output
        if metadata is not None:
            span_kwargs["metadata"] = metadata

        gen_only: dict = {}
        if model is not None:
            gen_only["model"] = model
        if usage is not None:
            gen_only["usage_details"] = usage
        if cost_details is not None:
            gen_only["cost_details"] = cost_details

        if gen_only:
            client.update_current_generation(**span_kwargs, **gen_only)
        elif span_kwargs:
            client.update_current_span(**span_kwargs)
    except Exception as exc:
        logger.debug("update_current_observation failed (non-critical): {}", exc)


# ---------------------------------------------------------------------------
# Flush
# ---------------------------------------------------------------------------

def flush() -> None:
    """Flush pending LangFuse events (call before program exit)."""
    if not _lf_available or not _is_enabled():
        return
    try:
        client = _get_client()
        client.flush()
        logger.debug("LangFuse flushed.")
    except Exception as exc:
        logger.debug("LangFuse flush failed: {}", exc)