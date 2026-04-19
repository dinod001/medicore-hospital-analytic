"""
Load dashboard datasets from PostgreSQL using date filters (dynamic — no hardcoded KPIs).
"""

from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session


def _df(session: Session, sql: str, params: dict[str, Any]) -> pd.DataFrame:
    rows = session.execute(text(sql), params).mappings().all()
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def fetch_revenue_trend(session: Session, start: date, end: date) -> pd.DataFrame:
    sql = """
    SELECT date_trunc('month', invoice_date)::date AS period,
           SUM(net_amount)::float AS revenue
    FROM billing_invoices
    WHERE invoice_date >= :start AND invoice_date <= :end
    GROUP BY 1
    ORDER BY 1
    """
    return _df(session, sql, {"start": start, "end": end})


def fetch_top_diagnoses(session: Session, start: date, end: date, limit: int = 10) -> pd.DataFrame:
    sql = """
    SELECT diagnosis_description, COUNT(*)::int AS cnt
    FROM diagnoses
    WHERE diagnosis_date >= :start AND diagnosis_date <= :end
    GROUP BY diagnosis_description
    ORDER BY cnt DESC
    LIMIT :limit
    """
    return _df(session, sql, {"start": start, "end": end, "limit": limit})


def fetch_doctor_load(session: Session, start: date, end: date, limit: int = 15) -> pd.DataFrame:
    sql = """
    SELECT TRIM(CONCAT(d.first_name, ' ', d.last_name)) AS doctor_name,
           COUNT(a.appointment_id)::int AS appts
    FROM appointments a
    JOIN doctors d ON a.doctor_id = d.doctor_id
    WHERE a.appointment_date >= :start AND a.appointment_date <= :end
    GROUP BY d.doctor_id, d.first_name, d.last_name
    ORDER BY appts DESC
    LIMIT :limit
    """
    return _df(session, sql, {"start": start, "end": end, "limit": limit})


def fetch_payment_methods(session: Session, start: date, end: date) -> pd.DataFrame:
    sql = """
    SELECT payment_method, SUM(amount)::float AS total
    FROM payments
    WHERE payment_date >= :start AND payment_date <= :end
    GROUP BY payment_method
    ORDER BY total DESC
    """
    return _df(session, sql, {"start": start, "end": end})


def fetch_department_workload(session: Session, start: date, end: date, limit: int = 12) -> pd.DataFrame:
    sql = """
    SELECT dept.department_name, COUNT(a.appointment_id)::int AS cnt
    FROM appointments a
    JOIN doctors doc ON a.doctor_id = doc.doctor_id
    JOIN departments dept ON doc.department_id = dept.department_id
    WHERE a.appointment_date >= :start AND a.appointment_date <= :end
    GROUP BY dept.department_id, dept.department_name
    ORDER BY cnt DESC
    LIMIT :limit
    """
    return _df(session, sql, {"start": start, "end": end, "limit": limit})


def load_all_panel_data(session: Session, start: date, end: date) -> dict[str, pd.DataFrame]:
    return {
        "revenue_trend": fetch_revenue_trend(session, start, end),
        "top_diagnoses": fetch_top_diagnoses(session, start, end),
        "doctor_load": fetch_doctor_load(session, start, end),
        "payment_methods": fetch_payment_methods(session, start, end),
        "department_workload": fetch_department_workload(session, start, end),
    }
