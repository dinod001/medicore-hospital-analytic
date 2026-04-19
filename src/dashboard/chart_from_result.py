"""
Build one chart descriptor from orchestrator tabular ``result`` (list of row dicts).

Supports multiple numeric series (e.g. admissions + discharges per month).
"""

from __future__ import annotations

from typing import Any, Optional


def _is_number(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def tabular_result_to_chart(
    result: Any,
    *,
    user_message: str = "",
) -> Optional[dict[str, Any]]:
    """
    JSON payload for the SPA: ``kind``, ``title``, ``x_key``, optional ``series``,
    and ``rows`` (list of dicts including x + each series key).
    """
    if not isinstance(result, list) or len(result) == 0:
        return None
    if not all(isinstance(r, dict) for r in result):
        return None

    keys = list(result[0].keys())
    if len(keys) < 2:
        return None

    numeric_cols = [k for k in keys if all(_is_number(r.get(k)) for r in result)]
    if not numeric_cols:
        return None

    time_hints = ("month", "date", "year", "day", "period", "week", "time")
    x_key = None
    for k in keys:
        if any(h in k.lower() for h in time_hints):
            x_key = k
            break
    if x_key is None:
        x_candidates = [k for k in keys if k not in numeric_cols]
        x_key = x_candidates[0] if x_candidates else keys[0]

    series_keys = [k for k in numeric_cols if k != x_key]
    if not series_keys:
        series_keys = [numeric_cols[0]] if numeric_cols[0] != x_key else []
    if not series_keys and numeric_cols:
        series_keys = [numeric_cols[0]]

    if x_key in series_keys and len(series_keys) > 1:
        series_keys = [k for k in series_keys if k != x_key]
    if not series_keys:
        return None

    xl = x_key.lower()
    if any(t in xl for t in ("month", "date", "year", "period", "week")):
        kind = "line"
    elif len(result) <= 20:
        kind = "bar"
    else:
        kind = "line"

    title = (user_message.strip()[:90] + "…") if len(user_message.strip()) > 90 else (
        user_message.strip() or "Query result"
    )

    use_keys = [x_key] + series_keys[:4]
    rows: list[dict[str, Any]] = []
    for r in result:
        row: dict[str, Any] = {}
        for k in use_keys:
            v = r.get(k)
            if k in series_keys and v is not None:
                try:
                    row[k] = float(v)
                except (TypeError, ValueError):
                    row[k] = None
            else:
                row[k] = v if v is not None else ""
        if any(row.get(sk) is not None for sk in series_keys):
            rows.append(row)

    if len(rows) < 1:
        return None

    out: dict[str, Any] = {
        "kind": kind,
        "title": title,
        "x_key": x_key,
        "rows": rows,
    }
    if len(series_keys) > 1:
        out["series"] = [{"key": k, "label": k.replace("_", " ").title()} for k in series_keys[:4]]
    else:
        out["y_key"] = series_keys[0]

    return out
