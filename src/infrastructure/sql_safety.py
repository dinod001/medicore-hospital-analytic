"""
Read-only SQL guard — blocks destructive / multi-statement SQL before execution.

Uses comment stripping + string masking + word-boundary scans (no extra deps).
"""

from __future__ import annotations

import re
from typing import Optional, Tuple

# Whole-word SQL verbs that must never appear in an approved read-only query body.
_FORBIDDEN_VERBS = re.compile(
    r"\b("
    r"INSERT|UPDATE|DELETE|DROP|TRUNCATE|ALTER|CREATE|REPLACE|MERGE|"
    r"GRANT|REVOKE|COPY|VACUUM|ANALYZE"
    r")\b",
    re.IGNORECASE,
)

# SELECT ... INTO creates a table in PostgreSQL — treat as mutating.
_SELECT_INTO = re.compile(r"\bSELECT\b[\s\S]*?\bINTO\b\s+(?:TEMP|TEMPORARY\s+)?TABLE\b", re.IGNORECASE)


def _strip_block_comments(sql: str) -> str:
    return re.sub(r"/\*[\s\S]*?\*/", " ", sql)


def _strip_line_comments(sql: str) -> str:
    out_lines = []
    for line in sql.splitlines():
        if "--" in line:
            line = re.sub(r"--.*$", "", line)
        out_lines.append(line)
    return "\n".join(out_lines)


def _mask_quoted_strings(sql: str) -> str:
    """Mask SQL string literals so keywords inside user data do not false-trigger."""
    out: list[str] = []
    i, n = 0, len(sql)
    while i < n:
        c = sql[i]
        if c == "'":
            out.append("''")
            i += 1
            while i < n:
                if sql[i] == "'" and i + 1 < n and sql[i + 1] == "'":
                    i += 2
                elif sql[i] == "'":
                    i += 1
                    break
                else:
                    i += 1
        elif c == '"':
            out.append('""')
            i += 1
            while i < n and sql[i] != '"':
                i += 1
            if i < n:
                i += 1
        else:
            out.append(c)
            i += 1
    return "".join(out)


def normalize_llm_sql(sql: str) -> str:
    """Strip whitespace and optional markdown fences from an LLM SQL response."""
    raw = str(sql).strip()
    raw = re.sub(r"^\s*```(?:sql)?\s*", "", raw, flags=re.IGNORECASE)
    raw = re.sub(r"\s*```\s*$", "", raw)
    return raw.strip()


def validate_readonly_sql(sql: str) -> Tuple[bool, Optional[str]]:
    """
    Return (True, None) if ``sql`` looks like a single safe read-only statement.

    Otherwise return (False, short user-safe reason).
    """
    raw = normalize_llm_sql(sql)
    if not raw:
        return False, "The model returned empty SQL."

    cleaned = _strip_line_comments(_strip_block_comments(raw))
    cleaned = " ".join(cleaned.split())

    parts = [p.strip() for p in cleaned.split(";") if p.strip()]
    if len(parts) > 1:
        return False, "Multiple SQL statements are not allowed."
    if not parts:
        return False, "No executable SQL found."

    stmt = parts[0]
    lead = stmt.lstrip()
    upper_lead = lead.upper()
    if not (
        upper_lead.startswith("SELECT")
        or upper_lead.startswith("WITH")
        or upper_lead.startswith("EXPLAIN")
    ):
        return False, "Only SELECT / WITH (CTE) / EXPLAIN SELECT queries are allowed."

    if upper_lead.startswith("EXPLAIN"):
        rest = re.sub(
            r"^\s*EXPLAIN\s*(\([^)]*\)\s*)?",
            "",
            lead,
            count=1,
            flags=re.IGNORECASE | re.DOTALL,
        ).strip()
        ru = rest.upper()
        if not (ru.startswith("SELECT") or ru.startswith("WITH")):
            return False, "EXPLAIN must be followed by SELECT or WITH."

    if _SELECT_INTO.search(stmt):
        return False, "SELECT INTO (table-creating) queries are not allowed."

    masked = _mask_quoted_strings(stmt)
    if _FORBIDDEN_VERBS.search(masked):
        return False, "Destructive or DDL keywords were detected in the SQL."

    return True, None
