"""
Token counts (tiktoken) and rough USD cost estimates for Langfuse.

Two functions only: ``count_tokens`` and ``estimate_llm_cost_usd``.
Build Langfuse payloads yourself, e.g.::

    pt = count_tokens(system_prompt + "\\n" + user_prompt)
    ct = count_tokens(output_text)
    usage = {"prompt_tokens": pt, "completion_tokens": ct, "total_tokens": pt + ct}
    cost_details = {"total": estimate_llm_cost_usd(pt, ct, model_id)}
    update_current_observation(usage=usage, cost_details=cost_details, model=model_id)

Prices are approximate $/1M tokens — edit ``_USD_PER_1M_INPUT_OUTPUT`` to match billing.
"""

from __future__ import annotations

from typing import Optional

import tiktoken

# (input $/1M, output $/1M) — update when provider pricing changes
_USD_PER_1M_INPUT_OUTPUT: dict[str, tuple[float, float]] = {
    "openai/gpt-4o-mini": (0.15, 0.60),
    "google/gemini-2.5-flash": (0.075, 0.30),
    "llama-3.1-8b-instant": (0.05, 0.08),
}
_DEFAULT_USD_PER_1M: tuple[float, float] = (0.15, 0.60)


def count_tokens(text: str, encoding_name: str = "cl100k_base") -> int:
    """Count tokens with tiktoken (good cross-model estimate for OpenAI-style APIs)."""
    if not text:
        return 0
    enc = tiktoken.get_encoding(encoding_name)
    return len(enc.encode(text))


def estimate_llm_cost_usd(
    prompt_tokens: int,
    completion_tokens: int,
    model_id: Optional[str],
) -> float:
    """Rough total USD = input rate × prompt + output rate × completion (per 1M tokens)."""
    key = (model_id or "").strip().lower()
    inp_m, out_m = _DEFAULT_USD_PER_1M
    for name, prices in _USD_PER_1M_INPUT_OUTPUT.items():
        if name in key:
            inp_m, out_m = prices
            break
    return (prompt_tokens / 1_000_000.0) * inp_m + (completion_tokens / 1_000_000.0) * out_m
