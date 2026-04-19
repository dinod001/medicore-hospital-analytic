"""
Structured chart specifications — same shape a Result Interpreter LLM should output.

Your app validates this JSON and renders with Plotly (never execute LLM-generated code).
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

ChartKind = Literal["bar", "line", "pie"]


class ChartSpec(BaseModel):
    """Declarative chart description for safe rendering."""

    chart_id: str = Field(..., description="Stable id, e.g. revenue_trend")
    kind: ChartKind
    title: str
    x_label: Optional[str] = None
    y_label: Optional[str] = None
    # For pie: category column key and value column key in the payload rows
    category_key: Optional[str] = None
    value_key: Optional[str] = None


def default_dashboard_specs() -> list[ChartSpec]:
    """Pre-built specs for the 5 rubric panels (types vary: line, bar, pie)."""
    return [
        ChartSpec(
            chart_id="revenue_trend",
            kind="line",
            title="Revenue trend (net invoiced)",
            x_label="Month",
            y_label="Net amount (local currency)",
            category_key="period",
            value_key="revenue",
        ),
        ChartSpec(
            chart_id="top_diagnoses",
            kind="bar",
            title="Top diagnoses (by count)",
            x_label="Diagnosis",
            y_label="Count",
            category_key="diagnosis_description",
            value_key="cnt",
        ),
        ChartSpec(
            chart_id="doctor_load",
            kind="bar",
            title="Doctor load (appointments)",
            x_label="Doctor",
            y_label="Appointments",
            category_key="doctor_name",
            value_key="appts",
        ),
        ChartSpec(
            chart_id="payment_methods",
            kind="pie",
            title="Payments by method",
            category_key="payment_method",
            value_key="total",
        ),
        ChartSpec(
            chart_id="department_workload",
            kind="bar",
            title="Department workload (appointments)",
            x_label="Department",
            y_label="Appointments",
            category_key="department_name",
            value_key="cnt",
        ),
    ]
