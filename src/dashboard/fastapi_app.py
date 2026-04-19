"""
MediCore — FastAPI serves the static UI + dashboard baseline + chat via AgentOrchestrator.

Run from project root:
  set PYTHONPATH=.
  uvicorn src.dashboard.fastapi_app:app --reload --host 127.0.0.1 --port 8000
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from src.agents.orchestrator import AgentOrchestrator
from src.dashboard.chart_specs import default_dashboard_specs
from src.dashboard.data_service import load_all_panel_data
from src.infrastructure.db.sql_client import get_session
from src.infrastructure.llm.llm_provider import get_router_llm

ROOT = Path(__file__).resolve().parent.parent.parent
WEB_DIR = ROOT / "web"

_orchestrator: Optional[AgentOrchestrator] = None


def get_orchestrator() -> AgentOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = AgentOrchestrator(get_router_llm())
    return _orchestrator


app = FastAPI(title="MediCore", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

if WEB_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")


@app.get("/")
def serve_index() -> FileResponse:
    index = WEB_DIR / "index.html"
    if not index.is_file():
        raise HTTPException(404, "web/index.html missing")
    return FileResponse(index)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/dashboard/baseline")
def dashboard_baseline(
    start: date = Query(...),
    end: date = Query(...),
) -> dict[str, Any]:
    """Always-on 5 panels: revenue, diagnoses, doctors, payments, departments."""
    if start > end:
        raise HTTPException(400, "start must be <= end")
    session = get_session()
    try:
        frames = load_all_panel_data(session, start, end)
        payload = {k: v.to_dict(orient="records") for k, v in frames.items()}
        return {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "chart_specs": [s.model_dump() for s in default_dashboard_specs()],
            "panels": payload,
        }
    finally:
        session.close()


class ChatBody(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    memory: list[dict[str, Any]] = Field(default_factory=list)


@app.post("/api/chat")
def api_chat(body: ChatBody) -> dict[str, Any]:
    """
    Main chat path — ``AgentOrchestrator.chat_with_sql_agent``.

    On successful tabular SQL runs, may include ``chart`` + ``insight`` (same as ``message``).
    """
    return get_orchestrator().chat_with_sql_agent(body.message.strip(), body.memory)
